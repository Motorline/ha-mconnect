"""Tests for the MCONNECT API client."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mconnect.api import (
    MConnectApi,
    MConnectAuthError,
    MConnectApiError,
)


class MockResponse:
    """Mock aiohttp response that works as async context manager."""

    def __init__(self, status=200, json_data=None, text_data="", content_type="application/json"):
        self.status = status
        self._json = json_data or {}
        self._text = text_data
        self.content_type = content_type

    async def json(self):
        return self._json

    async def text(self):
        if self._text:
            return self._text
        # Return serialized JSON so json.loads() works in the code under test
        import json
        return json.dumps(self._json)

    def raise_for_status(self):
        if self.status >= 400:
            from aiohttp import ClientResponseError
            raise ClientResponseError(
                request_info=MagicMock(), history=(), status=self.status
            )


class MockContextManager:
    """Wraps a MockResponse to work with `async with session.post(...) as resp:`."""

    def __init__(self, response: MockResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session where .post/.request return context managers."""
    session = MagicMock()
    return session


def _set_response(session, resp: MockResponse, method="post"):
    """Configure session method to return a context manager."""
    getattr(session, method).return_value = MockContextManager(resp)


def _set_responses(session, responses: list[MockResponse], method="request"):
    """Configure session method to return multiple context managers in sequence."""
    cms = [MockContextManager(r) for r in responses]
    getattr(session, method).side_effect = cms


@pytest.fixture
def api(mock_session):
    """Create an MConnectApi instance with mock session."""
    return MConnectApi(mock_session, base_url="https://test.api.com")


# ── exchange_code ────────────────────────────────────────────────────────


async def test_exchange_code_success(api, mock_session):
    """Test successful code exchange."""
    _set_response(mock_session, MockResponse(200, {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_in": 3600,
        "home_id": "home123",
    }))

    data = await api.exchange_code("auth_code")

    assert api.access_token == "new_access"
    assert api.refresh_token == "new_refresh"
    assert api.home_id == "home123"


async def test_exchange_code_400_error(api, mock_session):
    """Test code exchange with 400 error."""
    _set_response(mock_session, MockResponse(400, {"error": "invalid_grant"}))

    with pytest.raises(MConnectAuthError, match="invalid_grant"):
        await api.exchange_code("bad_code")


async def test_exchange_code_500_error(api, mock_session):
    """Test code exchange with server error."""
    _set_response(mock_session, MockResponse(500))

    with pytest.raises(MConnectApiError):
        await api.exchange_code("some_code")


async def test_exchange_code_403_token_limit(api, mock_session):
    """Test code exchange with max tokens reached."""
    from custom_components.mconnect.api import MConnectTokenLimitError

    _set_response(mock_session, MockResponse(403, {
        "code": "MaxPersonalAccessTokensError",
        "message": "Maximum of 5 active personal access tokens reached",
    }))

    with pytest.raises(MConnectTokenLimitError):
        await api.exchange_code("some_code")


async def test_exchange_code_401_unauthorized(api, mock_session):
    """Test code exchange with 401 unauthorized."""
    _set_response(mock_session, MockResponse(401))

    with pytest.raises(MConnectAuthError, match="Unauthorized"):
        await api.exchange_code("some_code")


async def test_refresh_404_token_revoked(api, mock_session):
    """Test refresh with revoked personal access token."""
    from custom_components.mconnect.api import MConnectTokenRevokedError

    api.refresh_token = "some_token"
    _set_response(mock_session, MockResponse(404, {
        "code": "TokenRevokedError",
    }))

    with pytest.raises(MConnectTokenRevokedError):
        await api.refresh_access_token()


async def test_refresh_403_forbidden(api, mock_session):
    """Test refresh with 403 forbidden."""
    api.refresh_token = "some_token"
    _set_response(mock_session, MockResponse(403, {
        "message": "Account suspended",
    }))

    with pytest.raises(MConnectAuthError, match="Account suspended"):
        await api.refresh_access_token()


# ── refresh_access_token ─────────────────────────────────────────────────


async def test_refresh_success(api, mock_session):
    """Test successful token refresh."""
    api.refresh_token = "old_refresh"
    _set_response(mock_session, MockResponse(200, {
        "access_token": "refreshed_access",
        "expires_in": 3600,
    }))

    await api.refresh_access_token()
    assert api.access_token == "refreshed_access"


async def test_refresh_no_token(api):
    """Test refresh fails without refresh token."""
    api.refresh_token = None
    with pytest.raises(MConnectAuthError, match="No refresh token"):
        await api.refresh_access_token()


async def test_refresh_server_error(api, mock_session):
    """Test refresh fails on non-200 response."""
    api.refresh_token = "some_token"
    _set_response(mock_session, MockResponse(401, text_data="Unauthorized"))

    with pytest.raises(MConnectAuthError, match="Refresh failed"):
        await api.refresh_access_token()


async def test_refresh_rotates_token(api, mock_session):
    """Test refresh updates refresh_token when server returns new one."""
    api.refresh_token = "old_refresh"
    _set_response(mock_session, MockResponse(200, {
        "access_token": "new_access",
        "refresh_token": "rotated_refresh",
        "expires_in": 3600,
    }))

    await api.refresh_access_token()
    assert api.refresh_token == "rotated_refresh"


