"""Lock platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_PLATFORM, DOMAIN, VALUE_TYPE_LOCK_UNLOCK
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
    def _add_new_locks() -> None:
        current_ids = set(coordinator.data.devices.keys())
        known_ids.intersection_update(current_ids)
        new_entities: list[MConnectLock] = []
        for device_id, device in coordinator.data.devices.items():
            if device_id in known_ids:
                continue
            dtype = device.get("type", "")
            if DEVICE_TYPE_PLATFORM.get(dtype) != "lock":
                continue
            for v in device.get("values", []):
                if v.get("type") == VALUE_TYPE_LOCK_UNLOCK and not v.get("query_only"):
                    known_ids.add(device_id)
                    new_entities.append(MConnectLock(coordinator, device, v.get("value_id")))
                    break
        if new_entities:
            async_add_entities(new_entities)

    _add_new_locks()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_locks))


class MConnectLock(MConnectEntity, LockEntity):
    """Representation of a Motorline lock."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)

    @property
    def is_locked(self) -> bool | None:
        val = self._get_value()
        if val is None:
            return None
        try:
            return int(val) == 1
        except (ValueError, TypeError):
            return None

    async def async_lock(self, **kwargs: Any) -> None:
        await self._send_value(self._value_id, 1)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._send_value(self._value_id, 0)
