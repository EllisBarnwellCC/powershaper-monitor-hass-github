import logging
import async_timeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_API_KEY,
)
from .const import DOMAIN
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): str
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add sensor entities for the integration."""
    sensors = []
    consent_uuid = entry.data['consent_uuid']
    _LOGGER.debug(f"Inside sensor.py: consent_uuid: {consent_uuid}")
    # client = CustomAPIClient(api_token)

    # try:
    #     data = await client.get_data()
    # except CustomAPIException as ex:
    #     _LOGGER.error("Error getting data from API: %s", ex)
    #     return False

    # Create a list of sensor entities
    sensor = PowershaperSensor(consent_uuid, "sensor", 60)

    sensors.append(sensor)
    # Add the sensors to Home Assistant
    async_add_entities(sensors)

    # Store the client and sensors in the hass data for later use
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "consent_uuid": consent_uuid, "sensors": sensors}

    return True


class PowershaperSensor(SensorEntity):
    """Representation of a Powershaper sensor."""

    def __init__(self,  consent_uuid, sensor_type, scan_interval):
        """Initialize the sensor."""
        self.consent_uuid = consent_uuid
        self._sensor_type = sensor_type
        self._state = None
        self._scan_interval = scan_interval

    async def async_update(self):
        """Fetch the latest data from the API."""
        # try:
        #     with async_timeout.timeout(10):
        #         url = f"https://api.powershaper.net/{self._sensor_type}"
        #         headers = {"Authorization": f"Bearer {self._api_key}"}
        #         response = await self._session.get(url, headers=headers)
        #         data = await response.json()

        #         if data:
        #             self._state = data["value"]
        # except Exception as error:
        #     _LOGGER.error("Error fetching data: %s", error)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Powershaper {self._sensor_type}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "kWh"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:power-plug"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return "power"
