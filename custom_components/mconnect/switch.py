"""Switch platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_PLATFORM, DOMAIN, VALUE_TYPE_ON_OFF, VALUE_TYPE_BINARY
from .coordinator import MConnectCoordinator
from .entity import MConnectEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # Coordinator-based, no limit needed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    @callback
    def _add_new_switches() -> None:
        current_ids = set(coordinator.data.devices.keys())
        known_ids.intersection_update(current_ids)
        new_entities: list[MConnectSwitch] = []
        for device_id, device in coordinator.data.devices.items():
            if device_id in known_ids:
                continue
            dtype = device.get("type", "")
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
