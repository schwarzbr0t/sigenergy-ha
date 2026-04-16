"""Constants for the Sigenergy Cloud integration."""

DOMAIN = "sigenergy"

# API
API_BASE_URL = "https://openapi-eu.sigencloud.com"  # default / backward compat

CONF_REGION = "region"
REGION_EU = "eu"
REGION_AP = "ap"
REGION_MEA = "mea"
REGION_CN = "cn"
REGION_ANZ = "anz"
REGION_LA = "la"
REGION_NA = "na"
REGION_JP = "jp"

REGION_URLS = {
    REGION_EU: "https://openapi-eu.sigencloud.com",
    REGION_AP: "https://openapi-apac.sigencloud.com",
    REGION_MEA: "https://openapi-mea.sigencloud.com",
    REGION_CN: "https://openapi-cn.sigencloud.com",
    REGION_ANZ: "https://openapi-aus.sigencloud.com",
    REGION_LA: "https://openapi-la.sigencloud.com",
    REGION_NA: "https://openapi-us.sigencloud.com",
    REGION_JP: "https://openapi-jp.sigencloud.com",
}
AUTH_URL_PASSWORD = "/openapi/auth/login/password"
AUTH_URL_KEY = "/openapi/auth/login/key"
SYSTEM_LIST_URL = "/openapi/system"
SYSTEM_LIST_PAGE_URL = "/openapi/system/page"
DEVICE_LIST_URL = "/openapi/system/{system_id}/devices"
REALTIME_SUMMARY_URL = "/openapi/systems/{system_id}/summary"
ENERGY_FLOW_URL = "/openapi/systems/{system_id}/energyFlow"
DEVICE_REALTIME_URL = "/openapi/systems/{system_id}/devices/{serial_number}/realtimeInfo"
QUERY_MODE_URL = "/openapi/instruction/{system_id}/settings"
SWITCH_MODE_URL = "/openapi/instruction/{system_id}/settings"
ONBOARD_URL = "/openapi/board/onboard"
OFFBOARD_URL = "/openapi/board/offboard"

# Token
TOKEN_EXPIRY_BUFFER = 600  # Refresh 10 minutes before expiry

# Config
CONF_AUTH_METHOD = "auth_method"
CONF_APP_KEY = "app_key"
CONF_APP_SECRET = "app_secret"
CONF_INSTALLATION_ID = "installation_id"
CONF_CACHED_SYSTEMS = "cached_systems"
CONF_CACHED_DEVICES = "cached_devices"

AUTH_METHOD_KEY = "key"
AUTH_METHOD_PASSWORD = "password"

# Update interval
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes (API rate limit: 1 request per 5 min)

# Device types
DEVICE_TYPE_INVERTER = "Inverter"
DEVICE_TYPE_BATTERY = "Battery"
DEVICE_TYPE_GATEWAY = "Gateway"
DEVICE_TYPE_DC_CHARGER = "DcCharger"
DEVICE_TYPE_AC_CHARGER = "AcCharger"
DEVICE_TYPE_METER = "Meter"

# Operating modes
OPERATING_MODE_MSC = 0  # Maximum Self-Consumption
OPERATING_MODE_FFG = 5  # Fully Feed-in to Grid
OPERATING_MODE_VPP = 6  # VPP
OPERATING_MODE_NBI = 8  # Northbound

OPERATING_MODES = {
    0: "Maximum Self-Consumption",
    5: "Fully Feed-in to Grid",
    6: "VPP",
    8: "Northbound",
}

# Battery active modes
BATTERY_ACTIVE_MODES = [
    "charge",
    "discharge",
    "idle",
    "selfConsumption",
    "selfConsumption-grid",
]

# Charge priority
CHARGE_PRIORITY_PV = "PV"
CHARGE_PRIORITY_GRID = "GRID"

# Discharge priority
DISCHARGE_PRIORITY_PV = "PV"
DISCHARGE_PRIORITY_BATTERY = "BATTERY"
