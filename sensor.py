import datetime
import logging
import random

import pytz
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp.client_exceptions import ClientError
from aiohttp.web import HTTPForbidden
from .const import (DOMAIN, POWERSHAPER_AUTH_URL, POWERSHAPER_BASE_SENSOR_URL)
from homeassistant.const import DEVICE_CLASS_GAS, UnitOfEnergy
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics, async_import_statistics
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=3600)


_LOGGER = logging.getLogger(__name__)


async def async_fetch_data(hass, api_token, url):
    """Fetch data from Powershaper's API"""

    session = async_get_clientsession(hass)
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }

    try:
        async with session.get(url, headers=headers) as response:
            response_data = await response.json()
    except ClientError as ex:
        _LOGGER.error(
            f"Client error whilst fetching data from Powershaper API: {ex} | response status: {response.status}")

    return response_data


async def async_setup_entry(hass, entry, async_add_entities):
    """Add sensor entities for the integration."""

    entities = []
    api_token = entry.data['api_token']
    # fetch the consent_uuid
    response_data = await async_fetch_data(hass, api_token, POWERSHAPER_AUTH_URL)
    consent_uuid = response_data[0]["consent_uuid"]

    _LOGGER.debug(
        f"Sucessfully fetched the consent_uuid from the powershaper api. Consent UUID: {consent_uuid}")

    # Create a list of sensor entities
    gas_meter = GasMeter(entry.data, DEVICE_CLASS_GAS,
                         consent_uuid, api_token, "unique_id_1")

    entities.append(gas_meter)

    # Add the sensors to Home Assistant
    async_add_entities(entities, update_before_add=True)

    # Store the client and sensors in the hass data for later use
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "entry_data":  entry.data, "entities": entities}

    return True


async def async_aggregate_data(data_points):
    """Aggregate the data to hourly values, since this is the smallest unit supported in the statistics"""
    aggregated_data_points = []
    hour_energy = 0
    prev_hour = None

    for data_point in data_points:
        energy_kwh = data_point['energy_kwh']
        time_str = data_point['time']
        time = datetime.datetime.strptime(
            time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

        if prev_hour is None:
            prev_hour = time.replace(minute=0, second=0, microsecond=0)

        if time.hour != prev_hour.hour:
            aggregated_data_points.append(
                {'time': prev_hour, 'energy_kwh': hour_energy})
            hour_energy = 0
            prev_hour = time.replace(minute=0, second=0, microsecond=0)

        hour_energy += energy_kwh

    # Append last hour
    aggregated_data_points.append(
        {'time': prev_hour, 'energy_kwh': hour_energy})

    return aggregated_data_points


async def async_import_historic_data(hass, api_token, consent_uuid, sensor: SensorEntity):

    statistics = []
    current_state = 0

    metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": "sensor." + sensor.sensor_type,
        "unit_of_measurement": sensor.unit_of_measurement
    }

    test_date = datetime.datetime.strptime('2023-05-02', '%Y-%m-%d')

    # fetch historic data
    api_url = url_builder(
        "gas", consent_uuid, test_date, "none")
    historic_data = await async_fetch_data(hass, api_token, api_url)
    aggregated_data = await async_aggregate_data(historic_data)

    summing = 0
    counter = 1
    for data_point in aggregated_data:
        summing += data_point['energy_kwh']
        _LOGGER.debug(
            f"counter: {counter} | sum:  {summing} | time: {data_point['time']} | energy: { data_point['energy_kwh']}")
        counter += 1
        statistics.append(
            StatisticData(
                start=data_point['time'],
                state=data_point['energy_kwh'],
                sum=summing,
                last_reset=None
            )
        )
        current_state = data_point['energy_kwh']

    # Add historic data to statistics
    async_import_statistics(hass, metadata, statistics)
    _LOGGER.debug("Successfully imported statistics")

    return current_state


def url_builder(sensor_type: str, consent_uuid: str, start_date: datetime, aggregate: str) -> str:
    """Build a url which is used to fetch the latest data from Powershaper for a given sensor type: gas or electricity."""
    date_string = start_date.strftime('%Y-%m-%d')
    # we are using the start date for both 'start' & 'end', since we only want data from the last 24 hours.
    return POWERSHAPER_BASE_SENSOR_URL+consent_uuid+"/"+sensor_type+"?start="+date_string+"&end="+date_string+"&aggregate="+aggregate+"&tz=UTC"


class GasMeter(SensorEntity):
    """Representation of a gas sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self,  entry_data, sensor_type,  consent_uuid, api_token, unique_id):
        """Initialize a gas sensor."""
        self._attr_unique_id = unique_id
        self.entry_data = entry_data
        self.sensor_type = sensor_type
        self.consent_uuid = consent_uuid
        self.api_token = api_token
        self.configured = False

    async def async_update(self):
        """Fetch the latest data from the API."""

        date_today = datetime.date.today()
        api_url = url_builder(
            self.sensor_type, self.consent_uuid, date_today, "none")

        _LOGGER.debug(f"self.configured: {self.configured}")
        try:
            if not self.configured:
                # fetch historic data - occurs only once, when the integration is initially setup & configured.
                _LOGGER.debug("Fetching historic data")
                latest_state = await async_import_historic_data(self.hass, self.api_token, self.consent_uuid, self)
                _LOGGER.debug("Successfully imported historic data")
                self.configured = True
            else:
                _LOGGER.debug("polling")

            # response_data = await async_fetch_data(
            #     self.hass, self._api_token, api_url)

            # _LOGGER.debug(f"GAS response_data: {response_data}")

            # random_number = round(random.uniform(0, 2), 2)

            _LOGGER.debug(f"latest_state: {latest_state}")
            # Set the state of the sensor
            # self.state = latest_state

        except Exception as error:
            _LOGGER.error("Error fetching data: %s", error)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.sensor_type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._attr_unit_of_measurement

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:meter-gas"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._attr_device_class
