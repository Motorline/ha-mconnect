"""Motorline MCONNECT REST API client.

Auth via server-signed JWT tokens. No client_secret needed.
The short-lived auth code (JWT with platform flag) is exchanged
for long-lived access + refresh tokens at /home-assistant/token.
"""
from __future__ import annotations
import logging, time
from typing import Any
import aiohttp
from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class MConnectAuthError(Exception):
    """Authentication error (401, invalid credentials)."""
    pass


class MConnectApiError(Exception):
    """Generic API error (500, network issues)."""
    pass


class MConnectTokenLimitError(MConnectAuthError):
    """Maximum personal access tokens reached (403)."""
    pass


class MConnectTokenRevokedError(MConnectAuthError):
    """Personal access token has been revoked (404)."""
    pass


class MConnectAccessError(Exception):
    """User does not have access to this home right now (e.g. time restrictions)."""
    pass


class MConnectApi:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = API_BASE_URL) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0.0
        self.home_id = None

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange short-lived auth JWT for access + refresh tokens."""
        url = self._base_url + "/home-assistant/token"
        payload = {"grant_type": "authorization_code", "code": code}
        async with self._session.post(url, json=payload) as resp:
            if resp.status == 403:
                body = await self._safe_json(resp)
                code_str = body.get("code", "")
                if code_str == "MaxPersonalAccessTokensError":
                    raise MConnectTokenLimitError(
                        body.get("message", "Maximum personal access tokens reached")
                    )
                raise MConnectAuthError(body.get("message", "Forbidden"))
            if resp.status == 400:
                body = await self._safe_json(resp)
                raise MConnectAuthError(
                    body.get("error_description", body.get("error", "invalid_grant"))
                )
            if resp.status == 401:
                raise MConnectAuthError("Unauthorized")
            if resp.status != 200:
                body = await resp.text()
                _LOGGER.error(
                    "MCONNECT token exchange failed: status=%d, body=%s",
                    resp.status, body[:500],
                )
                raise MConnectApiError(f"Token exchange failed (HTTP {resp.status})")
            data = await resp.json()
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token")
            self.home_id = data.get("home_id")
            self.token_expiry = time.time() + data.get("expires_in", 3600)
            return data

    async def refresh_access_token(self) -> None:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise MConnectAuthError("No refresh token available")
        url = self._base_url + "/home-assistant/token"
        payload = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        async with self._session.post(url, json=payload) as resp:
            if resp.status != 200:
                body_text = await resp.text()
                # Parse JSON from text
                body = {}
                try:
                    import json as _json
                    body = _json.loads(body_text)
                except Exception:
                    pass

                error_code = body.get("code", "")

                # Access period restriction — NOT an auth error
                if error_code == "InvalidAccessPeriodError":
                    raise MConnectAccessError(
                        body.get("message", "Access not allowed at this time")
                    )

                _LOGGER.error(
                    "MCONNECT token refresh failed: status=%d, body=%s",
                    resp.status, body_text[:500],
                )

                if resp.status == 403:
                    raise MConnectAuthError(body.get("message", "Forbidden"))
                if resp.status == 404:
                    if error_code == "TokenRevokedError":
                        raise MConnectTokenRevokedError(
                            "Personal access token has been revoked"
                        )
                    raise MConnectAuthError("Token not found")

                raise MConnectAuthError(f"Refresh failed (HTTP {resp.status})")
            data = await resp.json()
            self.access_token = data["access_token"]
            if "refresh_token" in data:
                self.refresh_token = data["refresh_token"]
            self.token_expiry = time.time() + data.get("expires_in", 3600)
            _LOGGER.debug(
                "MCONNECT token refreshed, expires in %ds",
                data.get("expires_in", 3600),
            )

    async def ensure_valid_token(self) -> None:
        """Ensure valid access token, refreshing 120s before expiry."""
        if self.access_token and time.time() < (self.token_expiry - 120):
            return
        await self.refresh_access_token()

    async def _request(self, method: str, path: str, json_data: dict[str, Any] | None = None) -> Any:
        """Make an authenticated request with auto-retry on 401."""
        await self.ensure_valid_token()
        url = self._base_url + path
        hdrs = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json",
        }
        _LOGGER.debug("MCONNECT API: %s %s", method, url)
        async with self._session.request(method, url, headers=hdrs, json=json_data) as resp:
            _LOGGER.debug("MCONNECT API: %s %s -> %d", method, path, resp.status)
            if resp.status == 401:
                # Check if this is an access period error
                body_text = await resp.text()
                body = {}
                try:
                    import json as _json
                    body = _json.loads(body_text)
                except Exception:
                    pass
                if body.get("code") == "InvalidAccessPeriodError":
                    raise MConnectAccessError(
                        body.get("message", "Access not allowed at this time")
                    )
                await self.refresh_access_token()
                hdrs["Authorization"] = "Bearer " + self.access_token
                async with self._session.request(method, url, headers=hdrs, json=json_data) as r2:
                    if r2.status == 401:
                        raise MConnectAuthError("Auth failed after refresh")
                    r2.raise_for_status()
                    return await r2.json() if r2.content_type == "application/json" else await r2.text()
            resp.raise_for_status()
            return await resp.json() if resp.content_type == "application/json" else await resp.text()

    async def get_devices(self) -> list[dict[str, Any]]:
        r = await self._request("GET", "/devices")
        return r if isinstance(r, list) else r.get("devices", r.get("data", []))

    async def get_device(self, device_id: str) -> dict[str, Any]:
        return await self._request("GET", "/devices/" + device_id)

    async def send_value(self, device_id: str, value_id: str, value: Any) -> None:
        await self._request(
            "POST",
            "/devices/value/" + device_id,
            json_data={"value_id": value_id, "value": value},
        )

    async def get_scenes(self) -> list[dict[str, Any]]:
        r = await self._request("GET", "/scenes")
        return r if isinstance(r, list) else r.get("scenes", r.get("data", []))

    async def execute_scene(self, scene_id: str) -> None:
        await self._request("POST", "/scenes/" + scene_id)

    async def revoke_token(self, token: str | None = None) -> bool:
        """Revoke a personal access token on the server.

        Args:
            token: The refresh_token JWT to revoke. Uses self.refresh_token if None.

        Returns True if revoked successfully, False on error (non-critical).
        """
        rt = token or self.refresh_token
        if not rt:
            return False
        url = self._base_url + "/home-assistant/token"
        try:
            async with self._session.request(
                "DELETE", url, json={"refresh_token": rt},
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status == 200:
                    data = await self._safe_json(resp)
                    _LOGGER.debug("MCONNECT: token revoked successfully")
                    return data.get("revoked", True)
                _LOGGER.warning(
                    "MCONNECT: token revocation returned status %d", resp.status
                )
                return False
        except Exception:
            _LOGGER.debug("MCONNECT: token revocation failed", exc_info=True)
            return False

    def export_tokens(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry,
        }

    def import_tokens(self, data: dict[str, Any]) -> None:
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.token_expiry = data.get("token_expiry", 0.0)
        self.home_id = data.get("home_id")

    @staticmethod
    async def _safe_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        """Safely parse JSON response, return empty dict on failure."""
        try:
            return await resp.json()
        except Exception:
            return {}
