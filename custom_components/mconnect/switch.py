"""Switch platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_TYPE_PLATFORM,
    DOMAIN,
    SHUTTER_MODE_RELAY,
    VALUE_TYPE_BINARY,
    VALUE_TYPE_ON_OFF,
)
from .coordinator import MConnectCoordinator
from .entity import MConnectEntity
from .shutter_helpers import get_shutter_labels, get_shutter_mode, get_shutter_show_mode

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCONNECT switch entities from a config entry."""
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    @callback
    def _add_new_switches() -> None:
        current_ids = set(coordinator.data.devices.keys())
        # Clean up stale combo keys
        stale = {c for c in known_ids if c.split("_", 1)[0] not in current_ids}
        known_ids.difference_update(stale)

        new_entities: list[MConnectSwitch | MConnectShutterRelaySwitch] = []

        for device_id, device in coordinator.data.devices.items():
            dtype = device.get("type", "")

            # ── SHUTTER in relay mode → relay switches ────────────────
            if dtype == "devices.types.SHUTTER":
                mode = get_shutter_mode(device)
                if mode != SHUTTER_MODE_RELAY:
                    continue

                show_mode = get_shutter_show_mode(device)
                labels = get_shutter_labels(device)

                for v in device.get("values", []):
                    vid = v.get("value_id", "")
                    if vid not in ("relay_01", "relay_02"):
                        continue
                    combo = f"{device_id}_{vid}"
                    if combo in known_ids:
                        continue
                    # Respect show_mode visibility (default True)
                    if not show_mode.get(vid, True):
                        continue
                    known_ids.add(combo)
                    new_entities.append(
                        MConnectShutterRelaySwitch(
                            coordinator, device, vid,
                            custom_name=labels.get(vid),
                        )
                    )
                continue

            # ── Standard switch devices ───────────────────────────────
            if device_id in known_ids:
                continue
            if DEVICE_TYPE_PLATFORM.get(dtype) != "switch":
                continue

            for v in device.get("values", []):
                vtype = v.get("type", "")
                vid = v.get("value_id", "")
                if vtype in (VALUE_TYPE_ON_OFF, VALUE_TYPE_BINARY) and not v.get("query_only") and not v.get("configuration"):
                    is_plug = dtype == "devices.types.PLUG"
                    known_ids.add(device_id)
                    new_entities.append(MConnectSwitch(coordinator, device, vid, is_plug))
                    break

        if new_entities:
            async_add_entities(new_entities)

    _add_new_switches()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_switches))


class MConnectSwitch(MConnectEntity, SwitchEntity):
    """Representation of a Motorline switch."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
        is_plug: bool = False,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)
        if is_plug:
            self._attr_device_class = SwitchDeviceClass.OUTLET

    @property
    def is_on(self) -> bool | None:
        val = self._get_value()
        if val is None:
            return None
        try:
            return int(val) == 1
        except (ValueError, TypeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send_value(self._value_id, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send_value(self._value_id, 0)


class MConnectShutterRelaySwitch(MConnectEntity, SwitchEntity):
    """A SHUTTER relay in relay mode (mode 1).

    Each relay (relay_01, relay_02) becomes an independent switch entity.
    Custom labels from the MCONNECT app are used when available.
    """

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
        custom_name: str | None = None,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)
        self._attr_device_class = SwitchDeviceClass.SWITCH

        # Use custom label from MCONNECT if available
        if custom_name:
            self._attr_name = custom_name

    @property
    def is_on(self) -> bool | None:
        val = self._get_value()
        if val is None:
            return None
        try:
            return int(val) == 1
        except (ValueError, TypeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send_value(self._value_id, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send_value(self._value_id, 0)
