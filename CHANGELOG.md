# Changelog

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
