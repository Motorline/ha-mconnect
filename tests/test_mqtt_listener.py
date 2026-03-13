"""Tests for the MCONNECT MQTT listener."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from custom_components.mconnect.mqtt_listener import MConnectMqttListener


@pytest.fixture
def get_token():
    """Mock token getter."""
    return MagicMock(return_value="mock_jwt_token")


@pytest.fixture
def listener(get_token):
    """Create an MQTT listener instance."""
    return MConnectMqttListener(
        home_id="home123",
        host="mqtt.test.com",
        port=8884,
        use_ssl=True,
        get_token=get_token,
    )


# ── Basic properties ─────────────────────────────────────────────────────


def test_initial_state(listener):
    """Test initial listener state."""
    assert listener.connected is False
    assert listener._client is None


# ── Start / Stop ─────────────────────────────────────────────────────────


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_start(mock_client_cls, listener, get_token):
    """Test MQTT start creates client and connects."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()

    mock_client.username_pw_set.assert_called_once_with(
        username="mock_jwt_token", password="ha"
    )
    mock_client.tls_set.assert_called_once()
    mock_client.connect_async.assert_called_once_with("mqtt.test.com", 8884, keepalive=60)
    mock_client.loop_start.assert_called_once()


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_start_no_token(mock_client_cls, listener, get_token):
    """Test start does nothing when no token available."""
    get_token.return_value = None
    listener._get_token = get_token

    listener.start()

    mock_client_cls.assert_not_called()


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_stop(mock_client_cls, listener):
    """Test MQTT stop disconnects and cleans up."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    listener.stop()

    mock_client.disconnect.assert_called_once()
    mock_client.loop_stop.assert_called_once()
    assert listener._client is None
    assert listener.connected is False


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_start_already_started(mock_client_cls, listener):
    """Test start does nothing if already connected."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    listener.start()  # Second call should be ignored

    assert mock_client_cls.call_count == 1


# ── Callbacks registration ───────────────────────────────────────────────


def test_register_state_callback(listener):
    """Test registering and unregistering state callbacks."""
    cb = MagicMock()
    unsub = listener.register_state_callback(cb)

    assert cb in listener._state_callbacks

    unsub()
    assert cb not in listener._state_callbacks


def test_register_refresh_callback(listener):
    """Test registering and unregistering refresh callbacks."""
    cb = MagicMock()
    unsub = listener.register_refresh_callback(cb)

    assert cb in listener._refresh_callbacks

    unsub()
    assert cb not in listener._refresh_callbacks


# ── on_connect ───────────────────────────────────────────────────────────


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_on_connect_success(mock_client_cls, listener):
    """Test on_connect with rc=0 subscribes to topics."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    listener._on_connect(mock_client, None, {}, 0)

    assert listener.connected is True
    assert mock_client.subscribe.call_count >= 3  # rooms/devices/#, rooms, all, scenes


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_on_connect_auth_failed(mock_client_cls, listener, get_token):
    """Test on_connect with rc=5 refreshes credentials."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    get_token.return_value = "new_token"
    listener._on_connect(mock_client, None, {}, 5)

    assert listener.connected is False
    # Should have updated credentials
    assert mock_client.username_pw_set.call_count >= 2  # Once in start, once in reconnect


# ── on_disconnect ────────────────────────────────────────────────────────


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_on_disconnect_unexpected(mock_client_cls, listener, get_token):
    """Test unexpected disconnect updates credentials."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    listener._connected = True
    get_token.return_value = "refreshed_token"

    listener._on_disconnect(mock_client, None, 5)

    assert listener.connected is False
    mock_client.username_pw_set.assert_called_with(
        username="refreshed_token", password="ha"
    )


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_on_disconnect_clean(mock_client_cls, listener):
    """Test clean disconnect (stop event set) does not update credentials."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    listener._stop_event.set()
    initial_call_count = mock_client.username_pw_set.call_count

    listener._on_disconnect(mock_client, None, 1)

    # Should not have called username_pw_set again
    assert mock_client.username_pw_set.call_count == initial_call_count


# ── Message routing ──────────────────────────────────────────────────────


def test_route_device_value_update(listener):
    """Test device value update message is routed to callbacks."""
    cb = MagicMock()
    listener.register_state_callback(cb)

    topic = "homes/home123/rooms/devices/room1/device1/value1"
    payload = json.dumps({"value": 42})

    listener._route_message(topic, payload)

    cb.assert_called_once_with("device1", "value1", {"value": 42})


def test_route_device_value_plain_text(listener):
    """Test device value with non-JSON payload."""
    cb = MagicMock()
    listener.register_state_callback(cb)

    topic = "homes/home123/rooms/devices/room1/device1/value1"

    listener._route_message(topic, "plain_value")

    cb.assert_called_once_with("device1", "value1", {"value": "plain_value"})


def test_route_refresh_signal_rooms(listener):
    """Test rooms refresh signal triggers callbacks."""
    cb = MagicMock()
    listener.register_refresh_callback(cb)

    listener._route_message("homes/home123/rooms", "")
    cb.assert_called_once()


def test_route_refresh_signal_all(listener):
    """Test 'all' refresh signal triggers callbacks."""
    cb = MagicMock()
    listener.register_refresh_callback(cb)

    listener._route_message("homes/home123/all", "")
    cb.assert_called_once()


def test_route_refresh_signal_scenes(listener):
    """Test scenes refresh signal triggers callbacks."""
    cb = MagicMock()
    listener.register_refresh_callback(cb)

    listener._route_message("homes/home123/scenes", "")
    cb.assert_called_once()


def test_route_ignores_wrong_home(listener):
    """Test messages for different homes are ignored."""
    cb = MagicMock()
    listener.register_state_callback(cb)

    listener._route_message("homes/other_home/rooms/devices/r/d/v", '{"value":1}')
    cb.assert_not_called()


def test_route_ignores_short_device_path(listener):
    """Test messages with incomplete device paths are ignored."""
    cb = MagicMock()
    listener.register_state_callback(cb)

    # Only 4 parts instead of 5
    listener._route_message("homes/home123/rooms/devices/room1/device1", '{}')
    cb.assert_not_called()


# ── _update_credentials ──────────────────────────────────────────────────


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_update_credentials_success(mock_client_cls, listener, get_token):
    """Test credential update with fresh token."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    get_token.return_value = "fresh_token"

    result = listener._update_credentials()

    assert result is True
    mock_client.username_pw_set.assert_called_with(
        username="fresh_token", password="ha"
    )


def test_update_credentials_no_client(listener):
    """Test credential update fails without client."""
    result = listener._update_credentials()
    assert result is False


@patch("custom_components.mconnect.mqtt_listener.paho_mqtt.Client")
def test_update_credentials_no_token(mock_client_cls, listener, get_token):
    """Test credential update fails without token."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    listener.start()
    get_token.return_value = None

    result = listener._update_credentials()
    assert result is False
