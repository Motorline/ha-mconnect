"""Base entity for the Motorline MCONNECT integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MConnectAccessError
from .const import DEVICE_TYPE_ICON, DOMAIN, ICON_MAP, MANUFACTURER
from .coordinator import MConnectCoordinator, MConnectData

_LOGGER = logging.getLogger(__name__)


def resolve_icon(icon_name: str | None, device_type: str | None = None) -> str | None:
    """Resolve an MCONNECT icon name to an mdi: icon string."""
    if icon_name:
        name = str(icon_name).strip().lower()
        # Direct match
        if name in ICON_MAP:
            return ICON_MAP[name]
        # Already an mdi: icon
        if name.startswith("mdi:"):
            return name
        # Partial match: check if any key is contained in the icon name
        for key, mdi in ICON_MAP.items():
            if key in name:
                return mdi
    # Fallback to device type
    if device_type and device_type in DEVICE_TYPE_ICON:
        return DEVICE_TYPE_ICON[device_type]
    return None


class MConnectEntity(CoordinatorEntity[MConnectCoordinator]):
    """Base class for MCONNECT entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MConnectCoordinator,
        device_data: dict[str, Any],
        value_id: str | None = None,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)

        self._device_id: str = str(device_data.get("_id") or device_data.get("id"))
        self._value_id: str | None = value_id
        self._device_data = device_data

        # Build unique ID
        if value_id:
            self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{value_id}"
        else:
            self._attr_unique_id = f"{DOMAIN}_{self._device_id}"

        # Entity name
        if value_id:
            val_obj = self._find_value_obj(device_data, value_id)
            val_name = val_obj.get("name") if val_obj else None
            val_type = val_obj.get("type", "") if val_obj else ""

            # Use translation keys for known value types (Gold: entity-translations)
            translation_map = {
                "values.types.OnOff": "on_off",
                "values.types.OpenClose": "open_close",
                "values.types.Brightness": "brightness",
                "values.types.LockUnlock": "lock_unlock",
                "values.types.Multilevel": "level",
                "values.types.Binary": "state",
                "values.types.Modes": "mode",
            }
            tkey = translation_map.get(val_type)
            if tkey:
                self._attr_translation_key = tkey

            if val_name:
                self._attr_name = val_name
            elif not tkey:
                self._attr_name = value_id.replace("_", " ").replace(".", " ").title()
        else:
            self._attr_name = None  # Use device name via has_entity_name

        # Icon: resolve from the MCONNECT icon field
        device_icon = device_data.get("icon")
        device_type = device_data.get("type")
        resolved = resolve_icon(device_icon, device_type)
        if resolved:
            self._attr_icon = resolved

        # Entity category: configuration or diagnostic values (Gold: entity-category)
        if value_id:
            val_obj = self._find_value_obj(device_data, value_id)
            if val_obj:
                if val_obj.get("configuration"):
                    self._attr_entity_category = EntityCategory.CONFIG
                    self._attr_entity_registry_enabled_default = False
                elif val_obj.get("query_only"):
                    self._attr_entity_category = EntityCategory.DIAGNOSTIC

    # ── Device info ──────────────────────────────────────────────────────

    @property
    def device_info(self) -> DeviceInfo:
        endpoint = self._device_data.get("endpoint") or {}
        product = endpoint.get("info", {}).get("product") or {}

        identifiers = {(DOMAIN, self._device_id)}
        endpoint_id = self._device_data.get("endpoint_id")
        if endpoint_id:
            identifiers.add((DOMAIN, f"endpoint_{endpoint_id}"))

        room = self._device_data.get("room") or {}
        suggested_area = room.get("name")

        return DeviceInfo(
            identifiers=identifiers,
            name=self._device_data.get("name") or "MCONNECT Device",
            manufacturer=product.get("manufacturer", MANUFACTURER),
            model=product.get("model") or product.get("name"),
            sw_version=product.get("software_version")
            or endpoint.get("info", {}).get("software_version"),
            hw_version=product.get("hardware_version"),
            suggested_area=suggested_area,
            via_device=(DOMAIN, f"endpoint_{endpoint_id}") if endpoint_id else None,
        )

    # ── Data access helpers ──────────────────────────────────────────────

    @property
    def _data(self) -> MConnectData:
        return self.coordinator.data

    @property
    def _current_device(self) -> dict[str, Any] | None:
        return self._data.devices.get(self._device_id)

    def _get_value(self, value_id: str | None = None) -> Any:
        vid = value_id or self._value_id
        if not vid:
            return None
        return self._data.get_device_value(self._device_id, vid)

    def _get_value_obj(self, value_id: str | None = None) -> dict[str, Any] | None:
        vid = value_id or self._value_id
        if not vid:
            return None
        return self._data.get_device_value_obj(self._device_id, vid)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        device = self._current_device
        if not device:
            return False
        endpoint = device.get("endpoint") or {}
        status = endpoint.get("status", 0)
        return status == 1

    # ── Command helper ───────────────────────────────────────────────────

    async def _send_value(self, value_id: str, value: Any) -> None:
        try:
            await self.coordinator.api.send_value(self._device_id, value_id, value)
        except MConnectAccessError as err:
            _LOGGER.warning(
                "Access denied for device %s: %s", self._device_id, err,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="access_denied",
            ) from err
        except Exception:
            _LOGGER.exception(
                "Failed to send value %s=%s to device %s",
                value_id, value, self._device_id,
            )
            raise

    # ── Static helpers ───────────────────────────────────────────────────

    @staticmethod
    def _find_value_obj(device_data: dict[str, Any], value_id: str) -> dict[str, Any] | None:
        for v in device_data.get("values", []):
            if v.get("value_id") == value_id:
                return v
        return None
