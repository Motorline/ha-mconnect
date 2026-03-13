"""MQTT listener for real-time device state updates from MCONNECT."""

from __future__ import annotations

import json
import logging
import ssl
import threading
from typing import Any, Callable

import paho.mqtt.client as paho_mqtt

_LOGGER = logging.getLogger(__name__)

# Callback type: (device_id, value_id, value_payload)
StateCallback = Callable[[str, str, dict[str, Any]], None]
# Callback for refresh signals
RefreshCallback = Callable[[], None]


class MConnectMqttListener:
    """Connects to the MCONNECT MQTT frontend broker for push updates."""

    def __init__(
        self,
        home_id: str,
        host: str,
        port: int,
        use_ssl: bool,
        get_token: Callable[[], str | None],
    ) -> None:
        self._home_id = home_id
        self._host = host
        self._port = port
        self._use_ssl = use_ssl
        self._get_token = get_token

        self._state_callbacks: list[StateCallback] = []
        self._refresh_callbacks: list[RefreshCallback] = []

        self._client: paho_mqtt.Client | None = None
        self._connected = False
        self._stop_event = threading.Event()

    # ── Public API ───────────────────────────────────────────────────────

    def register_state_callback(self, callback: StateCallback) -> Callable[[], None]:
        """Register a callback for device state updates. Returns unsubscribe fn."""
        self._state_callbacks.append(callback)
        return lambda: self._state_callbacks.remove(callback)

    def register_refresh_callback(self, callback: RefreshCallback) -> Callable[[], None]:
        """Register a callback for refresh signals (rooms changed, etc.)."""
        self._refresh_callbacks.append(callback)
        return lambda: self._refresh_callbacks.remove(callback)

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        """Connect to the MQTT broker in a background thread."""
        if self._client is not None:
            return

        token = self._get_token()
        if not token:
            _LOGGER.warning("No MQTT token available, skipping MQTT connection")
            return

        client_id = f"ha-mconnect-{self._home_id[:8]}"
        self._client = paho_mqtt.Client(
            client_id=client_id,
            protocol=paho_mqtt.MQTTv311,
        )

        # Auth: JWT as username, password can be anything
        self._client.username_pw_set(username=token, password="ha")

        if self._use_ssl:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._client.reconnect_delay_set(min_delay=5, max_delay=120)

        try:
            self._client.connect_async(self._host, self._port, keepalive=60)
            self._client.loop_start()
            _LOGGER.info("MQTT connecting to %s:%s", self._host, self._port)
        except Exception:
            _LOGGER.exception("Failed to start MQTT connection")
            self._client = None

    def stop(self) -> None:
        """Disconnect and clean up."""
        self._stop_event.set()
        if self._client:
            try:
                self._client.disconnect()
                self._client.loop_stop()
            except Exception:
                pass
            self._client = None
            self._connected = False
            _LOGGER.info("MQTT disconnected")

    def reconnect_with_new_token(self) -> None:
        """Reconnect using an updated JWT token."""
        self.stop()
        self._stop_event.clear()
        self.start()

    def _update_credentials(self) -> bool:
        """Update MQTT credentials with a fresh token before reconnect."""
        if not self._client:
            return False
        token = self._get_token()
        if not token:
            _LOGGER.warning("MQTT: no token available for credential update")
            return False
        self._client.username_pw_set(username=token, password="ha")
        _LOGGER.debug("MQTT credentials updated with fresh token")
        return True

    # ── Paho callbacks ───────────────────────────────────────────────────

    def _on_connect(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        flags: dict[str, Any],
        rc: int,
    ) -> None:
        if rc == 0:
            self._connected = True
            _LOGGER.info("MQTT connected, subscribing to home topics")
            self._subscribe_topics(client)
        else:
            self._connected = False
            rc_reasons = {
                1: "incorrect protocol version",
                2: "invalid client identifier",
                3: "server unavailable",
                4: "bad username or password",
                5: "not authorised",
            }
            reason = rc_reasons.get(rc, "unknown")
            _LOGGER.error("MQTT connection refused: rc=%s (%s)", rc, reason)

            # rc=4 or rc=5: token likely expired, refresh before next attempt
            if rc in (4, 5):
                _LOGGER.info("MQTT: token expired, refreshing credentials for next reconnect")
                self._update_credentials()

    def _on_disconnect(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        rc: int,
    ) -> None:
        self._connected = False
        if rc != 0 and not self._stop_event.is_set():
            _LOGGER.warning("MQTT unexpected disconnect (rc=%s), updating credentials", rc)
            # Refresh token before paho's auto-reconnect fires
            self._update_credentials()

    def _on_message(
        self,
        client: paho_mqtt.Client,
        userdata: Any,
        msg: paho_mqtt.MQTTMessage,
    ) -> None:
        topic = msg.topic
        payload_raw = msg.payload.decode("utf-8", errors="replace")

        _LOGGER.debug("MQTT message: %s → %s", topic, payload_raw[:200])

        try:
            self._route_message(topic, payload_raw)
        except Exception:
            _LOGGER.exception("Error processing MQTT message on %s", topic)

    # ── Topic routing ────────────────────────────────────────────────────

    def _subscribe_topics(self, client: paho_mqtt.Client) -> None:
        prefix = f"homes/{self._home_id}"
        topics = [
            (f"{prefix}/rooms/devices/#", 1),  # Individual device value changes
            (f"{prefix}/rooms", 1),             # Rooms refresh signal
            (f"{prefix}/all", 1),               # Full refresh signal
            (f"{prefix}/scenes", 1),            # Scenes refresh signal
        ]
        for topic, qos in topics:
            client.subscribe(topic, qos)
            _LOGGER.debug("Subscribed to %s", topic)

    def _route_message(self, topic: str, payload: str) -> None:
        prefix = f"homes/{self._home_id}/"

        if not topic.startswith(prefix):
            return

        relative = topic[len(prefix):]

        # ── Device value update ──────────────────────────────────────
        # Format: rooms/devices/{room_id}/{device_id}/{value_id}
        if relative.startswith("rooms/devices/"):
            parts = relative.split("/")
            # parts: ["rooms", "devices", room_id, device_id, value_id]
            if len(parts) == 5:
                _room_id, device_id, value_id = parts[2], parts[3], parts[4]
                try:
                    value_data = json.loads(payload)
                except (json.JSONDecodeError, ValueError):
                    value_data = {"value": payload}

                for cb in self._state_callbacks:
                    try:
                        cb(device_id, value_id, value_data)
                    except Exception:
                        _LOGGER.exception("State callback error")
            return

        # ── Refresh signals ──────────────────────────────────────────
        if relative in ("rooms", "all", "scenes"):
            for cb in self._refresh_callbacks:
                try:
                    cb()
                except Exception:
                    _LOGGER.exception("Refresh callback error")
