"""Tests for MCONNECT diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mconnect.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)
from custom_components.mconnect.coordinator import MConnectData

from .conftest import MOCK_DEVICES, MOCK_ENTRY_DATA, MOCK_HOME_ID, MOCK_SCENES


async def test_diagnostics_redacts_sensitive_data(hass):
    """Test diagnostics redacts tokens and personal info."""
    # Build mock coordinator data
    data = MConnectData()
    for d in MOCK_DEVICES:
        did = d.get("_id") or d.get("id")
        data.devices[str(did)] = d
    for s in MOCK_SCENES:
        sid = s.get("_id") or s.get("id")
        data.scenes[str(sid)] = s

    mock_coord = MagicMock()
    mock_coord.data = data
    mock_coord.last_update_success = True

    mock_runtime = MagicMock()
    mock_runtime.coordinator = mock_coord
    mock_runtime.mqtt = MagicMock()

    mock_entry = MagicMock()
    mock_entry.title = "MCONNECT - Casa"
    mock_entry.data = MOCK_ENTRY_DATA
    mock_entry.version = 1
    mock_entry.runtime_data = mock_runtime

    result = await async_get_config_entry_diagnostics(hass, mock_entry)

    # Check structure exists
    assert "entry" in result
    assert "coordinator" in result
    assert "devices" in result
    assert "scenes" in result

    # Check sensitive data is redacted
    assert result["entry"]["data"]["access_token"] == "**REDACTED**"
    assert result["entry"]["data"]["refresh_token"] == "**REDACTED**"

    # Check device count
    assert result["coordinator"]["device_count"] == len(MOCK_DEVICES)
    assert result["coordinator"]["scene_count"] == len(MOCK_SCENES)


async def test_to_redact_fields():
    """Test all sensitive fields are in TO_REDACT."""
    assert "access_token" in TO_REDACT
    assert "refresh_token" in TO_REDACT
    assert "token_expiry" in TO_REDACT
    assert "email" in TO_REDACT
