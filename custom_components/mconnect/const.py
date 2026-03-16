"""Constants for the Motorline MCONNECT integration."""
from __future__ import annotations

DOMAIN = "mconnect"
MANUFACTURER = "Motorline"

CONF_HOME_ID = "home_id"
CONF_HOME_NAME = "home_name"

DATA_ACCESS_TOKEN = "access_token"
DATA_REFRESH_TOKEN = "refresh_token"
DATA_TOKEN_EXPIRY = "token_expiry"
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
DATA_MQTT = "mqtt_listener"

API_BASE_URL = "https://rest.mconnect.pt"
AUTH_WEB_URL = "https://mconnect.pt"

MQTT_HOST = "mqttf.mconnect.pt"
MQTT_PORT = 8884
MQTT_USE_SSL = True

SCAN_INTERVAL_SECONDS = 3600

DEVICE_TYPE_PLATFORM: dict[str, str] = {
    "devices.types.LIGHT": "light",
    "devices.types.DIMMER": "light",
    "devices.types.SWITCH": "switch",
    "devices.types.PLUG": "switch",
    "devices.types.DOOR": "cover",
    "devices.types.GARAGE": "cover",
    "devices.types.SHUTTER": "cover",
    "devices.types.WINDOW": "cover",
    "devices.types.LOCK": "lock",
    "devices.types.FAN": "fan",
    "devices.types.THERMOSTAT": "climate",
    "devices.types.SENSOR": "sensor",
    "devices.types.MOTION_SENSOR": "binary_sensor",
    "devices.types.ZB_MOTION_SENSOR": "binary_sensor",
    "devices.types.LINK": "cover",
    "devices.types.RF_CONTROLLER": "switch",
    "devices.types.RF_REMOTE": "switch",
}

DEVICE_TYPE_IGNORE: set[str] = {"devices.types.ZB_BRIDGE", "devices.types.SCENE"}

COVER_DEVICE_CLASSES: dict[str, str] = {
    "devices.types.DOOR": "door", "devices.types.GARAGE": "garage",
    "devices.types.SHUTTER": "shutter", "devices.types.WINDOW": "window",
    "devices.types.LINK": "garage",
}

VALUE_TYPE_ON_OFF = "values.types.OnOff"
VALUE_TYPE_OPEN_CLOSE = "values.types.OpenClose"
VALUE_TYPE_BRIGHTNESS = "values.types.Brightness"
VALUE_TYPE_LOCK_UNLOCK = "values.types.LockUnlock"
VALUE_TYPE_MULTILEVEL = "values.types.Multilevel"
VALUE_TYPE_BINARY = "values.types.Binary"
VALUE_TYPE_MODES = "values.types.Modes"
VALUE_TYPE_JSON_CONFIG = "values.types.JsonConfig"

