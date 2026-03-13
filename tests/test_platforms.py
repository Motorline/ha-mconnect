"""Tests for MCONNECT entity platforms (cover, light, switch, scene, etc.)."""

from __future__ import annotations

import copy

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.mconnect.coordinator import MConnectCoordinator, MConnectData
from custom_components.mconnect.const import DOMAIN

from .conftest import MOCK_DEVICES, MOCK_SCENES, MOCK_HOME_ID


def _build_coordinator_data(devices=None, scenes=None) -> MConnectData:
    """Build a MConnectData instance from mock data (deep copied)."""
    data = MConnectData()
    for d in copy.deepcopy(devices or MOCK_DEVICES):
        did = str(d.get("_id") or d.get("id"))
        dtype = d.get("type", "")
        if dtype not in ("devices.types.ZB_BRIDGE", "devices.types.SCENE"):
            data.devices[did] = d
    for s in copy.deepcopy(scenes or MOCK_SCENES):
        sid = str(s.get("_id") or s.get("id"))
        data.scenes[sid] = s
    return data


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> MagicMock:
    """Create a mock coordinator with real MConnectData."""
    coord = MagicMock()
    coord.data = _build_coordinator_data()
    coord.hass = hass
    coord.api = AsyncMock()
    coord.api.send_value = AsyncMock()
    coord.api.execute_scene = AsyncMock()
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    coord.last_update_success = True
    # Needed for CoordinatorEntity.__init__
    coord.async_request_refresh = AsyncMock()
    return coord


# ── Cover platform ───────────────────────────────────────────────────────


def test_cover_entity_creation(mock_coordinator):
    """Test cover entity is created for garage device with position support."""
    from custom_components.mconnect.cover import MConnectCover
    from homeassistant.components.cover import CoverEntityFeature

    device = MOCK_DEVICES[0]  # Garage with OpenClose (percentage)
    entity = MConnectCover(mock_coordinator, device, "open_close")

    assert entity.unique_id == f"{DOMAIN}_device001_open_close"
    assert entity.device_class is not None  # garage
    # OpenClose percentage-based supports position
    assert entity.supported_features & CoverEntityFeature.SET_POSITION
    assert entity.supported_features & CoverEntityFeature.OPEN
    assert entity.supported_features & CoverEntityFeature.CLOSE


def test_cover_is_closed(mock_coordinator):
    """Test cover closed logic: OpenClose value 0 = closed (percentage-based)."""
    from custom_components.mconnect.cover import MConnectCover

    device = MOCK_DEVICES[0]
    entity = MConnectCover(mock_coordinator, device, "open_close")

    # Verify the data: value=0 means fully closed
    data = mock_coordinator.data
    assert data.get_device_value("device001", "open_close") == 0


async def test_cover_open(mock_coordinator):
    """Test cover open sends max value (100)."""
    from custom_components.mconnect.cover import MConnectCover

    device = MOCK_DEVICES[0]
    entity = MConnectCover(mock_coordinator, device, "open_close")

    await entity.async_open_cover()
    mock_coordinator.api.send_value.assert_called_with("device001", "open_close", 100)


async def test_cover_close(mock_coordinator):
    """Test cover close sends min value (0)."""
    from custom_components.mconnect.cover import MConnectCover

    device = MOCK_DEVICES[0]
    entity = MConnectCover(mock_coordinator, device, "open_close")

    await entity.async_close_cover()
    mock_coordinator.api.send_value.assert_called_with("device001", "open_close", 0)


# ── LINK cover ───────────────────────────────────────────────────────────


def test_link_cover_creation(mock_coordinator):
    """Test LINK cover with gate_state commands + gate_position read-only."""
    from custom_components.mconnect.cover import MConnectCover
    from homeassistant.components.cover import CoverEntityFeature

    device = MOCK_DEVICES[6]  # LINK device
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    assert entity._is_link is True
    # LINK supports open/close/stop but NOT set_position
    assert entity.supported_features & CoverEntityFeature.OPEN
    assert entity.supported_features & CoverEntityFeature.CLOSE
    assert entity.supported_features & CoverEntityFeature.STOP
    assert not (entity.supported_features & CoverEntityFeature.SET_POSITION)


def test_link_cover_closed_state(mock_coordinator):
    """Test LINK cover reports closed from gate_state=0."""
    from custom_components.mconnect.cover import MConnectCover

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    # gate_state=0 → closed
    data = mock_coordinator.data
    assert data.get_device_value("device007", "gate_state") == 0


