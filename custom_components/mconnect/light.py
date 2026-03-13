"""Light platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_TYPE_PLATFORM,
    DOMAIN,
    VALUE_TYPE_BRIGHTNESS,
    VALUE_TYPE_ON_OFF,
)
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
    def _add_new_lights() -> None:
        current_ids = set(coordinator.data.devices.keys())
        known_ids.intersection_update(current_ids)
        new_entities: list[MConnectLight] = []
        for device_id, device in coordinator.data.devices.items():
            if device_id in known_ids:
                continue
            dtype = device.get("type", "")
            if DEVICE_TYPE_PLATFORM.get(dtype) != "light":
                continue

            on_off_vid = None
            brightness_vid = None
            for v in device.get("values", []):
                vtype = v.get("type", "")
                vid = v.get("value_id", "")
                if vtype == VALUE_TYPE_ON_OFF and not v.get("query_only"):
                    on_off_vid = vid
                elif vtype == VALUE_TYPE_BRIGHTNESS and not v.get("query_only"):
                    brightness_vid = vid

            if on_off_vid or brightness_vid:
                known_ids.add(device_id)
                new_entities.append(
                    MConnectLight(coordinator, device, on_off_vid, brightness_vid)
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_new_lights()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_lights))


class MConnectLight(MConnectEntity, LightEntity):
    """Representation of a Motorline light."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        on_off_vid: str | None,
        brightness_vid: str | None,
    ) -> None:
        # Use the on_off value as primary, or brightness if no on_off
        primary = on_off_vid or brightness_vid
        super().__init__(coordinator, device_data, primary)

        self._on_off_vid = on_off_vid
        self._brightness_vid = brightness_vid

        if brightness_vid:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        if self._on_off_vid:
            val = self._get_value(self._on_off_vid)
            if val is not None:
                try:
                    return int(val) == 1
                except (ValueError, TypeError):
                    return None
        # If no on/off, use brightness > 0
        if self._brightness_vid:
            val = self._get_value(self._brightness_vid)
            if val is not None:
                try:
                    return int(val) > 0
                except (ValueError, TypeError):
                    return None
        return None

    @property
    def brightness(self) -> int | None:
        if not self._brightness_vid:
            return None
        val_obj = self._get_value_obj(self._brightness_vid)
        if not val_obj:
            return None
        try:
            val = int(val_obj.get("value", 0))
            v_min = int(val_obj.get("min", 0))
            v_max = int(val_obj.get("max", 100))
            if v_max == v_min:
                return 0
            # Convert to HA 0-255 range
            return round((val - v_min) / (v_max - v_min) * 255)
        except (ValueError, TypeError):
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and self._brightness_vid:
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            val_obj = self._get_value_obj(self._brightness_vid)
            v_min = int(val_obj.get("min", 0)) if val_obj else 0
            v_max = int(val_obj.get("max", 100)) if val_obj else 100
            actual = round(v_min + (ha_brightness / 255) * (v_max - v_min))
            await self._send_value(self._brightness_vid, actual)
        elif self._on_off_vid:
            await self._send_value(self._on_off_vid, 1)
        elif self._brightness_vid:
            val_obj = self._get_value_obj(self._brightness_vid)
            v_max = int(val_obj.get("max", 100)) if val_obj else 100
            await self._send_value(self._brightness_vid, v_max)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._on_off_vid:
            await self._send_value(self._on_off_vid, 0)
        elif self._brightness_vid:
            val_obj = self._get_value_obj(self._brightness_vid)
            v_min = int(val_obj.get("min", 0)) if val_obj else 0
            await self._send_value(self._brightness_vid, v_min)
