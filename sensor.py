import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import SensorEntity

from .const import (DOMAIN, URL_BASE)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add sensor entities for the integration."""
    entities = []
    # consent_uuid = entry.data['consent_uuid']

    # fetch the consent_uuid
    api_token = entry.data['api_token']

    _LOGGER.debug(f"api_token: {api_token}")
    session = async_get_clientsession(hass)
    api_url = URL_BASE
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }

    _LOGGER.debug(f"headers: {headers}")

    async with session.get(api_url, headers=headers) as response:
        response_data = await response.json()

    _LOGGER.debug(f"response_data: {response_data}")

    # Create a list of sensor entities

    gasEntity = GasEntity(entry.data, "gas", 60)

    entities.append(gasEntity)
    # Add the sensors to Home Assistant
    async_add_entities(entities)

    # Store the client and sensors in the hass data for later use
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "entry_data":  entry.data, "entities": entities}

    return True


def url_builder(sensor_type: str, consent_uuid: str) -> str:
    return URL_BASE + consent_uuid + "/" + sensor_type + "?start=2023-04-24&end=2023-04-25&aggregate=none&tz=UTC"


class GasEntity(SensorEntity):
    """Representation of a gas sensor."""

    def __init__(self,  entry_data, sensor_type, scan_interval):
        """Initialize the sensor."""
        self.entry_data = entry_data
        self._sensor_type = sensor_type
        self._state = None
        self._scan_interval = scan_interval

    async def async_update(self):
        """Fetch the latest data from the API."""

        # api_toke = self.entry_data['']
        # try:

        #     # session = async_get_clientsession(hass)
        #     # api_url = url_builder(self._sensor_type)
        #     # headers = {
        #     #     'Authorization': f'Token {api_token}',
        #     #     'Content-Type': 'application/json'
        #     # }

        #     # async with session.get(api_url, headers=headers) as response:
        #     #     response_data = await response.json()

        #     # with async_timeout.timeout(10):
        #     #     url = f"https://api.powershaper.net/{self._sensor_type}"
        #     #     headers = {"Authorization": f"Bearer {self._api_key}"}
        #     #     response = await self._session.get(url, headers=headers)
        #     #     data = await response.json()

        #     #     if data:
        #     #         self._state = data["value"]
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
        return "mdi:meter-gas"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return "power"
