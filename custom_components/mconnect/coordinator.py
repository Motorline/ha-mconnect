"""Data coordinator for the Motorline MCONNECT integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MConnectApi, MConnectApiError, MConnectAuthError, MConnectAccessError
from .const import (
    DEVICE_TYPE_IGNORE,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
)
from .mqtt_listener import MConnectMqttListener

_LOGGER = logging.getLogger(__name__)


class MConnectData:
    """Holds the latest known state of all devices and scenes."""

    def __init__(self) -> None:
        self.devices: dict[str, dict[str, Any]] = {}   # device_id → device dict
        self.scenes: dict[str, dict[str, Any]] = {}     # scene_id → scene dict
        self.home: dict[str, Any] = {}

    def get_device_value(self, device_id: str, value_id: str) -> Any:
        """Return current value for a specific device value_id."""
        device = self.devices.get(device_id)
        if not device:
            return None
        for v in device.get("values", []):
            if v.get("value_id") == value_id:
                return v.get("value")
        return None

    def get_device_value_obj(self, device_id: str, value_id: str) -> dict[str, Any] | None:
        """Return the full value object for a device value_id."""
        device = self.devices.get(device_id)
        if not device:
            return None
        for v in device.get("values", []):
            if v.get("value_id") == value_id:
                return v
        return None

    def update_device_value(self, device_id: str, value_id: str, value_data: dict[str, Any]) -> bool:
        """Update a single value in the local cache. Returns True if the device exists."""
        device = self.devices.get(device_id)
        if not device:
            return False
        for v in device.get("values", []):
            if v.get("value_id") == value_id:
                # Merge: the MQTT payload typically has the full value object
                v.update(value_data)
                return True
        return False


class MConnectCoordinator(DataUpdateCoordinator[MConnectData]):
    """Fetches device data and integrates MQTT real-time updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MConnectApi,
        mqtt: MConnectMqttListener | None,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
            config_entry=config_entry,
        )
        self.api = api
        self.mqtt = mqtt
        self._data = MConnectData()
        self._mqtt_unsub_state: Any = None
        self._mqtt_unsub_refresh: Any = None
        self._previous_device_ids: set[str] = set()
        self._previous_scene_ids: set[str] = set()

    # ── Setup / teardown ─────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Initial setup: start MQTT listener if available."""
        if self.mqtt:
            self._mqtt_unsub_state = self.mqtt.register_state_callback(
                self._on_mqtt_state_update
            )
            self._mqtt_unsub_refresh = self.mqtt.register_refresh_callback(
                self._on_mqtt_refresh_signal
            )
            await self.hass.async_add_executor_job(self.mqtt.start)

    async def async_shutdown(self) -> None:
        """Stop MQTT and clean up."""
        if self._mqtt_unsub_state:
            try:
                self._mqtt_unsub_state()
            except (ValueError, Exception):
                pass
        if self._mqtt_unsub_refresh:
            try:
                self._mqtt_unsub_refresh()
            except (ValueError, Exception):
                pass
        if self.mqtt:
            await self.hass.async_add_executor_job(self.mqtt.stop)

    # ── Coordinator fetch ────────────────────────────────────────────────

    async def _async_update_data(self) -> MConnectData:
        """Fetch all devices and scenes from the REST API."""
        try:
            raw_devices = await self.api.get_devices()
            raw_scenes = await self.api.get_scenes()
        except MConnectAccessError as err:
            # Access period restriction — NOT an auth error, don't trigger reauth
            # Just skip this update, entities will show last known state
            _LOGGER.warning("MCONNECT: access restricted — %s", err)
            raise UpdateFailed(f"Access restricted: {err}") from err
        except MConnectAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except MConnectApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        # Index devices by _id
        devices: dict[str, dict[str, Any]] = {}
        for d in raw_devices:
            dtype = d.get("type", "")
            if dtype in DEVICE_TYPE_IGNORE:
                continue
            did = d.get("_id") or d.get("id")
            if did:
                devices[str(did)] = d

        scenes: dict[str, dict[str, Any]] = {}
        for s in raw_scenes:
            sid = s.get("_id") or s.get("id")
            if sid:
                scenes[str(sid)] = s

        self._data.devices = devices
        self._data.scenes = scenes

        # Detect removed devices and scenes (Gold: dynamic-devices)
        current_device_ids = set(devices.keys())
        current_scene_ids = set(scenes.keys())

        removed_devices = self._previous_device_ids - current_device_ids
        removed_scenes = self._previous_scene_ids - current_scene_ids

        if removed_devices or removed_scenes:
            self._cleanup_removed_entities(removed_devices, removed_scenes)

        self._previous_device_ids = current_device_ids
        self._previous_scene_ids = current_scene_ids

        _LOGGER.debug(
            "MCONNECT: fetched %d devices, %d scenes",
            len(devices), len(scenes),
        )

        return self._data

    # ── Device/scene removal ────────────────────────────────────────────

    def _cleanup_removed_entities(
        self, removed_devices: set[str], removed_scenes: set[str]
    ) -> None:
        """Remove HA device entries for devices/scenes no longer in MCONNECT."""
        if not self.config_entry:
            return

        dev_reg = dr.async_get(self.hass)

        for device_id in removed_devices:
            # Devices are registered with identifier (DOMAIN, device_id)
            device_entry = dev_reg.async_get_device(
                identifiers={(DOMAIN, device_id)}
            )
            if device_entry:
                _LOGGER.info(
                    "Removing device %s (no longer in MCONNECT)", device_id
                )
                dev_reg.async_remove_device(device_entry.id)

        for scene_id in removed_scenes:
            # Scenes share the home device, so we remove via entity registry
            # Scene entities have unique_id = f"{DOMAIN}_scene_{scene_id}"
            from homeassistant.helpers import entity_registry as er
            ent_reg = er.async_get(self.hass)
            entity_id = ent_reg.async_get_entity_id(
                "scene", DOMAIN, f"{DOMAIN}_scene_{scene_id}"
            )
            if entity_id:
                _LOGGER.info(
                    "Removing scene entity %s (no longer in MCONNECT)", entity_id
                )
                ent_reg.async_remove(entity_id)

    # ── MQTT callbacks (called from background thread) ───────────────────

    def _on_mqtt_state_update(
        self, device_id: str, value_id: str, value_data: dict[str, Any]
    ) -> None:
        """Handle a real-time state update from MQTT."""
        updated = self._data.update_device_value(device_id, value_id, value_data)
        if updated:
            # Schedule HA state update on the event loop
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self._data)
        else:
            _LOGGER.debug(
                "MQTT update for unknown device/value: %s/%s", device_id, value_id
            )

    def _on_mqtt_refresh_signal(self) -> None:
        """Handle a refresh signal — trigger a full coordinator refresh."""
        _LOGGER.debug("MQTT refresh signal received, scheduling full update")
        self.hass.loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self.async_request_refresh())
        )
