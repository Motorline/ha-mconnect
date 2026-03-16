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

# Mapping from sensor value_id to show_mode key
_SHUTTER_SENSOR_SHOW_MAP: dict[str, str] = {
    "sensor_open": "input_01",
    "sensor_close": "input_02",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCONNECT binary sensor entities from a config entry."""
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    @callback
    def _add_new_binary_sensors() -> None:
        new_entities: list[MConnectBinarySensor | MConnectShutterInputSensor] = []

        # Sync known_ids: remove combos for devices that no longer exist
        current_device_ids = set(coordinator.data.devices.keys())
        stale = {c for c in known_ids if c.split("_", 1)[0] not in current_device_ids}
        known_ids.difference_update(stale)

        for device_id, device in coordinator.data.devices.items():
            dtype = device.get("type", "")

            # ── SHUTTER relay mode → input sensors ────────────────────
            if dtype == "devices.types.SHUTTER":
                mode = get_shutter_mode(device)
                if mode != SHUTTER_MODE_RELAY:
                    continue

                show_mode = get_shutter_show_mode(device)
                labels = get_shutter_labels(device)

                for v in device.get("values", []):
                    vid = v.get("value_id", "")
                    if vid not in ("sensor_open", "sensor_close"):
                        continue
                    combo = f"{device_id}_{vid}"
                    if combo in known_ids:
                        continue
                    # Check show_mode visibility using input_01/input_02 key
                    show_key = _SHUTTER_SENSOR_SHOW_MAP.get(vid, vid)
                    if not show_mode.get(show_key, True):
                        continue
                    known_ids.add(combo)
                    new_entities.append(
                        MConnectShutterInputSensor(
                            coordinator, device, vid,
                            custom_name=labels.get(show_key),
                        )
                    )
                continue

            # ── Standard binary sensors (MOTION_SENSOR, etc.) ─────────
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


class MConnectShutterInputSensor(MConnectEntity, BinarySensorEntity):
    """A SHUTTER input sensor in relay mode (mode 1).

    sensor_open and sensor_close become binary sensor entities.
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

        # Use custom label from MCONNECT if available
        if custom_name:
            self._attr_name = custom_name

        # sensor_open/sensor_close → opening/door device class
        if "open" in value_id:
            self._attr_device_class = BinarySensorDeviceClass.OPENING
        else:
            self._attr_device_class = BinarySensorDeviceClass.OPENING

    @property
    def is_on(self) -> bool | None:
        val = self._get_value()
        if val is None:
            return None
        try:
            return int(val) != 0
        except (ValueError, TypeError):
            return None
