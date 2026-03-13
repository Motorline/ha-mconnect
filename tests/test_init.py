"""Tests for MCONNECT integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mconnect.api import MConnectAuthError, MConnectApiError
from custom_components.mconnect.const import DOMAIN

from .conftest import MOCK_ENTRY_DATA, MOCK_HOME_ID, MOCK_DEVICES, MOCK_SCENES


def _make_mock_api(devices=None, scenes=None):
    """Create a mock API for init tests."""
    api = MagicMock()
    api.access_token = "token"
    api.refresh_token = "refresh"
    api.token_expiry = 9999999999.0
    api.home_id = MOCK_HOME_ID
    api.import_tokens = MagicMock()
    api.ensure_valid_token = AsyncMock()
    api.get_devices = AsyncMock(return_value=devices or MOCK_DEVICES)
    api.get_scenes = AsyncMock(return_value=scenes or MOCK_SCENES)
    api.export_tokens = MagicMock(return_value={
        "access_token": "token",
        "refresh_token": "refresh",
        "token_expiry": 9999999999.0,
    })
    return api


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry for init tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MCONNECT - Casa",
        data=MOCK_ENTRY_DATA,
        unique_id=MOCK_HOME_ID,
    )
    entry.add_to_hass(hass)
    return entry


# ── Setup entry ──────────────────────────────────────────────────────────


async def test_setup_entry_success(hass: HomeAssistant, mock_config_entry):
    """Test successful integration setup."""
    mock_api = _make_mock_api()

    with (
        patch("custom_components.mconnect.MConnectApi", return_value=mock_api),
        patch("custom_components.mconnect.MConnectMqttListener") as mock_mqtt_cls,
        patch("custom_components.mconnect.MConnectCoordinator") as mock_coord_cls,
    ):
        mock_coord = AsyncMock()
        mock_coord.async_add_listener = MagicMock(return_value=lambda: None)
        mock_coord_cls.return_value = mock_coord

        with patch.object(hass.config_entries, "async_forward_entry_setups"):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failed(hass: HomeAssistant, mock_config_entry):
    """Test setup marks entry as SETUP_ERROR on auth failure."""
    mock_api = _make_mock_api()
    mock_api.ensure_valid_token = AsyncMock(
        side_effect=MConnectAuthError("Token expired")
    )

    with patch("custom_components.mconnect.MConnectApi", return_value=mock_api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # HA catches ConfigEntryAuthFailed and sets state accordingly
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect(hass: HomeAssistant, mock_config_entry):
    """Test setup marks entry as SETUP_RETRY on connection error."""
    mock_api = _make_mock_api()
    mock_api.ensure_valid_token = AsyncMock()
    mock_api.get_devices = AsyncMock(side_effect=MConnectApiError("Timeout"))

    with patch("custom_components.mconnect.MConnectApi", return_value=mock_api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # HA catches ConfigEntryNotReady and schedules retry
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


# ── Unload entry ─────────────────────────────────────────────────────────


async def test_unload_entry(hass: HomeAssistant, mock_config_entry):
    """Test integration unload."""
    mock_api = _make_mock_api()

    with (
        patch("custom_components.mconnect.MConnectApi", return_value=mock_api),
        patch("custom_components.mconnect.MConnectMqttListener"),
        patch("custom_components.mconnect.MConnectCoordinator") as mock_coord_cls,
    ):
        mock_coord = AsyncMock()
        mock_coord.async_add_listener = MagicMock(return_value=lambda: None)
        mock_coord_cls.return_value = mock_coord

        with patch.object(hass.config_entries, "async_forward_entry_setups"):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert result is True


# ── Remove entry (revoke token) ─────────────────────────────────────────


async def test_remove_entry_revokes_token(hass: HomeAssistant, mock_config_entry):
    """Test removing integration revokes the personal access token."""
    from custom_components.mconnect import async_remove_entry

    mock_api = _make_mock_api()
    mock_api.revoke_token = AsyncMock(return_value=True)

    with patch("custom_components.mconnect.MConnectApi", return_value=mock_api):
        await async_remove_entry(hass, mock_config_entry)

    mock_api.revoke_token.assert_called_once()


async def test_remove_entry_no_refresh_token(hass: HomeAssistant):
    """Test removing integration without refresh token skips revocation."""
    from custom_components.mconnect import async_remove_entry

    entry_data = {**MOCK_ENTRY_DATA}
    del entry_data["refresh_token"]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="MCONNECT - Casa",
        data=entry_data,
        unique_id=MOCK_HOME_ID,
    )
    entry.add_to_hass(hass)

    mock_api = _make_mock_api()
    mock_api.refresh_token = None
    mock_api.revoke_token = AsyncMock(return_value=False)

    with patch("custom_components.mconnect.MConnectApi", return_value=mock_api):
        await async_remove_entry(hass, entry)

    mock_api.revoke_token.assert_not_called()