ICON_MAP: dict[str, str] = {
    # ── Lights ────────────────────────────────────────────────────────────
    "bulb": "mdi:lightbulb",
    "bulb-on": "mdi:lightbulb-on",
    "bulb-off": "mdi:lightbulb-off",
    "light": "mdi:lightbulb",
    "lamp": "mdi:lamp",
    "led": "mdi:led-on",
    "led-strip": "mdi:led-strip",
    "chandelier": "mdi:chandelier",
    "ceiling-light": "mdi:ceiling-light",
    "floor-lamp": "mdi:floor-lamp",
    "desk-lamp": "mdi:desk-lamp",
    "spotlight": "mdi:spotlight-beam",

    # ── Covers / Gates / Doors ────────────────────────────────────────────
    "gate": "mdi:gate",
    "garage": "mdi:garage",
    "garage-door": "mdi:garage",
    "garage-open": "mdi:garage-open",
    "garage-close": "mdi:garage",
    "door": "mdi:door",
    "door-open": "mdi:door-open",
    "door-close": "mdi:door-closed",
    "door-closed": "mdi:door-closed",
    "sliding-door": "mdi:door-sliding",
    "sliding-gate-open": "mdi:gate-open",
    "sliding-gate-close": "mdi:gate",
    "swing-gate-open": "mdi:gate-open",
    "swing-gate-close": "mdi:gate",
    "sliding-glass-door-open": "mdi:door-sliding-open",
    "sliding-glass-door-close": "mdi:door-sliding",
    "shutter": "mdi:window-shutter",
    "shutter-open": "mdi:window-shutter-open",
    "shutter-close": "mdi:window-shutter",
    "shutter-metal-open": "mdi:window-shutter-open",
    "shutter-metal-close": "mdi:window-shutter",
    "blind": "mdi:blinds",
    "blinds": "mdi:blinds",
    "window": "mdi:window-open",
    "window-open": "mdi:window-open",
    "window-close": "mdi:window-closed",
    "curtains-vertical-open": "mdi:curtains",
    "curtains-vertical-close": "mdi:curtains",
    "curtains-horizontal-open": "mdi:curtains",
    "curtains-horizontal-close": "mdi:curtains",
    "awning": "mdi:storefront-outline",
    "awning-open": "mdi:storefront-outline",
    "awning-close": "mdi:storefront-outline",
    "awning-valance-open": "mdi:storefront-outline",
    "awning-valance-close": "mdi:storefront-outline",
    "barrier": "mdi:boom-gate",
    "barrier-gate-open": "mdi:boom-gate-up",
    "barrier-gate-close": "mdi:boom-gate",
    "pillar-open": "mdi:pillar",
    "pillar-close": "mdi:pillar",
    "falk": "mdi:gate",

    # ── Switches / Plugs ──────────────────────────────────────────────────
    "switch": "mdi:toggle-switch",
    "plug": "mdi:power-plug",
    "socket": "mdi:power-socket-eu",
    "wall-socket-on": "mdi:power-plug",
    "wall-socket-off": "mdi:power-plug-off",
    "power": "mdi:power",
    "outlet": "mdi:power-plug",

    # ── Lock ──────────────────────────────────────────────────────────────
    "lock": "mdi:lock",
    "lock-open": "mdi:lock-open",
    "unlock": "mdi:lock-open",
    "key": "mdi:key",

    # ── Sensors ───────────────────────────────────────────────────────────
    "thermometer": "mdi:thermometer",
    "temperature": "mdi:thermometer",
    "humidity": "mdi:water-percent",
    "magnetic-sensor": "mdi:magnet",
    "motion": "mdi:motion-sensor",
    "motion-sensor": "mdi:motion-sensor",
    "smoke-detector": "mdi:smoke-detector",
    "water-leak": "mdi:water-alert",
    "gas-leak": "mdi:gas-cylinder",
    "sos": "mdi:alert",
    "alarm": "mdi:alarm-light",
    "vibration": "mdi:vibrate",

    # ── HVAC / Climate ────────────────────────────────────────────────────
    "fan": "mdi:fan",
    "thermostat": "mdi:thermostat",
    "ac": "mdi:air-conditioner",
    "air-conditioner": "mdi:air-conditioner",
    "heating": "mdi:radiator",
    "radiator": "mdi:radiator",
    "heating-radiator": "mdi:radiator",
    "heating-room": "mdi:fireplace",
    "water-heater": "mdi:water-boiler",

    # ── Remote ────────────────────────────────────────────────────────────
    "remote": "mdi:remote",
    "remote-control": "mdi:remote",
    "rf-remote": "mdi:remote",

    # ── Cameras ───────────────────────────────────────────────────────────
    "camera": "mdi:cctv",
    "bullet-camera": "mdi:cctv",
    "wall-camera": "mdi:cctv",
    "dome-camera": "mdi:cctv",
    "ptz-camera": "mdi:cctv",
    "video-camera": "mdi:video",

    # ── Weather / Time of day ─────────────────────────────────────────────
    "summer": "mdi:white-balance-sunny",
    "smiling-sun": "mdi:white-balance-sunny",
    "sad-sun": "mdi:weather-partly-cloudy",
    "sunrise": "mdi:weather-sunset-up",
    "snow": "mdi:snowflake",
    "clouds": "mdi:weather-cloudy",
    "fog": "mdi:weather-fog",
    "partly-cloudy-day": "mdi:weather-partly-cloudy",
    "rain": "mdi:weather-rainy",
    "no-rain": "mdi:weather-sunny",
    "wind": "mdi:weather-windy",
    "windsock": "mdi:windsock",
    "windy-weather": "mdi:weather-windy-variant",
    "lightning-bolt": "mdi:lightning-bolt",
    "cloud-lightning": "mdi:weather-lightning",
    "hail": "mdi:weather-hail",
    "haze": "mdi:weather-hazy",
    "spring": "mdi:flower",
    "winter": "mdi:snowflake",

    # ── Moon phases ───────────────────────────────────────────────────────
    "moon-and-stars": "mdi:weather-night",
    "moon": "mdi:moon-waning-crescent",
    "moonrise": "mdi:weather-sunset-up",
    "moonset": "mdi:weather-sunset-down",
    "full-moon": "mdi:moon-full",
    "waxing-gibbous": "mdi:moon-waxing-gibbous",
    "first-quarter": "mdi:moon-first-quarter",
    "waxing-crescent": "mdi:moon-waxing-crescent",
    "new-moon": "mdi:moon-new",
    "waning-crescent": "mdi:moon-waning-crescent",
    "last-quarter": "mdi:moon-last-quarter",
    "waning-gibbous": "mdi:moon-waning-gibbous",

    # ── Time of day / Scenes ──────────────────────────────────────────────
    "night": "mdi:weather-night",
    "night-2": "mdi:weather-night",
    "afternoon": "mdi:white-balance-sunny",
    "morning": "mdi:weather-sunset-up",
    "evening": "mdi:weather-sunset-down",
    "sunset": "mdi:weather-sunset-down",

    # ── Lifestyle scenes ──────────────────────────────────────────────────
    "sleeping-in-bed": "mdi:bed",
    "sleep": "mdi:sleep",
    "traveler": "mdi:account-arrow-right",
    "suitcase": "mdi:bag-suitcase",
    "campfire": "mdi:campfire",
    "beach": "mdi:beach",
    "pool": "mdi:pool",
    "cup": "mdi:coffee",
    "armchair": "mdi:sofa-single",
    "rocking-chair": "mdi:chair-rolling",
    "shower": "mdi:shower",
    "bathtub": "mdi:bathtub",
    "jacuzzi": "mdi:hot-tub",
    "home": "mdi:home",
    "away": "mdi:home-export-outline",
    "party": "mdi:party-popper",
    "movie": "mdi:movie-open",

    # ── Signs ─────────────────────────────────────────────────────────────
    "no-entry": "mdi:cancel",
    "close-sign": "mdi:close-circle",
    "open-sign": "mdi:check-circle",

    # ── Kitchen / Appliances ──────────────────────────────────────────────
    "coffee-maker": "mdi:coffee-maker",
    "popcorn-maker": "mdi:popcorn",
    "cooking": "mdi:stove",
    "cutting-a-carrot": "mdi:knife",
    "fry": "mdi:frying-pan",
    "gas-burner": "mdi:gas-burner",
    "grill": "mdi:grill",
    "kitchen-room": "mdi:stove",
    "electric-stovetop": "mdi:stove",
    "electric-teapot": "mdi:kettle",
    "microwave": "mdi:microwave",
    "fridge": "mdi:fridge",
    "dishwasher": "mdi:dishwasher",
    "toaster": "mdi:toaster",
    "toaster-oven": "mdi:toaster-oven",

    # ── Electronics / Media ───────────────────────────────────────────────
    "laptop": "mdi:laptop",
    "workstation": "mdi:desktop-tower-monitor",
    "monitor": "mdi:monitor",
    "tv": "mdi:television",
    "tv-on": "mdi:television",
    "tv-show": "mdi:television-play",
    "retro-tv": "mdi:television-classic",
    "video": "mdi:video",
    "clapperboard": "mdi:movie-open",
    "video-projector": "mdi:projector",
    "movie-projector": "mdi:projector",
    "popcorn": "mdi:popcorn",
    "movie-theater": "mdi:theater",
    "film-reel": "mdi:filmstrip",
    "music-festival": "mdi:music",
    "radio": "mdi:radio",

    # ── Laundry / Cleaning ────────────────────────────────────────────────
    "washing-machine": "mdi:washing-machine",
    "broom": "mdi:broom",
    "vacuuming": "mdi:robot-vacuum",
    "housekeeper": "mdi:broom",
    "housekeeping": "mdi:broom",
    "human-washing-dishes": "mdi:silverware-clean",
    "laundry-bag": "mdi:tshirt-crew",
    "cleaning-a-surface": "mdi:spray-bottle",
    "cleaning-service": "mdi:spray-bottle",

    # ── Rooms ─────────────────────────────────────────────────────────────
    "babys-room": "mdi:baby-face-outline",
    "bedroom": "mdi:bed",
    "dining-room": "mdi:silverware-fork-knife",
    "dining-room-2": "mdi:silverware-fork-knife",
    "office": "mdi:desk",

    # ── Celebrations / Holidays ───────────────────────────────────────────
    "gift": "mdi:gift",
    "cute-cake": "mdi:cake",
    "confetti": "mdi:confetti",
    "festival": "mdi:party-popper",
    "love": "mdi:heart",
    "small-hearts": "mdi:heart-multiple",
    "fire-heart": "mdi:heart-flash",
    "witch": "mdi:wizard-hat",
    "jack-lantern": "mdi:halloween",
    "christmas-tree": "mdi:pine-tree",
    "christmas-stocking": "mdi:stocking",
    "christmas-gift": "mdi:gift",
    "the-toast": "mdi:glass-cocktail",
    "firework-explosion": "mdi:firework",

    # ── Print / Office ────────────────────────────────────────────────────
    "print": "mdi:printer",
    "copy-machine": "mdi:printer",
    "shredder": "mdi:delete-variant",

    # ── Outdoor / Garden ──────────────────────────────────────────────────
    "bell": "mdi:bell",
    "doorbell": "mdi:doorbell",
    "speaker": "mdi:speaker",
    "irrigation": "mdi:sprinkler",
    "garden": "mdi:flower",
    "tree": "mdi:tree",
    "car": "mdi:car",
    "ev-charger": "mdi:ev-station",

    # ── Network / Energy ──────────────────────────────────────────────────
    "wifi": "mdi:wifi",
    "signal": "mdi:signal",
    "battery": "mdi:battery",
    "energy": "mdi:flash",
    "meter": "mdi:meter-electric",
    "water": "mdi:water",
}

