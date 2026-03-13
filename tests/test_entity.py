"""Tests for the MCONNECT base entity."""

from __future__ import annotations

from custom_components.mconnect.entity import resolve_icon
from custom_components.mconnect.const import ICON_MAP, DEVICE_TYPE_ICON


# ── resolve_icon ─────────────────────────────────────────────────────────


def test_resolve_icon_from_map():
    """Test icon resolution from ICON_MAP."""
    assert resolve_icon("garage") == "mdi:garage"
    assert resolve_icon("night") == "mdi:weather-night"
    assert resolve_icon("bulb-on") == "mdi:lightbulb-on"


def test_resolve_icon_fallback_to_device_type():
    """Test icon falls back to device type when icon name not in map."""
    result = resolve_icon("unknown_icon_name", "devices.types.GARAGE")
    assert result == DEVICE_TYPE_ICON.get("devices.types.GARAGE")


def test_resolve_icon_none():
    """Test icon returns None when no match."""
    result = resolve_icon(None, None)
    assert result is None


def test_resolve_icon_empty_string():
    """Test icon with empty string."""
    result = resolve_icon("", None)
    assert result is None or result == ICON_MAP.get("")


def test_icon_map_completeness():
    """Test ICON_MAP has many entries."""
    assert len(ICON_MAP) > 200  # We added 244 icons


def test_device_type_icon_map():
    """Test all device types have icons."""
    for dtype in ["devices.types.LIGHT", "devices.types.GARAGE",
                  "devices.types.LOCK", "devices.types.SENSOR"]:
        assert dtype in DEVICE_TYPE_ICON