async def test_refresh_network_error(api, mock_session):
    """Test refresh propagates network exceptions."""
    api.refresh_token = "some_token"
    mock_session.post.side_effect = Exception("Connection reset")

    with pytest.raises(Exception, match="Connection reset"):
        await api.refresh_access_token()


# ── ensure_valid_token ───────────────────────────────────────────────────


async def test_ensure_valid_token_still_valid(api):
    """Test ensure_valid_token skips refresh when token is still valid."""
    api.access_token = "valid_token"
    api.token_expiry = time.time() + 3600

    with patch.object(api, "refresh_access_token") as mock_refresh:
        await api.ensure_valid_token()
        mock_refresh.assert_not_called()


async def test_ensure_valid_token_expired(api, mock_session):
    """Test ensure_valid_token refreshes when token is about to expire."""
    api.access_token = "expired_token"
    api.refresh_token = "some_refresh"
    api.token_expiry = time.time() - 10

    _set_response(mock_session, MockResponse(200, {
        "access_token": "new_token",
        "expires_in": 3600,
    }))

    await api.ensure_valid_token()
    assert api.access_token == "new_token"


# ── _request ─────────────────────────────────────────────────────────────


async def test_request_success(api, mock_session):
    """Test successful authenticated request."""
    api.access_token = "valid"
    api.token_expiry = time.time() + 3600

    _set_response(mock_session, MockResponse(200, {"data": "test"}), "request")

    result = await api._request("GET", "/test")
    assert result == {"data": "test"}


async def test_request_401_retry(api, mock_session):
    """Test request retries on 401."""
    api.access_token = "expired"
    api.refresh_token = "valid_refresh"
    api.token_expiry = time.time() + 3600

    _set_responses(mock_session, [
        MockResponse(401),
        MockResponse(200, {"result": "ok"}),
    ], "request")

    _set_response(mock_session, MockResponse(200, {
        "access_token": "new_access",
        "expires_in": 3600,
    }))

    result = await api._request("GET", "/test")
    assert result == {"result": "ok"}


# ── get_devices / get_scenes / send_value / execute_scene ────────────────


async def test_get_devices_list(api, mock_session):
    """Test get_devices with list response."""
    api.access_token = "valid"
    api.token_expiry = time.time() + 3600

    _set_response(mock_session, MockResponse(200, [{"_id": "d1"}, {"_id": "d2"}]), "request")
    result = await api.get_devices()
    assert len(result) == 2


async def test_get_scenes_list(api, mock_session):
    """Test get_scenes with list response."""
    api.access_token = "valid"
    api.token_expiry = time.time() + 3600

    _set_response(mock_session, MockResponse(200, [{"_id": "s1"}]), "request")
    result = await api.get_scenes()
    assert len(result) == 1


async def test_send_value(api, mock_session):
    """Test send_value makes correct request."""
    api.access_token = "valid"
    api.token_expiry = time.time() + 3600

    _set_response(mock_session, MockResponse(200, {}), "request")
    await api.send_value("device1", "on_off", 1)
    mock_session.request.assert_called()


async def test_execute_scene(api, mock_session):
    """Test execute_scene makes correct request."""
    api.access_token = "valid"
    api.token_expiry = time.time() + 3600

    _set_response(mock_session, MockResponse(200, {}), "request")
    await api.execute_scene("scene1")
    mock_session.request.assert_called()


# ── export/import tokens ─────────────────────────────────────────────────


async def test_export_import_tokens(api):
    """Test token export and import roundtrip."""
    api.access_token = "at"
    api.refresh_token = "rt"
    api.token_expiry = 12345.0

    exported = api.export_tokens()
    assert exported["access_token"] == "at"

    api2 = MConnectApi(MagicMock())
    api2.import_tokens(exported)
    assert api2.access_token == "at"
    assert api2.refresh_token == "rt"


# ── revoke_token ─────────────────────────────────────────────────────────


async def test_revoke_token_success(api, mock_session):
    """Test successful token revocation."""
    _set_response(mock_session, MockResponse(200, {"revoked": True}), "request")

    api.refresh_token = "token_to_revoke"
    result = await api.revoke_token()
    assert result is True


async def test_revoke_token_specific(api, mock_session):
    """Test revoking a specific token."""
    _set_response(mock_session, MockResponse(200, {"revoked": True}), "request")

    result = await api.revoke_token("old_refresh_token")
    assert result is True
    mock_session.request.assert_called()


async def test_revoke_token_no_token(api):
    """Test revoke with no token returns False."""
    api.refresh_token = None
    result = await api.revoke_token()
    assert result is False


async def test_revoke_token_server_error(api, mock_session):
    """Test revoke handles server errors gracefully."""
    _set_response(mock_session, MockResponse(500), "request")

    api.refresh_token = "some_token"
    result = await api.revoke_token()
    assert result is False


async def test_revoke_token_network_error(api, mock_session):
    """Test revoke handles network errors gracefully."""
    mock_session.request.side_effect = Exception("Connection refused")

    api.refresh_token = "some_token"
    result = await api.revoke_token()
    assert result is False
