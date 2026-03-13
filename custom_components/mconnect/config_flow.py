"""Config flow for MCONNECT integration.

External auth flow - no client_id, no client_secret needed.
Security relies entirely on server-signed JWTs:
1. Server generates short-lived JWT (5 min) with platform='home-assistant'
2. HA receives JWT via webhook callback
3. HA sends JWT to /home-assistant/token
4. Server verifies JWT signature + expiry + platform flag
5. Server returns long-lived access_token (1h) + refresh_token
"""
from __future__ import annotations
import logging, secrets
from typing import Any
from urllib.parse import urlencode
from aiohttp import web
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.components import webhook
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from .api import MConnectApi, MConnectAuthError, MConnectApiError, MConnectTokenLimitError, MConnectTokenRevokedError
from .const import AUTH_WEB_URL, CONF_HOME_ID, CONF_HOME_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

OK_HTML = (
    "<!DOCTYPE html><html><head><title>MCONNECT</title>"
    "<style>body{font-family:sans-serif;display:flex;align-items:center;"
    "justify-content:center;height:100vh;margin:0;background:#f5f5f5}"
    ".c{text-align:center;padding:2rem;background:#fff;border-radius:12px;"
    'box-shadow:0 2px 8px rgba(0,0,0,.1)}h2{color:#4CAF50}</style></head>'
    '<body><div class="c"><h2 id="t"></h2><p id="m"></p></div>'
    "<script>"
    "var i={pt:['Autenticação com sucesso','Pode fechar esta janela e voltar ao Home Assistant.'],"
    "es:['Autenticación exitosa','Puede cerrar esta ventana y volver a Home Assistant.'],"
    "fr:['Authentification réussie','Vous pouvez fermer cette fenêtre et retourner à Home Assistant.'],"
    "de:['Authentifizierung erfolgreich','Sie können dieses Fenster schließen und zu Home Assistant zurückkehren.'],"
    "pl:['Uwierzytelnianie zakończone','Możesz zamknąć to okno i wrócić do Home Assistant.'],"
    "ro:['Autentificare reușită','Puteți închide această fereastră și reveni la Home Assistant.'],"
    "hu:['Hitelesítés sikeres','Bezárhatja ezt az ablakot és visszatérhet a Home Assistanthoz.'],"
    "en:['Authentication successful','You can close this window and return to Home Assistant.']};"
    "var l=navigator.language.slice(0,2),t=i[l]||i.en;"
    "document.getElementById('t').textContent=t[0];"
    "document.getElementById('m').textContent=t[1];"
    "</script></body></html>"
)
FAIL_HTML = (
    "<!DOCTYPE html><html><head><title>MCONNECT</title>"
    "<style>body{font-family:sans-serif;display:flex;align-items:center;"
    "justify-content:center;height:100vh;margin:0;background:#f5f5f5}"
    ".c{text-align:center;padding:2rem;background:#fff;border-radius:12px;"
    'box-shadow:0 2px 8px rgba(0,0,0,.1)}h2{color:#f44336}</style></head>'
    '<body><div class="c"><h2 id="t"></h2><p id="m"></p></div>'
    "<script>"
    "var i={pt:['Autenticação falhou','Por favor tente novamente a partir do Home Assistant.'],"
    "es:['Autenticación fallida','Por favor, inténtelo de nuevo desde Home Assistant.'],"
    "fr:['Échec de l\\'authentification','Veuillez réessayer depuis Home Assistant.'],"
    "de:['Authentifizierung fehlgeschlagen','Bitte versuchen Sie es erneut über Home Assistant.'],"
    "pl:['Uwierzytelnianie nie powiodło się','Spróbuj ponownie z poziomu Home Assistant.'],"
    "ro:['Autentificare eșuată','Vă rugăm să încercați din nou din Home Assistant.'],"
    "hu:['Hitelesítés sikertelen','Kérjük, próbálja újra a Home Assistantból.'],"
    "en:['Authentication failed','Please try again from Home Assistant.']};"
    "var l=navigator.language.slice(0,2),t=i[l]||i.en;"
    "document.getElementById('t').textContent=t[0];"
    "document.getElementById('m').textContent=t[1];"
    "</script></body></html>"
)