DEVICE_TYPE_ICON: dict[str, str] = {
    "devices.types.LIGHT": "mdi:lightbulb",
    "devices.types.DIMMER": "mdi:lightbulb",
    "devices.types.SWITCH": "mdi:toggle-switch",
    "devices.types.PLUG": "mdi:power-plug",
    "devices.types.DOOR": "mdi:door",
    "devices.types.GARAGE": "mdi:garage",
    "devices.types.SHUTTER": "mdi:window-shutter",
    "devices.types.WINDOW": "mdi:window-open",
    "devices.types.LOCK": "mdi:lock",
    "devices.types.FAN": "mdi:fan",
    "devices.types.THERMOSTAT": "mdi:thermostat",
    "devices.types.SENSOR": "mdi:eye",
    "devices.types.MOTION_SENSOR": "mdi:motion-sensor",
    "devices.types.ZB_MOTION_SENSOR": "mdi:motion-sensor",
    "devices.types.LINK": "mdi:gate",
    "devices.types.RF_CONTROLLER": "mdi:remote",
    "devices.types.RF_REMOTE": "mdi:remote",
}

# ── Shutter modes ─────────────────────────────────────────────────────────
SHUTTER_MODE_SHUTTER = 0       # Normal shutter (open/close/position)
SHUTTER_MODE_RELAY = 1         # Two independent relays (switches)
SHUTTER_MODE_VENETIAN = 2      # Venetian blind (position + tilt/rotation)

# Value IDs used internally by shutter devices (not exposed as entities)
SHUTTER_CONFIG_VALUE_IDS: set[str] = {
    "mode", "blind_rotation", "show_mode", "labels",
    "relay_01", "relay_02", "sensor_open", "sensor_close",
}

PLATFORMS: list[str] = [
    "cover", "light", "switch", "lock", "sensor",
    "binary_sensor", "scene", "fan", "climate",
]
