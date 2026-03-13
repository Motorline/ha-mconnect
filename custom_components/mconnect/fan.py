"""Fan platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    DEVICE_TYPE_PLATFORM,
    DOMAIN,
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
    def _add_new_fans() -> None:
        current_ids = set(coordinator.data.devices.keys())
        known_ids.intersection_update(current_ids)
        new_entities: list[MConnectFan] = []
        for device_id, device in coordinator.data.devices.items():
            if device_id in known_ids:
                continue
            dtype = device.get("type", "")
            if DEVICE_TYPE_PLATFORM.get(dtype) != "fan":
                continue

            on_off_vid = None
            speed_vid = None
            for v in device.get("values", []):
                vtype = v.get("type", "")
                if vtype == VALUE_TYPE_ON_OFF and not v.get("query_only"):
                    on_off_vid = v.get("value_id")
                elif vtype == VALUE_TYPE_MULTILEVEL and not v.get("query_only"):
                    speed_vid = v.get("value_id")

            if on_off_vid or speed_vid:
                known_ids.add(device_id)
                new_entities.append(MConnectFan(coordinator, device, on_off_vid, speed_vid))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_fans()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_fans))


class MConnectFan(MConnectEntity, FanEntity):
    """Representation of a Motorline fan."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        on_off_vid: str | None,
        speed_vid: str | None,
    ) -> None:
        primary = on_off_vid or speed_vid
        super().__init__(coordinator, device_data, primary)
        self._on_off_vid = on_off_vid
        self._speed_vid = speed_vid

        features = FanEntityFeature(0)
        if speed_vid:
            features |= FanEntityFeature.SET_SPEED
        self._attr_supported_features = features

    @property
    def is_on(self) -> bool | None:
        if self._on_off_vid:
            val = self._get_value(self._on_off_vid)
            if val is not None:
                try:
                    return int(val) == 1
                except (ValueError, TypeError):
                    pass
        if self._speed_vid:
            val = self._get_value(self._speed_vid)
            if val is not None:
                try:
                    return int(val) > 0
                except (ValueError, TypeError):
                    pass
        return None

    @property
    def percentage(self) -> int | None:
        if not self._speed_vid:
            return None
        val_obj = self._get_value_obj(self._speed_vid)
        if not val_obj:
            return None
        try:
            val = int(val_obj.get("value", 0))
            v_min = int(val_obj.get("min", 0))
            v_max = int(val_obj.get("max", 100))
            return ranged_value_to_percentage((v_min, v_max), val)
        except (ValueError, TypeError):
            return None

    async def async_turn_on(self, percentage: int | None = None, **kwargs: Any) -> None:
        if percentage is not None and self._speed_vid:
            await self.async_set_percentage(percentage)
        elif self._on_off_vid:
            await self._send_value(self._on_off_vid, 1)
        elif self._speed_vid:
            val_obj = self._get_value_obj(self._speed_vid)
            v_max = int(val_obj.get("max", 100)) if val_obj else 100
            await self._send_value(self._speed_vid, v_max)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._on_off_vid:
            await self._send_value(self._on_off_vid, 0)
        elif self._speed_vid:
            val_obj = self._get_value_obj(self._speed_vid)
            v_min = int(val_obj.get("min", 0)) if val_obj else 0
            await self._send_value(self._speed_vid, v_min)

    async def async_set_percentage(self, percentage: int) -> None:
        if not self._speed_vid:
            return
        val_obj = self._get_value_obj(self._speed_vid)
        v_min = int(val_obj.get("min", 0)) if val_obj else 0
        v_max = int(val_obj.get("max", 100)) if val_obj else 100
        actual = math.ceil(percentage_to_ranged_value((v_min, v_max), percentage))
        await self._send_value(self._speed_vid, actual)
