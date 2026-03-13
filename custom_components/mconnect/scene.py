"""Scene platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MConnectCoordinator
from .entity import resolve_icon

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    @callback
    def _add_new_scenes() -> None:
        """Check for new scenes and add them."""
        new_entities: list[MConnectScene] = []
        current_ids = set(coordinator.data.scenes.keys())

        # Remove stale IDs so re-added scenes can be re-created
        known_ids.intersection_update(current_ids)

        for scene_id, scene in coordinator.data.scenes.items():
            if scene_id not in known_ids:
                known_ids.add(scene_id)
                new_entities.append(MConnectScene(coordinator, scene))
        if new_entities:
            async_add_entities(new_entities)

    # Add initial scenes
    _add_new_scenes()

    # Listen for coordinator updates to detect new scenes
    entry.async_on_unload(coordinator.async_add_listener(_add_new_scenes))


class MConnectScene(CoordinatorEntity[MConnectCoordinator], SceneEntity):
    """Representation of a Motorline MCONNECT scene."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        scene_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._scene_id = str(scene_data.get("_id") or scene_data.get("id"))
        self._scene_data = scene_data
        self._attr_unique_id = f"{DOMAIN}_scene_{self._scene_id}"
        self._attr_name = scene_data.get("name", "Scene")

        # Icon
        icon_name = scene_data.get("icon")
        resolved = resolve_icon(icon_name)
        if resolved:
            self._attr_icon = resolved

    @property
    def device_info(self) -> DeviceInfo:
        home_id = self._scene_data.get("home_id", "")
        return DeviceInfo(
            identifiers={(DOMAIN, f"home_{home_id}")},
            name="MCONNECT Home",
            manufacturer=MANUFACTURER,
            model="MCONNECT",
        )

    async def async_activate(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.api.execute_scene(self._scene_id)
        except Exception:
            _LOGGER.exception("Failed to execute scene %s", self._scene_id)
            raise