async def _webhook_handler(hass: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response:
    _LOGGER.debug("MCONNECT webhook called! method=%s, query=%s", request.method, dict(request.query))
    params = dict(request.query)
    flow_id = params.get("state")
    code = params.get("code")
    if not flow_id or not code:
        _LOGGER.error("MCONNECT webhook: missing state or code")
        return web.Response(text=FAIL_HTML, content_type="text/html")
    hass.data.setdefault(DOMAIN, {})
    key = "auth_" + flow_id
    hass.data[DOMAIN][key] = {
        "code": code,
        "home_id": params.get("home_id", ""),
        "home_name": params.get("home_name", "Home"),
    }
    _LOGGER.debug("MCONNECT webhook: stored auth data for flow_id=%s, key=%s, domain_keys=%s", flow_id, key, list(hass.data.get(DOMAIN, {}).keys()))

    # Tell HA to advance the config flow - this triggers async_step_auth
    try:
        await hass.config_entries.flow.async_configure(flow_id=flow_id)
        _LOGGER.debug("MCONNECT webhook: flow advanced for flow_id=%s", flow_id)
    except Exception as err:
        _LOGGER.debug("MCONNECT webhook: async_configure returned: %s", err)

    return web.Response(text=OK_HTML, content_type="text/html")


class MConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Motorline MCONNECT."""

    VERSION = 1

    def __init__(self) -> None:
        self._wh_id = None
        self._auth_url = None
        self._auth_data = None
        self._reauth_entry = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Start external auth flow."""
        _LOGGER.debug("MCONNECT: async_step_user called, flow_id=%s", self.flow_id)
        self._wh_id = "mconnect_auth_" + secrets.token_hex(16)
        webhook.async_register(
            self.hass, DOMAIN, "MCONNECT Auth",
            self._wh_id, _webhook_handler,
            allowed_methods=("GET", "POST"),
        )
        _LOGGER.debug("MCONNECT: webhook registered: %s", self._wh_id)
        try:
            ha_url = get_url(self.hass, allow_internal=True, prefer_external=True)
        except Exception:
            ha_url = get_url(self.hass, allow_internal=True)
        redirect_uri = ha_url + "/api/webhook/" + self._wh_id
        params = {
            "platform": "home-assistant",
            "type": "authorization",
            "redirect_uri": redirect_uri,
            "state": self.flow_id,
        }
        self._auth_url = AUTH_WEB_URL + "/?" + urlencode(params)
        _LOGGER.debug("MCONNECT: auth_url=%s", self._auth_url)
        return self.async_external_step(step_id="auth", url=self._auth_url)

    async def async_step_auth(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Poll for auth completion."""
        key = "auth_" + self.flow_id
        domain_data = self.hass.data.get(DOMAIN, {})
        auth_data = domain_data.get(key)
        _LOGGER.debug("MCONNECT: async_step_auth poll, flow_id=%s, key=%s, found=%s, all_keys=%s", self.flow_id, key, auth_data is not None, list(domain_data.keys()))
        if auth_data is not None:
            self._auth_data = auth_data
            self.hass.data[DOMAIN].pop(key, None)
            if self._wh_id:
                webhook.async_unregister(self.hass, self._wh_id)
            _LOGGER.debug("MCONNECT: auth data found! advancing to finish. home_id=%s", auth_data.get("home_id"))
            return self.async_external_step_done(next_step_id="finish")
        return self.async_external_step(step_id="auth", url=self._auth_url)

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Exchange auth code JWT for tokens and create config entry."""
        _LOGGER.debug("MCONNECT: async_step_finish called, has_auth_data=%s", self._auth_data is not None)
        if self._auth_data is None:
            _LOGGER.error("MCONNECT: no auth data in finish step!")
            return self.async_abort(reason="auth_failed")
        code = self._auth_data["code"]
        home_id = self._auth_data.get("home_id", "")
        home_name = self._auth_data.get("home_name", "Home")
        _LOGGER.debug("MCONNECT: exchanging code for tokens, home_id=%s, code_len=%d", home_id, len(code))
        session = async_get_clientsession(self.hass)
        api = MConnectApi(session)
        try:
            data = await api.exchange_code(code)
            home_id = data.get("home_id", home_id)
            home_name = data.get("home_name", home_name)
            _LOGGER.debug("MCONNECT: token exchange SUCCESS! home=%s, has_access=%s, has_refresh=%s", home_name, api.access_token is not None, api.refresh_token is not None)
        except MConnectTokenLimitError as err:
            _LOGGER.error("MCONNECT: max personal access tokens reached: %s", err)
            return self.async_abort(reason="token_limit_reached")
        except MConnectTokenRevokedError as err:
            _LOGGER.error("MCONNECT: token revoked: %s", err)
            return self.async_abort(reason="token_revoked")
        except MConnectAuthError as err:
            _LOGGER.error("MCONNECT: token exchange auth error: %s", err)
            return self.async_abort(reason="auth_failed")
        except MConnectApiError as err:
            _LOGGER.error("MCONNECT: token exchange API error: %s", err)
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("MCONNECT: token exchange UNEXPECTED ERROR")
            return self.async_abort(reason="unknown")
        await self.async_set_unique_id(home_id)

        # Handle reauth: update existing entry instead of creating new one
        if self._reauth_entry:
            result = await self._finish_reauth(api, home_id, home_name)
            if result:
                return result

        # Check if already configured — revoke the newly created token before aborting
        existing = self._async_current_entries()
        for entry in existing:
            if entry.unique_id == home_id:
                _LOGGER.debug(
                    "MCONNECT: home %s already configured, revoking new token", home_id
                )
                await api.revoke_token()
                return self.async_abort(reason="already_configured")

        _LOGGER.debug("MCONNECT: creating config entry for %s", home_name)
        return self.async_create_entry(
            title="MCONNECT - " + home_name,
            data={
                CONF_HOME_ID: home_id,
                CONF_HOME_NAME: home_name,
                **api.export_tokens(),
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle re-authentication when token expires."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id", "")
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Start reauth external flow."""
        return await self.async_step_user()

    async def _finish_reauth(self, api: MConnectApi, home_id: str, home_name: str) -> config_entries.ConfigFlowResult | None:
        """Finish reauth by revoking old token and updating existing entry."""
        if self._reauth_entry:
            # Revoke old personal access token before replacing with new one
            old_refresh = self._reauth_entry.data.get("refresh_token")
            if old_refresh:
                _LOGGER.debug("MCONNECT: revoking old personal access token")
                revoke_api = MConnectApi(async_get_clientsession(self.hass))
                revoke_api.import_tokens(self._reauth_entry.data)
                await revoke_api.revoke_token(old_refresh)

            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={
                    CONF_HOME_ID: home_id,
                    CONF_HOME_NAME: home_name,
                    **api.export_tokens(),
                },
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return None
