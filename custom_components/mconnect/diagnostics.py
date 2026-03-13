"""Diagnostics support for MCONNECT."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "access_token",
    "refresh_token",
    "token_expiry",
    "home_id",
    "home_name",
    "key",
    "email",
    "_id",
    "endpoint_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator

    devices_diag = {}
    for device_id, device in coordinator.data.devices.items():
        devices_diag[device_id] = {
            "name": device.get("name"),
            "type": device.get("type"),
            "icon": device.get("icon"),
            "endpoint_status": (device.get("endpoint") or {}).get("status"),
            "values": [
                {
                    "value_id": v.get("value_id"),
                    "type": v.get("type"),
                    "value": v.get("value"),
                }
                for v in device.get("values", [])
            ],
        }

    scenes_diag = {}
    for scene_id, scene in coordinator.data.scenes.items():
        scenes_diag[scene_id] = {
            "name": scene.get("name"),
            "icon": scene.get("icon"),
        }

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "data": dict(entry.data),
                "version": entry.version,
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "device_count": len(coordinator.data.devices),
                "scene_count": len(coordinator.data.scenes),
            },
            "devices": devices_diag,
            "scenes": scenes_diag,
            "mqtt_connected": runtime_data.mqtt is not None,
        },
        TO_REDACT,
    )
