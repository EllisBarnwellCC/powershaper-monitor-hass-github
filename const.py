"""
Constants for the Powershaper integration.

Authored by Robert Sahakyan
"""

DOMAIN = "powershaper_monitor"

API_TOKEN_LENGTH = 40
AGGREGATE_TYPE_ALL = "all"
AGGREGATE_TYPE_HOUR = "hour"

POWERSHAPER_AUTH_URL = "https://app.powershaper.io/meters/api/v1/meters/"
POWERSHAPER_BASE_SENSOR_URL = "https://app.powershaper.io/meters/api/v1/meter/"

ICON_GAS_METER = "mdi:meter-gas"
ICON_ELECTRICITY_METER = "mdi:meter-electric"
ICON_MOLECULE_CO2 = "mdi:molecule-co2"

SENSOR_TYPE_GAS = "gas"
SENSOR_TYPE_ELECTRICITY = "electricity"
SENSOR_TYPE_CARBON = "elec_carbon"

MEASUREMENT_UNIT_KG = "kg"

# configurable
DATA_REFRESH_INTERVAL = 7
