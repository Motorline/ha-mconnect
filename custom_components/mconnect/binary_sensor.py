"""Binary sensor platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_PLATFORM, DOMAIN, VALUE_TYPE_BINARY, VALUE_TYPE_ON_OFF
from .coordinator import MConnectCoordinator
from .entity import MConnectEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # Coordinator-based, no limit needed

# Infer device class from value_id keywords
_BINARY_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "motion": BinarySensorDeviceClass.MOTION,
    "occupancy": BinarySensorDeviceClass.OCCUPANCY,
    "contact": BinarySensorDeviceClass.DOOR,
    "door": BinarySensorDeviceClass.DOOR,
    "window": BinarySensorDeviceClass.WINDOW,
    "smoke": BinarySensorDeviceClass.SMOKE,
    "water": BinarySensorDeviceClass.MOISTURE,
    "leak": BinarySensorDeviceClass.MOISTURE,
    "tamper": BinarySensorDeviceClass.TAMPER,
    "vibration": BinarySensorDeviceClass.VIBRATION,
    "ias_zone": BinarySensorDeviceClass.MOTION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    @callback
    def _add_new_binary_sensors() -> None:
        new_entities: list[MConnectBinarySensor] = []

        # Sync known_ids: remove combos for devices that no longer exist
        current_device_ids = set(coordinator.data.devices.keys())
        stale = {c for c in known_ids if c.split("_", 1)[0] not in current_device_ids}
        known_ids.difference_update(stale)

        for device_id, device in coordinator.data.devices.items():
            dtype = device.get("type", "")
            if DEVICE_TYPE_PLATFORM.get(dtype) != "binary_sensor":
                continue
            for v in device.get("values", []):
                vtype = v.get("type", "")
                vid = v.get("value_id", "")
                combo = f"{device_id}_{vid}"
                if combo in known_ids:
                    continue
                if vtype in (VALUE_TYPE_BINARY, VALUE_TYPE_ON_OFF) and not v.get("configuration"):
                    known_ids.add(combo)
                    new_entities.append(MConnectBinarySensor(coordinator, device, vid, dtype))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_binary_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_binary_sensors))


class MConnectBinarySensor(MConnectEntity, BinarySensorEntity):
    """Representation of a Motorline binary sensor."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
        device_type: str,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)

        # Infer device class
        vid_lower = value_id.lower()
        for keyword, dc in _BINARY_CLASS_MAP.items():
            if keyword in vid_lower:
                self._attr_device_class = dc
                break
        else:
            if "MOTION" in device_type:
                self._attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool | None:
        val = self._get_value()
        if val is None:
            return None
        try:
            return int(val) != 0
        except (ValueError, TypeError):
            return None
