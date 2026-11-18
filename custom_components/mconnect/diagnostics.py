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

    mqtt = runtime_data.mqtt
    mqtt_diag = {
        "enabled": mqtt is not None,
        "connected": mqtt.connected if mqtt else False,
        "client_id": _mask_client_id(mqtt.client_id) if mqtt else None,
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
            "mqtt": mqtt_diag,
        },
        TO_REDACT,
    )


def _mask_client_id(client_id: str) -> str:
    """Hide the home id part of the client id, keep the instance part.

    Format: ha-mc-<home_id[:8]>-<instance_id[:8]>
    """
    parts = client_id.split("-")
    if len(parts) == 4:
        parts[2] = "*" * len(parts[2])
    return "-".join(parts)