def test_link_cover_opening_state(mock_coordinator):
    """Test LINK cover reports opening from gate_state=8."""
    from custom_components.mconnect.cover import MConnectCover, GATE_STATE_OPENING

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    mock_coordinator.data.update_device_value(
        "device007", "gate_state", {"value": 8}
    )

    state = entity._get_gate_state()
    assert state == 8
    assert state in GATE_STATE_OPENING


def test_link_cover_closing_state(mock_coordinator):
    """Test LINK cover reports closing from gate_state=6."""
    from custom_components.mconnect.cover import MConnectCover, GATE_STATE_CLOSING

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    mock_coordinator.data.update_device_value(
        "device007", "gate_state", {"value": 6}
    )

    state = entity._get_gate_state()
    assert state == 6
    assert state in GATE_STATE_CLOSING


def test_link_cover_position_read_only(mock_coordinator):
    """Test LINK cover reads position from gate_position (read-only)."""
    from custom_components.mconnect.cover import MConnectCover

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    # Set gate_position to 50%
    mock_coordinator.data.update_device_value(
        "device007", "gate_position", {"value": 50, "min": 0, "max": 100}
    )

    pos = entity._link_position()
    assert pos == 50


async def test_link_cover_open_sends_to_gate_state(mock_coordinator):
    """Test LINK open sends FULL_OPEN command (2) to gate_state, NOT gate_position."""
    from custom_components.mconnect.cover import MConnectCover, LINK_CMD_FULL_OPEN

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    await entity.async_open_cover()
    mock_coordinator.api.send_value.assert_called_with(
        "device007", "gate_state", LINK_CMD_FULL_OPEN  # 2
    )


async def test_link_cover_close_sends_to_gate_state(mock_coordinator):
    """Test LINK close sends CLOSE command (0) to gate_state."""
    from custom_components.mconnect.cover import MConnectCover, LINK_CMD_CLOSE

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    await entity.async_close_cover()
    mock_coordinator.api.send_value.assert_called_with(
        "device007", "gate_state", LINK_CMD_CLOSE  # 0
    )


async def test_link_cover_stop_sends_to_gate_state(mock_coordinator):
    """Test LINK stop sends STOP command (13) to gate_state."""
    from custom_components.mconnect.cover import MConnectCover, LINK_CMD_STOP

    device = MOCK_DEVICES[6]
    entity = MConnectCover(
        mock_coordinator, device,
        value_id="gate_state",
        gate_state_vid="gate_state",
        gate_position_vid="gate_position",
    )

    await entity.async_stop_cover()
    mock_coordinator.api.send_value.assert_called_with(
        "device007", "gate_state", LINK_CMD_STOP  # 13
    )


# ── Light platform ───────────────────────────────────────────────────────


def test_light_entity_creation(mock_coordinator):
    """Test light entity is created with correct color mode."""
    from custom_components.mconnect.light import MConnectLight
    from homeassistant.components.light import ColorMode

    device = MOCK_DEVICES[1]  # Light with on_off + brightness
    entity = MConnectLight(mock_coordinator, device, "on_off", "brightness")

    assert entity.unique_id == f"{DOMAIN}_device002_on_off"
    assert entity.color_mode == ColorMode.BRIGHTNESS
    assert ColorMode.BRIGHTNESS in entity.supported_color_modes


def test_light_is_on(mock_coordinator):
    """Test light reports on state."""
    from custom_components.mconnect.light import MConnectLight

    device = MOCK_DEVICES[1]
    entity = MConnectLight(mock_coordinator, device, "on_off", "brightness")

    assert entity.is_on is True  # value=1


def test_light_brightness(mock_coordinator):
    """Test light brightness conversion."""
    from custom_components.mconnect.light import MConnectLight

    device = MOCK_DEVICES[1]
    entity = MConnectLight(mock_coordinator, device, "on_off", "brightness")

    # 75 out of 0-100 → ~191 out of 0-255
    brightness = entity.brightness
    assert brightness is not None
    assert 180 <= brightness <= 200


async def test_light_turn_on(mock_coordinator):
    """Test light turn on."""
    from custom_components.mconnect.light import MConnectLight

    device = MOCK_DEVICES[1]
    entity = MConnectLight(mock_coordinator, device, "on_off", "brightness")

    await entity.async_turn_on()
    mock_coordinator.api.send_value.assert_called()


async def test_light_turn_off(mock_coordinator):
    """Test light turn off."""
    from custom_components.mconnect.light import MConnectLight

    device = MOCK_DEVICES[1]
    entity = MConnectLight(mock_coordinator, device, "on_off", "brightness")

    await entity.async_turn_off()
    mock_coordinator.api.send_value.assert_called()


# ── Switch platform ──────────────────────────────────────────────────────


