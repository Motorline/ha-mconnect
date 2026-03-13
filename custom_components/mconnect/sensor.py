"""Sensor platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_PLATFORM, DOMAIN, VALUE_TYPE_MULTILEVEL
from .coordinator import MConnectCoordinator
from .entity import MConnectEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # Coordinator-based, no limit needed

# Mapping of known value_id patterns to HA sensor classes
_SENSOR_CLASS_MAP: dict[str, tuple[SensorDeviceClass | None, str | None]] = {
    "temperature": (SensorDeviceClass.TEMPERATURE, "°C"),
    "humidity": (SensorDeviceClass.HUMIDITY, "%"),
    "illuminance": (SensorDeviceClass.ILLUMINANCE, "lx"),
    "pressure": (SensorDeviceClass.PRESSURE, "hPa"),
    "battery": (SensorDeviceClass.BATTERY, "%"),
    "voltage": (SensorDeviceClass.VOLTAGE, "V"),
    "current": (SensorDeviceClass.CURRENT, "A"),
    "power": (SensorDeviceClass.POWER, "W"),
    "energy": (SensorDeviceClass.ENERGY, "kWh"),
    "rssi": (SensorDeviceClass.SIGNAL_STRENGTH, "dBm"),
}


def _infer_sensor_class(
    value_id: str, unit: str | None
) -> tuple[SensorDeviceClass | None, str | None]:
    """Infer HA sensor class from the value_id or unit."""
    vid_lower = value_id.lower()
    for keyword, (dc, default_unit) in _SENSOR_CLASS_MAP.items():
        if keyword in vid_lower:
            return dc, unit or default_unit
    return None, unit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()  # device_id + value_id combos

    @callback
    def _add_new_sensors() -> None:
        new_entities: list[MConnectSensor] = []

        # Sync known_ids: remove combos for devices that no longer exist
        current_device_ids = set(coordinator.data.devices.keys())
        stale = {c for c in known_ids if c.split("_", 1)[0] not in current_device_ids}
        known_ids.difference_update(stale)

        for device_id, device in coordinator.data.devices.items():
            dtype = device.get("type", "")
            is_sensor_type = DEVICE_TYPE_PLATFORM.get(dtype) == "sensor"

            for v in device.get("values", []):
                vid = v.get("value_id", "")
                vtype = v.get("type", "")
                combo = f"{device_id}_{vid}"
                if combo in known_ids:
                    continue
                if v.get("configuration") or v.get("command_only"):
                    continue

                add = False
                if is_sensor_type and (vtype == VALUE_TYPE_MULTILEVEL or v.get("query_only")):
                    add = True
                elif not is_sensor_type and v.get("query_only") and vtype == VALUE_TYPE_MULTILEVEL:
                    add = True

                if add:
                    known_ids.add(combo)
                    new_entities.append(MConnectSensor(coordinator, device, vid))

        if new_entities:
            async_add_entities(new_entities)

    _add_new_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_sensors))


class MConnectSensor(MConnectEntity, SensorEntity):
    """Representation of a Motorline sensor value."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)

        val_obj = self._find_value_obj(device_data, value_id)
        unit = val_obj.get("unit") if val_obj else None
        dc, final_unit = _infer_sensor_class(value_id, unit)

        if dc:
            self._attr_device_class = dc
        if final_unit:
            self._attr_native_unit_of_measurement = final_unit
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | str | None:
        val = self._get_value()
        if val is None:
            return None
        try:
            return round(float(val), 2)
        except (ValueError, TypeError):
            return str(val)
