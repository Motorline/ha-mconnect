"""Button platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.helpers.translation import async_get_translations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DEVICE_TYPE_PLATFORM, DOMAIN, VALUE_TYPE_MULTILEVEL
from .coordinator import MConnectCoordinator
from .cover import LINK_CMD_PEDESTRIAN_OPEN, _find_link_value_ids
from .entity import MConnectEntity

PARALLEL_UPDATES = 0

# BridgeButtonsMode enum (0-indexed): ZERO, ONE, TWO, THREE, FOUR, SHUTTER
_MODE_SHUTTER = 5

_BUTTON_RF_VALUES = (2, 3, 1, 4)

_SHUTTER_ICONS = {1: "mdi:arrow-up", 2: "mdi:stop", 3: "mdi:arrow-down"}

# English fallbacks used when translations are unavailable
_SHUTTER_FALLBACK = {1: "1 Open", 2: "2 Stop", 3: "3 Close"}
_BUTTON_FALLBACK = {1: "Button 1", 2: "Button 2", 3: "Button 3", 4: "Button 4"}


def _channel_vid(device: dict[str, Any]) -> str | None:
    """Return the main Multilevel channel value_id for an RF device."""
    for v in device.get("values", []):
        if (
            v.get("type") == VALUE_TYPE_MULTILEVEL
            and not v.get("query_only")
            and not v.get("configuration")
        ):
            return v.get("value_id")
    return None


def _mode(device: dict[str, Any]) -> int:
    """Return mode_channel integer (BridgeButtonsMode index), defaulting to 4 (FOUR)."""
    for v in device.get("values", []):
        if v.get("value_id", "").startswith("mode_channel"):
            try:
                return int(v.get("value") or 0)
            except (ValueError, TypeError):
                pass
    return 4


def _button_count(mode: int) -> int:
    """Number of visible buttons for a given mode."""
    if mode == _MODE_SHUTTER:
        return 3
    return min(max(mode, 1), 4)


def _labels(device: dict[str, Any]) -> dict[int, str]:
    """Parse channel_labels JSON array into {button_num: label}.

    The API stores labels as a JSON array of {"id": "button_0N", "v": "..."}.
    """
    for v in device.get("values", []):
        if v.get("value_id", "").startswith("channel_labels"):
            raw = v.get("value")
            if raw:
                try:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(data, list):
                        result: dict[int, str] = {}
                        for item in data:
                            item_id = item.get("id", "")
                            label = str(item.get("v", "")).strip()
                            if item_id.startswith("button_0") and label:
                                try:
                                    result[int(item_id[-1])] = label
                                except (ValueError, IndexError):
                                    pass
                        return result
                except (json.JSONDecodeError, TypeError):
                    pass
    return {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCONNECT button entities from a config entry."""
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    trans = await async_get_translations(hass, hass.config.language, "entity", [DOMAIN])

    def _t(key: str) -> str | None:
        return trans.get(f"component.{DOMAIN}.entity.button.{key}.name")

    @callback
    def _add_new_buttons() -> None:
        current_ids = set(coordinator.data.devices.keys())
        stale = {c for c in known_ids if c.split("_", 1)[0] not in current_ids}
        known_ids.difference_update(stale)

        new_entities: list[ButtonEntity] = []

        for device_id, device in coordinator.data.devices.items():
            dtype = device.get("type", "")

            # LINK gates: expose a pedestrian-open button next to the cover
            if dtype == "devices.types.LINK":
                state_vid, _ = _find_link_value_ids(device)
                if not state_vid:
                    continue
                combo = f"{device_id}_{state_vid}_pedestrian"
                if combo in known_ids:
                    continue
                known_ids.add(combo)
                new_entities.append(
                    MConnectLinkPedestrianButton(coordinator, device, state_vid)
                )
                continue

            if DEVICE_TYPE_PLATFORM.get(dtype) != "button":
                continue

            vid = _channel_vid(device)
            if not vid:
                continue

            mode_val = _mode(device)
            num_btns = _button_count(mode_val)
            label_map = _labels(device)

            for btn in range(1, num_btns + 1):
                combo = f"{device_id}_{vid}_{btn}"
                if combo in known_ids:
                    continue
                known_ids.add(combo)

                custom_label = label_map.get(btn, "")
                if custom_label:
                    label = custom_label
                elif mode_val == _MODE_SHUTTER:
                    label = _t(f"shutter_{'open' if btn == 1 else 'stop' if btn == 2 else 'close'}") \
                            or _SHUTTER_FALLBACK.get(btn, f"{btn}")
                else:
                    label = _t(f"rf_button_{btn}") or _BUTTON_FALLBACK.get(btn, f"Button {btn}")

                new_entities.append(
                    MConnectRfButton(coordinator, device, vid, btn, label, mode_val)
                )

        if new_entities:
            async_add_entities(new_entities)

    _add_new_buttons()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_buttons))


class MConnectRfButton(MConnectEntity, ButtonEntity):
    """One button on an RF_CONTROLLER or RF_REMOTE device."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
        button_num: int,
        label: str,
        mode: int,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)
        self._button_num = button_num

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{value_id}_{button_num}"
        self._attr_translation_key = None
        self._attr_name = label

        self._attr_icon = (
            _SHUTTER_ICONS.get(button_num, f"mdi:numeric-{button_num}")
            if mode == _MODE_SHUTTER
            else f"mdi:numeric-{button_num}"
        )

    async def async_press(self) -> None:
        """Send the RF value for this button position."""
        rf_value = _BUTTON_RF_VALUES[self._button_num - 1]
        await self._send_value(self._value_id, rf_value)


class MConnectLinkPedestrianButton(MConnectEntity, ButtonEntity):
    """Pedestrian-open button for a LINK gate device."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{value_id}_pedestrian"
        # Base class derives name/category/icon from the gate_state value
        # object (query_only Multilevel) — override for this command button.
        self._attr_translation_key = "pedestrian_open"
        # _attr_name must not exist at all, otherwise it takes precedence
        # over the translation key when HA resolves the entity name.
        if hasattr(self, "_attr_name"):
            del self._attr_name
        self._attr_entity_category = None
        self._attr_icon = "mdi:walk"

    async def async_press(self) -> None:
        """Send the pedestrian open command to gate_state."""
        await self._send_value(self._value_id, LINK_CMD_PEDESTRIAN_OPEN)
