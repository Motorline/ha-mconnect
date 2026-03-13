"""Motorline MCONNECT integration for Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MConnectApi, MConnectApiError, MConnectAuthError, MConnectTokenRevokedError, MConnectAccessError
from .const import (
    CONF_HOME_ID,
    DOMAIN,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_USE_SSL,
    PLATFORMS,
)
from .coordinator import MConnectCoordinator
from .mqtt_listener import MConnectMqttListener

_LOGGER = logging.getLogger(__name__)

type MConnectConfigEntry = ConfigEntry[MConnectRuntimeData]


@dataclass
class MConnectRuntimeData:
    """Runtime data for MCONNECT integration."""

    coordinator: MConnectCoordinator
    api: MConnectApi
    mqtt: MConnectMqttListener | None


async def async_setup_entry(hass: HomeAssistant, entry: MConnectConfigEntry) -> bool:
    """Set up Motorline MCONNECT from a config entry."""
    session = async_get_clientsession(hass)
    api = MConnectApi(session)

    # Restore saved tokens
    api.import_tokens(entry.data)

    # Test connection before setup (Bronze: test-before-setup)
    try:
        await api.ensure_valid_token()
    except MConnectAccessError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="access_denied",
        ) from err
    except MConnectAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except (MConnectApiError, Exception) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    # Verify API works by fetching devices
    try:
        await api.get_devices()
    except MConnectAccessError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="access_denied",
        ) from err
    except MConnectAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
    except (MConnectApiError, Exception) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    # MQTT listener
    home_id = entry.data[CONF_HOME_ID]
    mqtt_listener: MConnectMqttListener | None = None
    try:
        mqtt_listener = MConnectMqttListener(
            home_id=home_id,
            host=MQTT_HOST,
            port=MQTT_PORT,
            use_ssl=MQTT_USE_SSL,
            get_token=lambda: api.access_token,
        )
    except Exception:
        _LOGGER.warning("MQTT listener setup failed, continuing without real-time updates")

    # Create coordinator
    coordinator = MConnectCoordinator(hass, api, mqtt_listener, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data (Bronze: runtime-data)
    entry.runtime_data = MConnectRuntimeData(
        coordinator=coordinator,
        api=api,
        mqtt=mqtt_listener,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Persist refreshed tokens on each coordinator update
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _persist_tokens(hass, entry, api)
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MConnectConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and getattr(entry, "runtime_data", None):
        await entry.runtime_data.coordinator.async_shutdown()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: MConnectConfigEntry) -> None:
    """Revoke personal access token when integration is removed."""
    session = async_get_clientsession(hass)
    api = MConnectApi(session)
    api.import_tokens(entry.data)

    if api.refresh_token:
        _LOGGER.debug("Revoking personal access token before removal")
        await api.revoke_token()


def _persist_tokens(
    hass: HomeAssistant, entry: MConnectConfigEntry, api: MConnectApi
) -> None:
    """Persist refreshed tokens back to the config entry data."""
    new_tokens = api.export_tokens()
    updated_data = {**entry.data, **new_tokens}
    if updated_data != entry.data:
        hass.config_entries.async_update_entry(entry, data=updated_data)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: MConnectConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow manual removal of a device from the UI.

    Returns True if the device is not currently present in the MCONNECT data
    (i.e. it's safe to remove). Blocks removal of active devices.
    """
    if not getattr(entry, "runtime_data", None):
        return True
    coordinator = entry.runtime_data.coordinator

    # Check if any identifier matches an active device
    for identifier in device_entry.identifiers:
        if identifier[0] != DOMAIN:
            continue
        device_id = identifier[1]
        # Allow removal if device/home is no longer in coordinator data
        if device_id in coordinator.data.devices:
            return False  # Still active, block removal
        if device_id.startswith("home_"):
            return False  # Don't allow removing the home device

    return True
