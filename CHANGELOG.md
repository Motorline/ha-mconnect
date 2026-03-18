# Changelog

## 26.03.18 (2026-03-18)

### Fix LINK gate_state parsing

- Mask gate_state value with `0x3F` to extract only the lower 6 bits (actual state), stripping RF information ([#1](https://github.com/Motorline/ha-mconnect/issues/1))

## 26.03.16 (2026-03-16)

### Shutter mode support

- SHUTTER devices now respect the mode configuration from the MCONNECT app
- Mode 0 (Shutter): cover with open/close/position, respects `onlyOpenClose` attribute
- Mode 1 (Relay): two independent switches (relay_01, relay_02) + input binary sensors (sensor_open, sensor_close) with custom labels and visibility
- Mode 2 (Venetian): cover with tilt control via blind_rotation (open/close/set tilt position)
- New shared helper module `shutter_helpers.py`
- Note: changing shutter mode requires a manual integration reload in HA

## 26.03.13 (2026-03-12)

### Initial release

- OAuth authentication via MCONNECT webapp
- Personal access token management (create, revoke on reauth/removal)
- Real-time MQTT push updates
- REST API polling fallback (1h interval)
- Automatic token refresh with credential persistence
- Re-authentication flow when tokens are revoked
- Access period restriction handling (no crash on time-limited access)
- Dynamic device and scene discovery (add/remove without restart)
- LINK device support (gate_state commands + gate_position read-only)
- Diagnostics support with sensitive data redaction
- Supported platforms: cover, light, switch, lock, fan, climate, sensor, binary_sensor, scene
- Translations: English, Portuguese, Spanish, French, German, Polish, Romanian, Hungarian
