"""Tests for the MCONNECT config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mconnect.api import (
    MConnectAuthError,
    MConnectApiError,
    MConnectTokenLimitError,
    MConnectTokenRevokedError,
)
from custom_components.mconnect.const import (
    AUTH_WEB_URL,
    CONF_HOME_ID,
    CONF_HOME_NAME,
    DOMAIN,
)

from .conftest import (
    MOCK_ACCESS_TOKEN,
    MOCK_AUTH_CODE,
    MOCK_ENTRY_DATA,
    MOCK_HOME_ID,
    MOCK_HOME_NAME,
    MOCK_REFRESH_TOKEN,
)


# ── Helper ───────────────────────────────────────────────────────────────


def _inject_auth_data(hass: HomeAssistant, flow_id: str) -> None:
    """Simulate webhook callback by injecting auth data into hass.data."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][f"auth_{flow_id}"] = {
        "code": MOCK_AUTH_CODE,
        "home_id": MOCK_HOME_ID,
        "home_name": MOCK_HOME_NAME,
    }


async def _init_and_advance_to_finish(
    hass: HomeAssistant,
) -> str:
    """Start flow, inject auth data, and advance to the finish step. Return flow_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow_id = result["flow_id"]

    _inject_auth_data(hass, flow_id)

    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

    return flow_id


# ── Test: full successful flow ───────────────────────────────────────────


async def test_full_flow_success(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test a complete successful config flow from user init to entry creation."""
    # Step 1: User starts flow → external step with auth URL
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"
    assert AUTH_WEB_URL in result["url"]

    flow_id = result["flow_id"]

    # Step 2: Simulate webhook callback storing auth data
    _inject_auth_data(hass, flow_id)

    # Step 3: Advance flow — auth step finds data → external_step_done
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

    # Step 4: Finish step exchanges code → creates config entry
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"MCONNECT - {MOCK_HOME_NAME}"
    assert result["data"][CONF_HOME_ID] == MOCK_HOME_ID
    assert result["data"][CONF_HOME_NAME] == MOCK_HOME_NAME
    assert result["data"]["access_token"] == MOCK_ACCESS_TOKEN
    assert result["data"]["refresh_token"] == MOCK_REFRESH_TOKEN

    mock_api.exchange_code.assert_called_once_with(MOCK_AUTH_CODE)

    # Clean up: remove the entry to prevent lingering threads at teardown
    with patch(
        "custom_components.mconnect.async_remove_entry",
        new_callable=AsyncMock,
    ):
        await hass.config_entries.async_remove(result["result"].entry_id)


# ── Test: auth URL contains required params ──────────────────────────────


