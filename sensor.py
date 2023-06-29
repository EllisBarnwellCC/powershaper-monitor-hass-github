"""
sensor.py - setup the home assistant sensors for pulling metering data from powershaper

Authored by Robert Sahakyan
"""

from collections import namedtuple
import logging
import pytz
from typing import Any, NamedTuple
from datetime import datetime, timedelta, date
from .const import (DOMAIN,
                    POWERSHAPER_AUTH_URL,
                    POWERSHAPER_BASE_SENSOR_URL,
                    ICON_GAS_METER,
                    ICON_ELECTRICITY_METER,
                    ICON_MOLECULE_CO2,
                    SENSOR_TYPE_GAS,
                    SENSOR_TYPE_ELECTRICITY,
                    SENSOR_TYPE_CARBON,
                    AGGREGATE_TYPE_HOUR,
                    DATA_REFRESH_INTERVAL,
                    MEASUREMENT_UNIT_KG)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp.client_exceptions import ClientError
from homeassistant.const import UnitOfEnergy
from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from cofycloud import aysnc_push_half_hourly_data

SCAN_INTERVAL = timedelta(seconds=3600)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> bool:
    """Add sensor entities for the integration."""

    entities = []
    api_token = entry.data['api_token']

    # fetch auth data from Powershaper's API
    response_data = await async_fetch_data(hass, api_token, POWERSHAPER_AUTH_URL)

    consent_uuid = response_data[0]["consent_uuid"]
    earliest_electricity_date = response_data[0]['range']['earliest'][:10]
    latest_electricity_date = response_data[0]['range']['latest'][:10]
    earliest_gas_date = response_data[1]['range']['earliest'][:10]
    latest_gas_date = response_data[1]['range']['latest'][:10]

    # Create sensor entities
    gas_meter = GasMeter(entry.data, SENSOR_TYPE_GAS,
                         consent_uuid, api_token, earliest_gas_date, latest_gas_date)
    electricity_meter = ElectricityMeter(entry.data, SENSOR_TYPE_ELECTRICITY,
                                         consent_uuid, api_token, earliest_electricity_date, latest_electricity_date)
    electricity_co2_meter = ElectricityCo2Emissions(entry.data, SENSOR_TYPE_CARBON,
                                                    consent_uuid, api_token, earliest_electricity_date, latest_electricity_date)
    entities.append(gas_meter)
    entities.append(electricity_meter)
    entities.append(electricity_co2_meter)

    # Add the sensors to Home Assistant
    async_add_entities(entities, update_before_add=True)

    # Store the client and sensors in the hass data for later use
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "entry_data":  entry.data, "entities": entities}

    return True


async def async_fetch_data(hass, api_token, url) -> dict[str, Any]:
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
            f"Client error while fetching data from Powershaper API: {ex} | response status: {response.status}")
    except Exception as ex:
        _LOGGER.error(
            f"Unexpected exception while fetching data from the Powershaper API: {ex} | response status: {response.status}")

    return response_data


def url_builder(sensor: SensorEntity, consent_uuid: str, start_date: str, end_date: str, aggregate: str) -> str:
    """Build a url which is used to fetch the latest data from Powershaper for a given sensor type: gas or electricity."""

    # currently only retrieving the carbon_kg from the electricity meter
    if sensor.sensor_type is SENSOR_TYPE_CARBON:
        sensor_type = SENSOR_TYPE_ELECTRICITY
    else:
        sensor_type = sensor.sensor_type

    return POWERSHAPER_BASE_SENSOR_URL+consent_uuid+"/"+sensor_type+"?start="+start_date+"&end="+end_date+"&aggregate="+aggregate+"&tz=UTC"


async def async_fetch_historic_data(hass, sensor: SensorEntity) -> dict[str, Any]:
    """Fetches all available historic data for a given sensor"""
    api_url = url_builder(
        sensor, sensor.consent_uuid, sensor.earliest_date, sensor.latest_date, AGGREGATE_TYPE_HOUR)

    historic_data = await async_fetch_data(hass, sensor.api_token, api_url)

    return historic_data


