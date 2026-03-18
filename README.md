# Motorline MCONNECT for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/Motorline/ha-mconnect/main/custom_components/mconnect/brand/logo.png" alt="Motorline MCONNECT" width="256">
</p>

[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Motorline/ha-mconnect.svg)](https://github.com/Motorline/ha-mconnect/releases)

Home Assistant integration for [Motorline MCONNECT](https://mconnect.pt) — control your gates, lights, shutters, locks and more directly from Home Assistant.

## Features

- **Real-time updates** via MQTT push — instant state changes without polling delays
- **Automatic device discovery** — new devices and scenes added in MCONNECT appear automatically in HA
- **OAuth authentication** — secure login via the MCONNECT webapp (email, Google, Facebook or Apple)
- **Personal Access Tokens** — revocable tokens managed from your MCONNECT account
- **Automatic token refresh** — access tokens renew seamlessly without user intervention
- **Full diagnostics** — downloadable diagnostics with sensitive data redacted

## Supported device types

| MCONNECT type | HA platform | Features |
|---|---|---|
| Gate / Garage / Link | Cover | Open, Close, Stop, Position |
| Shutter / Window / Door | Cover | Open, Close, Stop |
| Light | Light | On/Off, Brightness |
| Dimmer | Light | On/Off, Brightness |
| Switch / Plug / RF Controller | Switch | On/Off |
| Lock | Lock | Lock/Unlock |
| Fan | Fan | On/Off, Speed |
| Thermostat | Climate | On/Off, Temperature, Modes |
| Sensor | Sensor | Temperature, Humidity, Power, Energy, etc. |
| Motion Sensor / ZB Motion Sensor | Binary sensor | Motion detection |
| Scenes | Scene | Activate |

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant
2. Click **⋮** → **Custom repositories**
3. Add `https://github.com/Motorline/ha-mconnect` with category **Integration**
4. Search for **Motorline MCONNECT** and click **Download**
5. Restart Home Assistant

### Manual

1. Download the [latest release](https://github.com/Motorline/ha-mconnect/releases)
2. Extract the `mconnect` folder into `config/custom_components/`
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **MCONNECT**
3. A browser window opens to the MCONNECT login page
4. Sign in with your MCONNECT account and select your home
5. The window closes automatically and your devices appear in HA

No manual configuration or YAML is needed.

## How it works

The integration connects to the Motorline MCONNECT cloud platform:

- **REST API** — fetches devices, scenes and states every hour as a sync fallback
- **MQTT** — receives real-time push updates for instant state changes
- **OAuth** — authenticates via server-signed JWTs with automatic token refresh

When you change a device state in the MCONNECT app, it appears in HA within seconds via MQTT. The 60-second polling serves as a fallback to ensure data stays in sync.

## Re-authentication

If your session expires or is revoked, Home Assistant will show a notification asking you to re-authenticate. Click it and sign in again — all your devices and automations remain intact.

You can also manage your Home Assistant personal access token from the MCONNECT app/webapp under account settings.

## Removing the integration

1. Go to **Settings** → **Devices & Services**
2. Find **MCONNECT** and click **⋮** → **Delete**
3. All devices and entities will be removed from HA

This does not affect your MCONNECT account or devices.

## Troubleshooting

| Issue | Solution |
|---|---|
| "Authentication failed" during setup | Ensure you're using the correct MCONNECT account and that your subscription is active |
| Setup fails on mobile app | Go to **Settings → System → Network** and set your external Home Assistant URL |
| Devices show as "Unavailable" | Check that the MCONNECT endpoint/hub is online in the MCONNECT app |
| MQTT disconnects in logs | Normal when access token refreshes — the connection recovers automatically within seconds |
| Scenes not appearing | New scenes are detected via MQTT push or on the hourly sync — restart the integration to force an immediate refresh |
| Re-auth notification keeps appearing | Remove the integration and add it again to get a fresh token |

## Known limitations

- Requires an active MCONNECT cloud account and internet connection (cloud-based integration)
- Cover position feedback depends on the physical device supporting it — most Motorline gates are open/close only
- Device names and icons come from the MCONNECT platform — rename them in HA via the entity settings if needed

## License

This project is licensed under the **MIT License with Commons Clause** — you are free to use, modify, and contribute, but commercial use by third parties is not permitted. See [LICENSE](LICENSE) for details.
