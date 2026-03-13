"""Cover platform for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COVER_DEVICE_CLASSES,
    DEVICE_TYPE_PLATFORM,
    DOMAIN,
    VALUE_TYPE_MULTILEVEL,
    VALUE_TYPE_OPEN_CLOSE,
)
from .coordinator import MConnectCoordinator
from .entity import MConnectEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# ── LINK gate_state codes ────────────────────────────────────────────────
# Commands sent TO the gate_state value_id
LINK_CMD_CLOSE = 0
LINK_CMD_FULL_OPEN = 2
LINK_CMD_PEDESTRIAN_OPEN = 3
LINK_CMD_STOP = 13

# State codes received FROM the gate_state value_id
GATE_STATE_CLOSED = {0, 1}
GATE_STATE_OPEN = {2, 3, 4, 5}
GATE_STATE_CLOSING = {6, 7}
GATE_STATE_OPENING = {8, 9, 12}  # 12 = pre-flashing before open
GATE_STATE_STOPPED = {13}
GATE_STATE_IDLE = {14}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MCONNECT cover entities from a config entry."""
    coordinator: MConnectCoordinator = entry.runtime_data.coordinator
    known_ids: set[str] = set()

    @callback
    def _add_new_covers() -> None:
        new_entities: list[MConnectCover] = []
        current_ids = set(coordinator.data.devices.keys())
        known_ids.intersection_update(current_ids)
        for device_id, device in coordinator.data.devices.items():
            if device_id in known_ids:
                continue
            dtype = device.get("type", "")
            if DEVICE_TYPE_PLATFORM.get(dtype) != "cover":
                continue

            if dtype == "devices.types.LINK":
                # LINK: first value = gate_state (commands + state), second = gate_position (read-only)
                state_vid, position_vid = _find_link_value_ids(device)
                if state_vid:
                    known_ids.add(device_id)
                    new_entities.append(
                        MConnectCover(
                            coordinator, device,
                            value_id=state_vid,
                            gate_state_vid=state_vid,
                            gate_position_vid=position_vid,
                        )
                    )
            else:
                # Standard covers: single OpenClose or Multilevel value
                value_id = _find_cover_value_id(device)
                if value_id:
                    known_ids.add(device_id)
                    new_entities.append(MConnectCover(coordinator, device, value_id))

        if new_entities:
            async_add_entities(new_entities)

    _add_new_covers()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_covers))


