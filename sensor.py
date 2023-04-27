import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import SensorEntity
from aiohttp.client_exceptions import ClientError
from aiohttp.web import HTTPForbidden
from .const import (DOMAIN, POWERSHAPER_AUTH_URL, POWERSHAPER_BASE_SENSOR_URL)
_LOGGER = logging.getLogger(__name__)


async def async_get_consent_uuid(hass, api_token) -> str:
    """Get the consnet_uuid using the api token provided by the user"""

    session = async_get_clientsession(hass)
    api_url = POWERSHAPER_AUTH_URL
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }

    async with session.get(api_url, headers=headers) as response:
        response_data = await response.json()

    if response.status == 403:
        _LOGGER.debug(
            f"Invalid or no authorisation token supplied, response status: {response.status}")
        raise HTTPForbidden

    if response.status != 200:
        _LOGGER.debug(
            f"Error occurred whilst fetching Powershaper API, response status: {response.status}")
        raise ClientError

    _LOGGER.debug(
        f"Sucessfully fetched the consent_uuid from the powershaper api. Consent UUID: {response_data[0]['consent_uuid']}")

    return response_data[0]['consent_uuid']


async def async_setup_entry(hass, entry, async_add_entities):
    """Add sensor entities for the integration."""
    entities = []
    # consent_uuid = entry.data['consent_uuid']

    api_token = entry.data['api_token']

    # fetch the consent_uuid
    try:
        consent_uuid = await async_get_consent_uuid(hass, api_token)
    except HTTPForbidden:
        _LOGGER.debug("error occurred")

    # Create a list of sensor entities
    gas_meter = GasMeter(entry.data, "gas",
                         86400, consent_uuid, api_token)

    entities.append(gas_meter)
    # Add the sensors to Home Assistant
    async_add_entities(entities)

    # Store the client and sensors in the hass data for later use
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "entry_data":  entry.data, "entities": entities}

    return True


def url_builder(sensor_type: str, consent_uuid: str) -> str:
    return POWERSHAPER_BASE_SENSOR_URL + consent_uuid + "/" + sensor_type + "?start=2023-04-24&end=2023-04-24&aggregate=day&tz=UTC"


class GasMeter(SensorEntity):
    """Representation of a gas sensor."""

    def __init__(self,  entry_data, sensor_type, scan_interval, consent_uuid, api_token):
        """Initialize the sensor."""
        self.entry_data = entry_data
        self._sensor_type = sensor_type
        self._state = None
        self._scan_interval = scan_interval
        self._consent_uuid = consent_uuid
        self._api_token = api_token

    async def async_update(self):
        """Fetch the latest data from the API."""

        try:
            session = async_get_clientsession(self.hass)
            api_url = url_builder(self._sensor_type, self._consent_uuid)
            headers = {
                'Authorization': f'Token {self._api_token}',
                'Content-Type': 'application/json'
            }

            async with session.get(api_url, headers=headers) as response:
                response_data = await response.json()

            _LOGGER.debug(f"GAS response_data: {response_data}")

        except Exception as error:
            _LOGGER.error("Error fetching data: %s", error)

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