async def async_poll_new_data(hass, sensor: SensorEntity) -> list[Any]:
    """Calls the Powershaper API to check if there is new data available. 

    Returns a list of data or an empty list if no new data is available.
    """
    today = str(date.today())
    latest_date = sensor.latest_date

    api_url = url_builder(sensor, sensor.consent_uuid,
                          latest_date, today, AGGREGATE_TYPE_HOUR)

    response_data = await async_fetch_data(hass, sensor.api_token, api_url)

    response_latest_timestamp = datetime.strptime(
        response_data[-1]['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

    sensor_latest_timestamp = datetime.strptime(
        sensor.latest_timestamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

    new_data = []

    # Since we cannot predict which hour the last timestamp was made available
    # this ensures that only data after the last imported timestamp is added
    if (response_latest_timestamp > sensor_latest_timestamp):
        for data in response_data:

            temp_timestamp = datetime.strptime(
                data['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

            if (temp_timestamp > sensor_latest_timestamp):
                new_data.append(data)

        return new_data

    return []


async def async_import_data(hass, sensor: SensorEntity, data, current_sum) -> NamedTuple:
    """Imports data into Home Assistant's database using the Statistics API."""
    if sensor.sensor_type is SENSOR_TYPE_CARBON:
        key_type = 'carbon_kg'
    else:
        key_type = 'energy_kwh'

    statistics = []
    metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": "sensor." + sensor.sensor_type,
        "unit_of_measurement": sensor.unit_of_measurement
    }

    for data_point in data:
        current_sum += data_point[key_type]
        statistics.append(
            StatisticData(
                start=datetime.strptime(
                    data_point['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC),
                state=data_point[key_type],
                sum=current_sum,
                last_reset=None
            )
        )
        latest_timestamp = data_point['time']
        
        await aysnc_push_half_hourly_data(data_point[key_type], data_point['time'])

    async_import_statistics(hass, metadata, statistics)
    

    ReturnData = namedtuple('ReturnData', ['sum', 'latest_timestamp'])
    return ReturnData(current_sum, latest_timestamp)


def historic_refresh(last_refresh_date) -> bool:
    """A check whether it is time to do a historic data refresh"""
    if (datetime.now() - last_refresh_date >= timedelta(days=DATA_REFRESH_INTERVAL)):
        return True
    return False


class GasMeter(SensorEntity):
    """Representation of a gas sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry_data, sensor_type, consent_uuid, api_token, earliest_date, latest_date):
        """Initialize a gas sensor."""
        self._attr_unique_id = DOMAIN+sensor_type+earliest_date
        self.entry_data = entry_data
        self.sensor_type = sensor_type
        self.consent_uuid = consent_uuid
        self.api_token = api_token
        self.sum = 0
        self.initialized = False
        self.earliest_date = earliest_date
        self.latest_date = latest_date
        self.latest_timestamp = None
        self.last_refresh_date = datetime.now()

    async def async_update(self):
        """Fetches historic data upon initialization, with subsequent polls every hour for new data from the Powershaper API."""
        try:
            if not self.initialized or historic_refresh(self.last_refresh_date):
                historic_data = await async_fetch_historic_data(self.hass, self)
                response = await async_import_data(self.hass, self, historic_data, 0)
                self.sum = response.sum
                self.latest_timestamp = response.latest_timestamp
                self.latest_date = response.latest_timestamp[:10]
                self.last_data_refesh = datetime.now()
                self.initialized = True
                _LOGGER.debug(
                    f"Successfully imported historic {self.sensor_type} data")
            else:
                new_data = await async_poll_new_data(self.hass, self)
                if new_data:
                    _LOGGER.debug(
                        f"New data is available for {self.sensor_type} sensor")
                    response = await async_import_data(self.hass, self, new_data, self.sum)
                    self.sum = response.sum
                    self.latest_timestamp = response.latest_timestamp
                    self.latest_date = response.latest_timestamp[:10]
                else:
                    _LOGGER.debug(
                        f"No new data available for {self.sensor_type}")
        except Exception as error:
            _LOGGER.error("Error updating sensor: %s", error)

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

    def __init__(self, entry_data, sensor_type, consent_uuid, api_token, earliest_date, latest_date):
        """Initialize a Electricity sensor."""
        self._attr_unique_id = DOMAIN+sensor_type+earliest_date
        self.entry_data = entry_data
        self.sensor_type = sensor_type
        self.consent_uuid = consent_uuid
        self.api_token = api_token
        self.sum = 0
        self.initialized = False
        self.earliest_date = earliest_date
        self.latest_date = latest_date
        self.latest_timestamp = None
        self.last_refresh_date = datetime.now()

    async def async_update(self):
        """Fetches historic data upon initialization, with subsequent polls every hour for new data from the Powershaper API."""
        try:
            if not self.initialized or historic_refresh(self.last_refresh_date):
                historic_data = await async_fetch_historic_data(self.hass, self)
                response = await async_import_data(self.hass, self, historic_data, 0)
                self.sum = response.sum
                self.latest_timestamp = response.latest_timestamp
                self.latest_date = response.latest_timestamp[:10]
                _LOGGER.debug(
                    f"Successfully imported historic {self.sensor_type} data")
                self.initialized = True
            else:
                new_data = await async_poll_new_data(self.hass, self)
                if new_data:
                    _LOGGER.debug(
                        f"New data is available for {self.sensor_type} sensor")
                    response = await async_import_data(self.hass, self, new_data, self.sum)
                    self.sum = response.sum
                    self.latest_timestamp = response.latest_timestamp
                    self.latest_date = response.latest_timestamp[:10]
                else:
                    _LOGGER.debug(
                        f"No new data available for {self.sensor_type}")
        except Exception as error:
            _LOGGER.error("Error updating sensor: %s", error)

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
        return ICON_ELECTRICITY_METER

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._attr_device_class


class ElectricityCo2Emissions(SensorEntity):
    """Representation of an electricity carbon sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = MEASUREMENT_UNIT_KG
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry_data, sensor_type, consent_uuid, api_token, earliest_date, latest_date):
        """Initialize a ElectricityCo2Emissions sensor."""
        self._attr_unique_id = DOMAIN+sensor_type+earliest_date
        self.entry_data = entry_data
        self.sensor_type = sensor_type
        self.consent_uuid = consent_uuid
        self.api_token = api_token
        self.sum = 0
        self.initialized = False
        self.earliest_date = earliest_date
        self.latest_date = latest_date
        self.latest_timestamp = None
        self.last_refresh_date = datetime.now()

    async def async_update(self):
        """Fetches historic data upon initialization, with subsequent polls every hour for new data from the Powershaper API."""
        try:
            if not self.initialized or historic_refresh(self.last_refresh_date):
                # fetch historic data upon initialization
                historic_data = await async_fetch_historic_data(self.hass, self)
                response = await async_import_data(self.hass, self, historic_data, 0)
                self.sum = response.sum
                self.latest_timestamp = response.latest_timestamp
                self.latest_date = response.latest_timestamp[:10]
                _LOGGER.debug(
                    f"Successfully imported historic {self.sensor_type} data")
                self.initialized = True
            else:
                new_data = await async_poll_new_data(self.hass, self)
                if new_data:
                    _LOGGER.debug(
                        f"New data is available for {self.sensor_type} sensor")
                    response = await async_import_data(self.hass, self, new_data, self.sum)
                    self.sum = response.sum
                    self.latest_timestamp = response.latest_timestamp
                    self.latest_date = response.latest_timestamp[:10]
                else:
                    _LOGGER.debug(
                        f"No new data available for {self.sensor_type}")
        except Exception as error:
            _LOGGER.error("Error updating sensor: %s", error)

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
        return ICON_MOLECULE_CO2

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._attr_device_class