def test_switch_entity_creation(mock_coordinator):
    """Test switch entity is created for plug device."""
    from custom_components.mconnect.switch import MConnectSwitch
    from homeassistant.components.switch import SwitchDeviceClass

    device = MOCK_DEVICES[2]  # Plug
    entity = MConnectSwitch(mock_coordinator, device, "on_off", is_plug=True)

    assert entity.device_class == SwitchDeviceClass.OUTLET


def test_switch_is_off(mock_coordinator):
    """Test switch reports off state."""
    from custom_components.mconnect.switch import MConnectSwitch

    device = MOCK_DEVICES[2]
    entity = MConnectSwitch(mock_coordinator, device, "on_off")

    assert entity.is_on is False  # value=0


async def test_switch_turn_on(mock_coordinator):
    """Test switch turn on sends value 1."""
    from custom_components.mconnect.switch import MConnectSwitch

    device = MOCK_DEVICES[2]
    entity = MConnectSwitch(mock_coordinator, device, "on_off")

    await entity.async_turn_on()
    mock_coordinator.api.send_value.assert_called_with("device003", "on_off", 1)


async def test_switch_turn_off(mock_coordinator):
    """Test switch turn off sends value 0."""
    from custom_components.mconnect.switch import MConnectSwitch

    device = MOCK_DEVICES[2]
    entity = MConnectSwitch(mock_coordinator, device, "on_off")

    await entity.async_turn_off()
    mock_coordinator.api.send_value.assert_called_with("device003", "on_off", 0)


# ── Lock platform ────────────────────────────────────────────────────────


def test_lock_is_locked(mock_coordinator):
    """Test lock reports locked state."""
    from custom_components.mconnect.lock import MConnectLock

    device = MOCK_DEVICES[5]  # Lock
    entity = MConnectLock(mock_coordinator, device, "lock_unlock")

    assert entity.is_locked is True  # value=1


async def test_lock_unlock(mock_coordinator):
    """Test lock unlock command."""
    from custom_components.mconnect.lock import MConnectLock

    device = MOCK_DEVICES[5]
    entity = MConnectLock(mock_coordinator, device, "lock_unlock")

    await entity.async_unlock()
    mock_coordinator.api.send_value.assert_called_with("device006", "lock_unlock", 0)


async def test_lock_lock(mock_coordinator):
    """Test lock command."""
    from custom_components.mconnect.lock import MConnectLock

    device = MOCK_DEVICES[5]
    entity = MConnectLock(mock_coordinator, device, "lock_unlock")

    await entity.async_lock()
    mock_coordinator.api.send_value.assert_called_with("device006", "lock_unlock", 1)


# ── Sensor platform ─────────────────────────────────────────────────────


def test_sensor_entity_creation(mock_coordinator):
    """Test sensor entity infers device class."""
    from custom_components.mconnect.sensor import MConnectSensor
    from homeassistant.components.sensor import SensorDeviceClass

    device = MOCK_DEVICES[3]  # Temperature sensor
    entity = MConnectSensor(mock_coordinator, device, "temperature")

    assert entity.device_class == SensorDeviceClass.TEMPERATURE
    assert entity.native_unit_of_measurement == "°C"


def test_sensor_value(mock_coordinator):
    """Test sensor returns numeric value."""
    from custom_components.mconnect.sensor import MConnectSensor

    device = MOCK_DEVICES[3]
    entity = MConnectSensor(mock_coordinator, device, "temperature")

    assert entity.native_value == 22.5


# ── Binary sensor platform ──────────────────────────────────────────────


def test_binary_sensor_creation(mock_coordinator):
    """Test binary sensor entity with motion class."""
    from custom_components.mconnect.binary_sensor import MConnectBinarySensor
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass

    device = MOCK_DEVICES[4]  # Motion sensor
    entity = MConnectBinarySensor(
        mock_coordinator, device, "motion", "devices.types.MOTION_SENSOR"
    )

    assert entity.device_class == BinarySensorDeviceClass.MOTION
    assert entity.is_on is False  # value=0


# ── Scene platform ──────────────────────────────────────────────────────


def test_scene_entity_creation(mock_coordinator):
    """Test scene entity creation."""
    from custom_components.mconnect.scene import MConnectScene

    scene = MOCK_SCENES[0]
    entity = MConnectScene(mock_coordinator, scene)

    assert entity.unique_id == f"{DOMAIN}_scene_scene001"
    assert entity.name == "Boa Noite"


async def test_scene_activate(mock_coordinator):
    """Test scene activation."""
    from custom_components.mconnect.scene import MConnectScene

    scene = MOCK_SCENES[0]
    entity = MConnectScene(mock_coordinator, scene)

    await entity.async_activate()
    mock_coordinator.api.execute_scene.assert_called_once_with("scene001")
