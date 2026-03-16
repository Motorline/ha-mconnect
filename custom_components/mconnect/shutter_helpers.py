"""Shared helpers for SHUTTER device mode handling."""

from __future__ import annotations

from typing import Any

from .const import SHUTTER_MODE_SHUTTER


def get_shutter_mode(device: dict[str, Any]) -> int:
    """Get the mode value for a SHUTTER device. Default 0 (normal shutter)."""
    for v in device.get("values", []):
        if v.get("value_id") == "mode":
            try:
                return int(v.get("value", SHUTTER_MODE_SHUTTER))
            except (ValueError, TypeError):
                return SHUTTER_MODE_SHUTTER
    return SHUTTER_MODE_SHUTTER


def get_shutter_show_mode(device: dict[str, Any]) -> dict[str, bool]:
    """Get show_mode visibility flags.

    Returns a dict like {"relay_01": True, "relay_02": False, "input_01": True, ...}.
    Missing keys default to True (visible).
    """
    for v in device.get("values", []):
        if v.get("value_id") == "show_mode":
            raw = v.get("value")
            if isinstance(raw, list):
                result: dict[str, bool] = {}
                for item in raw:
                    if isinstance(item, dict):
                        result[item.get("id", "")] = item.get("v", True)
                return result
    return {}


def get_shutter_labels(device: dict[str, Any]) -> dict[str, str]:
    """Get custom labels for relays and inputs.

    Returns a dict like {"relay_01": "Lâmpada", "input_01": "Sensor Porta"}.
    Only non-empty labels are included.
    """
    for v in device.get("values", []):
        if v.get("value_id") == "labels":
            raw = v.get("value")
            if isinstance(raw, list):
                result: dict[str, str] = {}
                for item in raw:
                    if isinstance(item, dict):
                        label = item.get("v", "")
                        if label:
                            result[item.get("id", "")] = label
                return result
    return {}
