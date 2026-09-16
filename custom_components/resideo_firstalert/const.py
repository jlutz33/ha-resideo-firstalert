"""Constants for the First Alert by Resideo integration."""

from datetime import timedelta

DOMAIN = "resideo_firstalert"

# OAuth Configuration
OAUTH_CLIENT_ID = "SRmiA7CaYi1JgivDZdzzoZu4X5VBogGt"
OAUTH_TOKEN_URL = "https://login.resideo.com/oauth/token"
OAUTH_AUTHORIZE_URL = "https://login.resideo.com/authorize"
OAUTH_AUDIENCE = "https://resideo-prod.auth0.com/api/v2/"
OAUTH_SCOPES = "openid profile email offline_access"

# API Configuration
# Resideo retired api.resideo.com in Sept 2026 (it now answers every call with a canned
# 503 "planned maintenance" body that never clears) and moved the consumer API to this
# host. Paths are unchanged; two extra headers are now required on every call (see
# api.py::_request). Confirmed live: both endpoints below 401 (not 503/404) at this host
# when unauthenticated. Source: sfcodes/ha-resideo v0.3.0, which mapped the same move for
# Resideo's thermostat/leak-detector devices.
API_BASE_URL = "https://api.ha.resideo.com"
API_ACCOUNTS_ENDPOINT = "/ris-public-api/api/v1/accounts"
API_DEVICE_STATE_ENDPOINT = "/ris-public-api/api/v2/devices/smokeDetectors/{device_id}/state"

# Azure APIM subscription key (prod). Mandatory on every api.ha.resideo.com call, not just
# writes - sent unconditionally by the app on every request.
API_SUBSCRIPTION_KEY = "b60885e8a9b44680a29ea1f03452878a"
# The real app's User-Agent, sent on every API call (distinct from the browser-ish UA used
# for the Auth0 web login flow in auth.py).
API_USER_AGENT = "First Alert/2440 CFNetwork/3860.600.12 Darwin/25.5.0"

# Update interval
DEFAULT_SCAN_INTERVAL = 60  # seconds
MIN_SCAN_INTERVAL = 5  # seconds
MAX_SCAN_INTERVAL = 3600  # seconds (1 hour)

# Config keys
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ACCESS_TOKEN = "access_token"
CONF_TOKEN_EXPIRY = "token_expiry"

# Device types
DEVICE_TYPE_SMOKE_DETECTOR = "SmokeDetector"
# productFamily reported in the account listing. Accounts can also contain other
# Resideo devices (for example productFamily "LeakDetector"), which this
# integration does not model and which have no state endpoint on this API.
PRODUCT_FAMILY_SMOKE_DETECTOR = "SmokeDetector"

# Alarm states
ALARM_STATE_IDLE = "idle"
ALARM_STATE_ALARM = "alarm"
ALARM_STATE_GOOD = "good"
ALARM_STATE_LOW = "low"
ALARM_STATE_NONE = "none"
ALARM_STATE_AC = "ac"
ALARM_STATE_BATTERY = "battery"
ALARM_STATE_NOT_SILENCED = "not_silenced"
ALARM_STATE_SILENCED = "silenced"
ALARM_STATE_EOL_NO = "no"
ALARM_STATE_EOL_YES = "yes"
ALARM_STATE_TESTING = "testing"

# Platforms
PLATFORMS = ["binary_sensor", "sensor"]
