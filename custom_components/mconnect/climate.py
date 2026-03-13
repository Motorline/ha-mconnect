"""Climate platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_TYPE_PLATFORM,
    DOMAIN,
    VALUE_TYPE_MODES,
    VALUE_TYPE_MULTILEVEL,
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
    def _add_new_climates() -> None:
        current_ids = set(coordinator.data.devices.keys())
        known_ids.intersection_update(current_ids)
        new_entities: list[MConnectClimate] = []
        for device_id, device in coordinator.data.devices.items():
            if device_id in known_ids:
                continue
            dtype = device.get("type", "")
            if DEVICE_TYPE_PLATFORM.get(dtype) != "climate":
                continue
            known_ids.add(device_id)
            new_entities.append(MConnectClimate(coordinator, device))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_climates()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_climates))


class MConnectClimate(MConnectEntity, ClimateEntity):
    """Representation of a Motorline thermostat."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, device_data)

        self._on_off_vid: str | None = None
        self._setpoint_vid: str | None = None
        self._current_temp_vid: str | None = None
        self._mode_vid: str | None = None

        for v in device_data.get("values", []):
            vtype = v.get("type", "")
            vid = v.get("value_id", "")
            vid_lower = vid.lower()

            if vtype == VALUE_TYPE_ON_OFF and not v.get("query_only"):
                self._on_off_vid = vid
            elif vtype == VALUE_TYPE_MULTILEVEL:
                if "setpoint" in vid_lower or "target" in vid_lower:
                    self._setpoint_vid = vid
                elif "temperature" in vid_lower or "temp" in vid_lower:
                    if v.get("query_only"):
                        self._current_temp_vid = vid
                    else:
                        self._setpoint_vid = self._setpoint_vid or vid
            elif vtype == VALUE_TYPE_MODES:
                self._mode_vid = vid

        # Features
        features = ClimateEntityFeature(0)
        if self._setpoint_vid:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_supported_features = features

        # HVAC modes
        modes = [HVACMode.OFF]
        if self._on_off_vid or self._setpoint_vid:
            modes.append(HVACMode.HEAT)
        self._attr_hvac_modes = modes

        # Temperature range
        if self._setpoint_vid:
            sp_obj = self._find_value_obj(device_data, self._setpoint_vid)
            if sp_obj:
                self._attr_min_temp = float(sp_obj.get("min", 5))
                self._attr_max_temp = float(sp_obj.get("max", 35))
                precision = sp_obj.get("precision")
                if precision and precision > 0:
                    self._attr_target_temperature_step = float(10 ** -precision)

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._on_off_vid:
            val = self._get_value(self._on_off_vid)
            if val is not None:
                try:
                    return HVACMode.HEAT if int(val) == 1 else HVACMode.OFF
                except (ValueError, TypeError):
                    pass
        return HVACMode.HEAT  # Default if no on/off control

    @property
    def current_temperature(self) -> float | None:
        if self._current_temp_vid:
            val = self._get_value(self._current_temp_vid)
            if val is not None:
                try:
                    return round(float(val), 1)
                except (ValueError, TypeError):
                    pass
        return None

    @property
    def target_temperature(self) -> float | None:
        if self._setpoint_vid:
            val = self._get_value(self._setpoint_vid)
            if val is not None:
                try:
                    return round(float(val), 1)
                except (ValueError, TypeError):
                    pass
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if not self._on_off_vid:
            return
        if hvac_mode == HVACMode.OFF:
            await self._send_value(self._on_off_vid, 0)
        else:
            await self._send_value(self._on_off_vid, 1)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is not None and self._setpoint_vid:
            await self._send_value(self._setpoint_vid, temp)
