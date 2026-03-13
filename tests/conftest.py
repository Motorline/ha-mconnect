"""Fixtures for MCONNECT tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mconnect.const import CONF_HOME_ID, CONF_HOME_NAME, DOMAIN

# ── Mock data ────────────────────────────────────────────────────────────

MOCK_HOME_ID = "629abc123def456789abcdef"
MOCK_HOME_NAME = "Casa"
MOCK_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.mock_access"
MOCK_REFRESH_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.mock_refresh"
MOCK_AUTH_CODE = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.mock_code"

MOCK_ENTRY_DATA = {
    CONF_HOME_ID: MOCK_HOME_ID,
    CONF_HOME_NAME: MOCK_HOME_NAME,
    "access_token": MOCK_ACCESS_TOKEN,
    "refresh_token": MOCK_REFRESH_TOKEN,
    "token_expiry": 9999999999.0,
}

MOCK_EXCHANGE_RESPONSE = {
    "token_type": "Bearer",
    "access_token": MOCK_ACCESS_TOKEN,
    "refresh_token": MOCK_REFRESH_TOKEN,
    "expires_in": 3600,
    "home_id": MOCK_HOME_ID,
    "home_name": MOCK_HOME_NAME,
}

MOCK_DEVICES = [
    {
        "_id": "device001",
        "name": "Portão Garagem",
        "type": "devices.types.GARAGE",
        "icon": "garage",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "open_close",
                "type": "values.types.OpenClose",
                "value": 0,
                "min": 0,
                "max": 100,
            }
        ],
    },
    {
        "_id": "device002",
        "name": "Luz Sala",
        "type": "devices.types.LIGHT",
        "icon": "bulb",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "on_off",
                "type": "values.types.OnOff",
                "value": 1,
            },
            {
                "value_id": "brightness",
                "type": "values.types.Brightness",
                "value": 75,
                "min": 0,
                "max": 100,
            },
        ],
    },
    {
        "_id": "device003",
        "name": "Tomada Cozinha",
        "type": "devices.types.PLUG",
        "icon": "plug",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "on_off",
                "type": "values.types.OnOff",
                "value": 0,
            }
        ],
    },
    {
        "_id": "device004",
        "name": "Sensor Temp",
        "type": "devices.types.SENSOR",
        "icon": "thermometer",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "temperature",
                "type": "values.types.Multilevel",
                "value": 22.5,
                "unit": "°C",
                "query_only": True,
            }
        ],
    },
    {
        "_id": "device005",
        "name": "Sensor Movimento",
        "type": "devices.types.MOTION_SENSOR",
        "icon": "motion",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "motion",
                "type": "values.types.Binary",
                "value": 0,
            }
        ],
    },
    {
        "_id": "device006",
        "name": "Fechadura",
        "type": "devices.types.LOCK",
        "icon": "lock",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "lock_unlock",
                "type": "values.types.LockUnlock",
                "value": 1,
            }
        ],
    },
    {
        "_id": "device007",
        "name": "Portão LINK",
        "type": "devices.types.LINK",
        "icon": "gate",
        "endpoint": {"status": "online"},
        "values": [
            {
                "value_id": "gate_state",
                "type": "values.types.Multilevel",
                "value": 0,
                "min": 0,
                "max": 14,
                "query_only": True,
            },
            {
                "value_id": "gate_position",
                "type": "values.types.OpenClose",
                "value": 0,
                "min": 0,
                "max": 100,
            },
        ],
    },
]

MOCK_SCENES = [
    {
        "_id": "scene001",
        "name": "Boa Noite",
        "icon": "night",
        "home_id": MOCK_HOME_ID,
    },
    {
        "_id": "scene002",
        "name": "Sair de Casa",
        "icon": "away",
        "home_id": MOCK_HOME_ID,
    },
]


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable custom integrations for all tests."""
    return


@pytest.fixture(autouse=True)
async def setup_ha_config(hass: HomeAssistant) -> None:
    """Configure HA with an internal URL so get_url() works in tests."""
    hass.config.internal_url = "http://192.168.1.100:8123"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MCONNECT - Casa",
        data=MOCK_ENTRY_DATA,
        unique_id=MOCK_HOME_ID,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Mock MConnectApi for config_flow tests."""
    with patch(
        "custom_components.mconnect.config_flow.MConnectApi",
        autospec=True,
    ) as mock_cls:
        api = mock_cls.return_value
        api.exchange_code = AsyncMock(return_value=MOCK_EXCHANGE_RESPONSE)
        api.access_token = MOCK_ACCESS_TOKEN
        api.refresh_token = MOCK_REFRESH_TOKEN
        api.token_expiry = 9999999999.0
        api.home_id = MOCK_HOME_ID
        api.export_tokens.return_value = {
            "access_token": MOCK_ACCESS_TOKEN,
            "refresh_token": MOCK_REFRESH_TOKEN,
            "token_expiry": 9999999999.0,
        }
        api.revoke_token = AsyncMock(return_value=True)
        api.import_tokens = MagicMock()
        yield api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry to avoid full platform setup during flow tests."""
    with patch(
        "custom_components.mconnect.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_api_instance() -> AsyncMock:
    """Create a standalone mock API instance for non-flow tests."""
    api = AsyncMock()
    api.access_token = MOCK_ACCESS_TOKEN
    api.refresh_token = MOCK_REFRESH_TOKEN
    api.token_expiry = 9999999999.0
    api.home_id = MOCK_HOME_ID
    api.ensure_valid_token = AsyncMock()
    api.get_devices = AsyncMock(return_value=MOCK_DEVICES)
    api.get_scenes = AsyncMock(return_value=MOCK_SCENES)
    api.send_value = AsyncMock()
    api.execute_scene = AsyncMock()
    api.refresh_access_token = AsyncMock()
    api.import_tokens = MagicMock()
    api.export_tokens = MagicMock(return_value={
        "access_token": MOCK_ACCESS_TOKEN,
        "refresh_token": MOCK_REFRESH_TOKEN,
        "token_expiry": 9999999999.0,
    })
    return api
