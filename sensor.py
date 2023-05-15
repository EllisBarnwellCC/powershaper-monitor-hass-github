import datetime
import logging
import random
import time

import pytz
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp.client_exceptions import ClientError
from .const import (DOMAIN, POWERSHAPER_AUTH_URL,
                    POWERSHAPER_BASE_SENSOR_URL, ICON_GAS_METER, ICON_ELECTRICITY_METER, SENSOR_TYPE_GAS, SENSOR_TYPE_ELECTRICITY, SENSOR_TYPE_CARBON, AGGREGATE_TYPE)
from homeassistant.const import DEVICE_CLASS_GAS, UnitOfEnergy
from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.helpers import entity_registry as er
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
    earliest_date_str = response_data[0]['range']['earliest']
    latest_date_str = response_data[0]['range']['latest']
    # earliest_date = datetime.datetime.strptime(earliest_date_str, '%Y-%m-%d')
    # latest_date = datetime.datetime.strptime(latest_date_str, '%Y-%m-%d')

    # _LOGGER.debug(f"earliest_date_str: {earliest_date_str}")
    # _LOGGER.debug(f"latest_date_str: {latest_date_str}")

    # earliest_date_str = earliest_date.strftime('%Y-%m-%d')

    _LOGGER.debug(
        f"Sucessfully fetched the consent_uuid from the powershaper api. Consent UUID: {consent_uuid}")

    # Create a list of sensor entities
    gas_meter = GasMeter(entry.data, SENSOR_TYPE_GAS,
                         consent_uuid, api_token)
    electricity_meter = ElectricityMeter(entry.data, SENSOR_TYPE_ELECTRICITY,
                                         consent_uuid, api_token)

    entities.append(gas_meter)
    entities.append(electricity_meter)

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


async def async_import_historic_data(hass, api_token, consent_uuid, sensor: SensorEntity, current_sum):

    statistics = []
    current_state = 0

    metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": "sensor." + sensor._sensor_type,
        "unit_of_measurement": sensor.unit_of_measurement
    }

    _LOGGER.debug(f"Fetching data for sensory type: {sensor._sensor_type}")
    test_date_start = datetime.datetime.strptime('2023-01-01', '%Y-%m-%d')
    test_date_end = datetime.datetime.strptime('2023-05-01', '%Y-%m-%d')

    api_url = url_builder(
        sensor._sensor_type, consent_uuid, test_date_start, test_date_end, "none")

    # fetch historic data
    start_fetch = time.process_time()
    historic_data = await async_fetch_data(hass, api_token, api_url)
    _LOGGER.debug(f"time to fetch data: {time.process_time() - start_fetch}")

    start_aggregate = time.process_time()
    aggregated_data = await async_aggregate_data(historic_data)
    _LOGGER.debug(
        f"time to aggregate data: {time.process_time() - start_aggregate}")

    start = time.process_time()

    for data_point in aggregated_data:
        current_sum += data_point['energy_kwh']
        statistics.append(
            StatisticData(
                start=data_point['time'],
                state=data_point['energy_kwh'],
                sum=current_sum,
                last_reset=None
            )
        )
        current_state = data_point['energy_kwh']

    _LOGGER.debug(f"time to add statistics: {time.process_time() - start}")

    # Add historic data to statistics
    async_import_statistics(hass, metadata, statistics)
    _LOGGER.debug("Successfully imported statistics")

    return current_state


def url_builder(sensor_type: str, consent_uuid: str, start_date: datetime, end_date: datetime, aggregate: str) -> str:
    """Build a url which is used to fetch the latest data from Powershaper for a given sensor type: gas or electricity."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    return POWERSHAPER_BASE_SENSOR_URL+consent_uuid+"/"+sensor_type+"?start="+start_date_str+"&end="+end_date_str+"&aggregate="+aggregate+"&tz=UTC"


class GasMeter(SensorEntity):
    """Representation of a gas sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry_data, sensor_type,  consent_uuid, api_token):
        """Initialize a gas sensor."""
        self._attr_unique_id = "powershaper"+sensor_type+"123"
        self._state = None
        self._entry_data = entry_data
        self._sensor_type = sensor_type
        self._consent_uuid = consent_uuid
        self._api_token = api_token

    async def async_update(self):
        """Fetch the latest data from the API."""
        try:
            _LOGGER.debug("polling gas")
            # fetch historic data
            current_state = await async_import_historic_data(self.hass, self._api_token, self._consent_uuid, self, 0)
            _LOGGER.debug("Successfully imported gas data")

            # random_number = round(random.uniform(0, 2), 2)
            # Set the state of the sensor

            _LOGGER.debug(f"current_state (gas): {current_state}")
            self._state = current_state

        except Exception as error:
            _LOGGER.error("Error fetching data: %s", error)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._sensor_type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._attr_unit_of_measurement

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_GAS_METER

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._attr_device_class


class ElectricityMeter(SensorEntity):
    """Representation of an electricity sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry_data, sensor_type,  consent_uuid, api_token):
        """Initialize a gas sensor."""
        self._attr_unique_id = "powershaper"+sensor_type+"123"
        self._state = None
        self._entry_data = entry_data
        self._sensor_type = sensor_type
        self._consent_uuid = consent_uuid
        self._api_token = api_token

    async def async_update(self):
        """Fetch the latest data from the API."""
        try:
            _LOGGER.debug("polling electricity meter")
            current_state = await async_import_historic_data(self.hass, self._api_token, self._consent_uuid, self, 0)
            _LOGGER.debug("Successfully imported electricity data")

            _LOGGER.debug(f"current_state (elec): {current_state}")
            self._state = current_state
        except Exception as error:
            _LOGGER.error("Error fetching data: %s", error)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._sensor_type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._attr_unit_of_measurement

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_ELECTRICITY_METER

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._attr_device_class