async def test_auth_url_params(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the generated auth URL contains all required OAuth parameters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_url = result["url"]
    assert AUTH_WEB_URL in auth_url
    assert "platform=home-assistant" in auth_url
    assert "type=authorization" in auth_url
    assert "redirect_uri=" in auth_url
    assert f"state={result['flow_id']}" in auth_url


# ── Test: auth step waiting (no data yet) ────────────────────────────────


async def test_auth_step_waiting(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test auth step keeps polling when webhook hasn't fired yet."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    flow_id = result["flow_id"]

    # Don't inject auth data — user hasn't logged in yet
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"


# ── Test: token exchange auth error → abort ──────────────────────────────


async def test_finish_exchange_auth_error(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test finish step aborts when server returns auth error."""
    mock_api.exchange_code.side_effect = MConnectAuthError("invalid_grant")

    flow_id = await _init_and_advance_to_finish(hass)
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_failed"


# ── Test: token exchange API error → abort ───────────────────────────────


async def test_finish_exchange_api_error(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test finish step aborts when server returns API error."""
    mock_api.exchange_code.side_effect = MConnectApiError("Server error")

    flow_id = await _init_and_advance_to_finish(hass)
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


# ── Test: token limit reached → abort ────────────────────────────────────


async def test_finish_token_limit_reached(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test finish step aborts when max personal access tokens reached."""
    mock_api.exchange_code.side_effect = MConnectTokenLimitError("Max tokens")

    flow_id = await _init_and_advance_to_finish(hass)
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_limit_reached"


# ── Test: token revoked → abort ──────────────────────────────────────────


async def test_finish_token_revoked(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test finish step aborts when personal access token is revoked."""
    mock_api.exchange_code.side_effect = MConnectTokenRevokedError("Revoked")

    flow_id = await _init_and_advance_to_finish(hass)
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_revoked"


# ── Test: token exchange unexpected error → abort unknown ────────────────


async def test_finish_exchange_unexpected_error(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test finish step aborts with 'unknown' on unexpected exception."""
    mock_api.exchange_code.side_effect = RuntimeError("Connection reset")

    flow_id = await _init_and_advance_to_finish(hass)
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


# ── Test: duplicate home → abort already_configured ──────────────────────


async def test_already_configured(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test flow aborts and revokes token when home is already configured."""
    # Create existing entry with same unique_id
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="MCONNECT - Casa",
        data=MOCK_ENTRY_DATA,
        unique_id=MOCK_HOME_ID,
    )
    existing.add_to_hass(hass)

    # Add revoke_token mock
    mock_api.revoke_token = AsyncMock(return_value=True)

    # Start new flow for the same home
    flow_id = await _init_and_advance_to_finish(hass)
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the newly created token was revoked
    mock_api.revoke_token.assert_called_once()


# ── Test: reauth flow success ────────────────────────────────────────────


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test re-authentication updates existing entry instead of creating new."""
    # Create existing entry
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="MCONNECT - Casa",
        data=MOCK_ENTRY_DATA,
        unique_id=MOCK_HOME_ID,
    )
    existing.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing.entry_id,
        },
        data=MOCK_ENTRY_DATA,
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"

    flow_id = result["flow_id"]

    # Simulate webhook callback
    _inject_auth_data(hass, flow_id)

    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)
    assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Verify existing entry was updated with new tokens
    assert existing.data["access_token"] == MOCK_ACCESS_TOKEN
    assert existing.data["refresh_token"] == MOCK_REFRESH_TOKEN


# ── Test: webhook handler success ────────────────────────────────────────


async def test_webhook_handler_success(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test webhook handler stores auth data and returns OK HTML."""
    from custom_components.mconnect.config_flow import _webhook_handler, OK_HTML

    # Start a flow to get a valid flow_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow_id = result["flow_id"]

    # Create a mock aiohttp request
    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.query = {
        "state": flow_id,
        "code": MOCK_AUTH_CODE,
        "home_id": MOCK_HOME_ID,
        "home_name": MOCK_HOME_NAME,
    }

    response = await _webhook_handler(hass, "test_webhook_id", mock_request)

    # Webhook should return success HTML
    assert OK_HTML in response.text

    # The webhook calls async_configure internally, which advances the flow
    # and consumes the auth data. Verify the flow was advanced to finish step
    # by calling configure again — it should proceed to create entry.
    result = await hass.config_entries.flow.async_configure(flow_id=flow_id)
    assert result["type"] is FlowResultType.CREATE_ENTRY


# ── Test: webhook handler missing state → fail ──────────────────────────


async def test_webhook_handler_missing_state(hass: HomeAssistant) -> None:
    """Test webhook handler returns error when state is missing."""
    from custom_components.mconnect.config_flow import _webhook_handler, FAIL_HTML

    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.query = {"code": MOCK_AUTH_CODE}  # Missing state

    response = await _webhook_handler(hass, "test_webhook_id", mock_request)

    assert FAIL_HTML in response.text


# ── Test: webhook handler missing code → fail ───────────────────────────


async def test_webhook_handler_missing_code(hass: HomeAssistant) -> None:
    """Test webhook handler returns error when code is missing."""
    from custom_components.mconnect.config_flow import _webhook_handler, FAIL_HTML

    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.query = {"state": "some_flow_id"}  # Missing code

    response = await _webhook_handler(hass, "test_webhook_id", mock_request)

    assert FAIL_HTML in response.text


# ── Test: webhook handler empty params → fail ───────────────────────────


async def test_webhook_handler_no_params(hass: HomeAssistant) -> None:
    """Test webhook handler returns error when no params provided."""
    from custom_components.mconnect.config_flow import _webhook_handler, FAIL_HTML

    mock_request = AsyncMock()
    mock_request.method = "GET"
    mock_request.query = {}

    response = await _webhook_handler(hass, "test_webhook_id", mock_request)

    assert FAIL_HTML in response.text