def _find_link_value_ids(
    device: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Find gate_state and gate_position value_ids for a LINK device.

    Returns (gate_state_vid, gate_position_vid).
    Convention: first value = gate_state, second value = gate_position.
    """
    values = device.get("values", [])
    state_vid: str | None = None
    position_vid: str | None = None

    if len(values) >= 1:
        state_vid = values[0].get("value_id")
    if len(values) >= 2:
        position_vid = values[1].get("value_id")

    return state_vid, position_vid


def _find_cover_value_id(device: dict[str, Any]) -> str | None:
    """Find the best value_id to use as the cover control (non-LINK)."""
    for v in device.get("values", []):
        vtype = v.get("type", "")
        vid = v.get("value_id", "")
        if v.get("command_only") and v.get("configuration"):
            continue
        if vtype == VALUE_TYPE_OPEN_CLOSE:
            return vid
        if vtype == VALUE_TYPE_MULTILEVEL and not v.get("query_only"):
            return vid
    # Fallback: first non-config, non-query-only value
    for v in device.get("values", []):
        if not v.get("query_only") and not v.get("configuration"):
            return v.get("value_id")
    return None


class MConnectCover(MConnectEntity, CoverEntity):
    """Representation of a Motorline cover (gate, shutter, door, etc.)."""

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str,
        gate_state_vid: str | None = None,
        gate_position_vid: str | None = None,
    ) -> None:
        super().__init__(coordinator, device_data, value_id)

        self._gate_state_vid = gate_state_vid
        self._gate_position_vid = gate_position_vid
        self._is_link = device_data.get("type") == "devices.types.LINK"

        dtype = device_data.get("type", "")
        dc = COVER_DEVICE_CLASSES.get(dtype)
        if dc:
            self._attr_device_class = CoverDeviceClass(dc)

        # Features
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        if self._is_link:
            # LINK: no SET_POSITION (only open/close/stop commands via gate_state)
            # gate_position is read-only for current position display
            features |= CoverEntityFeature.STOP
        else:
            val_obj = self._find_value_obj(device_data, value_id)
            val_type = val_obj.get("type", "") if val_obj else ""
            if val_type in (VALUE_TYPE_MULTILEVEL, VALUE_TYPE_OPEN_CLOSE):
                features |= CoverEntityFeature.SET_POSITION
                features |= CoverEntityFeature.STOP
        self._attr_supported_features = features

        # Look for a stop value_id (non-LINK devices)
        self._stop_value_id: str | None = None
        if not self._is_link:
            for v in device_data.get("values", []):
                vid = v.get("value_id", "")
                if "stop" in vid.lower() or "pause" in vid.lower():
                    self._stop_value_id = vid
                    break

    # ── State ────────────────────────────────────────────────────────────

    @property
    def is_closed(self) -> bool | None:
        if self._is_link:
            return self._link_is_closed()
        # Standard covers: 0 = closed
        val = self._get_value()
        if val is None:
            return None
        try:
            return int(val) == 0
        except (ValueError, TypeError):
            return None

    @property
    def is_closing(self) -> bool | None:
        if self._is_link:
            state = self._get_gate_state()
            if state is not None:
                return state in GATE_STATE_CLOSING
        return None

    @property
    def is_opening(self) -> bool | None:
        if self._is_link:
            state = self._get_gate_state()
            if state is not None:
                return state in GATE_STATE_OPENING
        return None

    @property
    def current_cover_position(self) -> int | None:
        if self._is_link:
            return self._link_position()
        # Standard covers
        val_obj = self._get_value_obj()
        if not val_obj:
            return None
        try:
            val = int(val_obj.get("value", 0))
            v_min = int(val_obj.get("min", 0))
            v_max = int(val_obj.get("max", 100))
            if v_max == v_min:
                return 0
            return round((val - v_min) / (v_max - v_min) * 100)
        except (ValueError, TypeError):
            return None

    # ── LINK-specific state helpers ──────────────────────────────────────

    def _get_gate_state(self) -> int | None:
        """Get the gate_state value for LINK devices."""
        if not self._gate_state_vid:
            return None
        val = self._data.get_device_value(self._device_id, self._gate_state_vid)
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def _link_is_closed(self) -> bool | None:
        """Determine if a LINK gate is closed from gate_state."""
        state = self._get_gate_state()
        if state is None:
            pos = self._link_position()
            if pos is not None:
                return pos == 0
            return None
        if state in GATE_STATE_CLOSED:
            return True
        if state in GATE_STATE_IDLE:
            pos = self._link_position()
            if pos is not None:
                return pos == 0
            return True
        return False

    def _link_position(self) -> int | None:
        """Get the gate_position percentage for LINK devices (read-only)."""
        if not self._gate_position_vid:
            return None
        val_obj = self._data.get_device_value_obj(
            self._device_id, self._gate_position_vid
        )
        if not val_obj:
            return None
        try:
            val = int(val_obj.get("value", 0))
            v_min = int(val_obj.get("min", 0))
            v_max = int(val_obj.get("max", 100))
            if v_max == v_min:
                return 0
            return round((val - v_min) / (v_max - v_min) * 100)
        except (ValueError, TypeError):
            return None

    # ── Commands ─────────────────────────────────────────────────────────

    async def async_open_cover(self, **kwargs: Any) -> None:
        if self._is_link:
            # LINK: send FULL_OPEN command (2) to gate_state
            await self._send_value(self._gate_state_vid, LINK_CMD_FULL_OPEN)
        else:
            val_obj = self._get_value_obj()
            v_max = int(val_obj.get("max", 100)) if val_obj else 100
            await self._send_value(self._value_id, v_max)

    async def async_close_cover(self, **kwargs: Any) -> None:
        if self._is_link:
            # LINK: send CLOSE command (0) to gate_state
            await self._send_value(self._gate_state_vid, LINK_CMD_CLOSE)
        else:
            val_obj = self._get_value_obj()
            v_min = int(val_obj.get("min", 0)) if val_obj else 0
            await self._send_value(self._value_id, v_min)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        if self._is_link:
            # LINK: send STOP command (13) to gate_state
            await self._send_value(self._gate_state_vid, LINK_CMD_STOP)
        elif self._stop_value_id:
            await self._send_value(self._stop_value_id, 1)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        # Only for non-LINK covers
        if self._is_link:
            return
        position = kwargs.get("position", 0)
        val_obj = self._get_value_obj()
        if val_obj:
            v_min = int(val_obj.get("min", 0))
            v_max = int(val_obj.get("max", 100))
            actual = round(v_min + (position / 100) * (v_max - v_min))
            await self._send_value(self._value_id, actual)
        else:
            await self._send_value(self._value_id, position)
