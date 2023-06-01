import datetime
import logging
import random
import time
import pytz
from .const import (DOMAIN,
                    POWERSHAPER_AUTH_URL,
                    POWERSHAPER_BASE_SENSOR_URL,
                    ICON_GAS_METER,
                    ICON_ELECTRICITY_METER,
                    ICON_MOLECULE_CO2,
                    SENSOR_TYPE_GAS,
                    SENSOR_TYPE_ELECTRICITY,
                    SENSOR_TYPE_CARBON,
                    AGGREGATE_TYPE_ALL,
                    AGGREGATE_TYPE_HOUR)
from datetime import date
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp.client_exceptions import ClientError
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
    earliest_electricity = response_data[0]['range']['earliest'][:10]
    latest_electricity = response_data[0]['range']['latest'][:10]
    earliest_gas = response_data[1]['range']['earliest'][:10]
    latest_gas = response_data[1]['range']['latest'][:10]

    _LOGGER.debug(
        f"Sucessfully fetched the consent_uuid from the powershaper api. Consent UUID: {consent_uuid}")

    # Create a list of sensor entities
    gas_meter = GasMeter(entry.data, SENSOR_TYPE_GAS,
                         consent_uuid, api_token, earliest_gas, latest_gas)
    electricity_meter = ElectricityMeter(entry.data, SENSOR_TYPE_ELECTRICITY,
                                         consent_uuid, api_token, earliest_electricity, latest_electricity)
    electricity_co2_meter = ElectricityCo2Emissions(entry.data, SENSOR_TYPE_CARBON,
                                                    consent_uuid, api_token, earliest_electricity, latest_electricity)

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


async def async_aggregate_data(data_points, key_type):
    """Aggregate the data to hourly values, since this is the smallest unit supported in the statistics"""
    aggregated_data_points = []
    hour_energy = 0
    prev_hour = None

    for data_point in data_points:
        energy_kwh = data_point[key_type]
        time_str = data_point['time']
        time = datetime.datetime.strptime(
            time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

        if prev_hour is None:
            prev_hour = time.replace(minute=0, second=0, microsecond=0)

        if time.hour != prev_hour.hour:
            aggregated_data_points.append(
                {'time': prev_hour, key_type: hour_energy})
            hour_energy = 0
            prev_hour = time.replace(minute=0, second=0, microsecond=0)

        hour_energy += energy_kwh

    # Append last hour
    aggregated_data_points.append(
        {'time': prev_hour, key_type: hour_energy})

    return aggregated_data_points


async def async_data_orchestrator(hass, sensor: SensorEntity, current_sum, start_date, end_date):

    _LOGGER.debug(f"Fetching data for sensor type: {sensor._sensor_type}")

    api_url = url_builder(
        sensor, sensor._consent_uuid, start_date, end_date, AGGREGATE_TYPE_HOUR)

    # fetch historic data
    historic_data = await async_fetch_data(hass, sensor._api_token, api_url)

    statistics = create_statistics(sensor, historic_data)

    latest_timestamp = None
    statistics = []
    metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": "sensor." + sensor._sensor_type,
        "unit_of_measurement": sensor.unit_of_measurement
    }

    if sensor._sensor_type is SENSOR_TYPE_CARBON:
        key_type = 'carbon_kg'
    else:
        key_type = 'energy_kwh'

    for data_point in historic_data:
        current_sum += data_point[key_type]
        statistics.append(
            StatisticData(
                start=datetime.datetime.strptime(
                    data_point['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC),
                state=data_point[key_type],
                sum=current_sum,
                last_reset=None
            )
        )
        latest_timestamp = data_point['time']

    # Add historic data to statistics
    async_import_statistics(hass, metadata, statistics)
    _LOGGER.debug("Successfully imported statistics")

    return {'sum': current_sum, 'latest_timestamp': latest_timestamp}


async def async_poll_new_data(hass, sensor: SensorEntity):

    today = str(date.today())
    latest_date = sensor._latest[:10]

    api_url = url_builder(sensor, sensor._consent_uuid,
                          latest_date, today, AGGREGATE_TYPE_HOUR)

    response_data = await async_fetch_data(hass, sensor._api_token, api_url)

    response_latest_timestamp = datetime.datetime.strptime(
        response_data[-1]['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

    sensor_latest_timestamp = datetime.datetime.strptime(
        sensor._latest, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC)

    if (response_latest_timestamp > sensor_latest_timestamp):
        _LOGGER.debug(f"response_data: {response_data}")
        return response_data

    return []


def create_statistics(sensor: SensorEntity, data):

    if sensor._sensor_type is SENSOR_TYPE_CARBON:
        key_type = 'carbon_kg'
    else:
        key_type = 'energy_kwh'

    statistics = []
    metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": "sensor." + sensor._sensor_type,
        "unit_of_measurement": sensor.unit_of_measurement
    }

    for data_point in data:
        current_sum += data_point[key_type]
        statistics.append(
            StatisticData(
                start=datetime.datetime.strptime(
                    data_point['time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC),
                state=data_point[key_type],
                sum=current_sum,
                last_reset=None
            )
        )
        latest_timestamp = data_point['time']

    return {'statistics': statistics, 'metadata': metadata}


def url_builder(sensor: SensorEntity, consent_uuid: str, start_date: str, end_date: str, aggregate: str) -> str:
    """Build a url which is used to fetch the latest data from Powershaper for a given sensor type: gas or electricity."""

    # currently only retrieving the carbon_kg from the electricity meter
    if sensor._sensor_type is SENSOR_TYPE_CARBON:
        sensor_type = SENSOR_TYPE_ELECTRICITY
    else:
        sensor_type = sensor._sensor_type

    return POWERSHAPER_BASE_SENSOR_URL+consent_uuid+"/"+sensor_type+"?start="+start_date+"&end="+end_date+"&aggregate="+aggregate+"&tz=UTC"


class GasMeter(SensorEntity):
    """Representation of a gas sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry_data, sensor_type, consent_uuid, api_token, earliest, latest):
        """Initialize a gas sensor."""
        self._attr_unique_id = "powershaper"+sensor_type+"123"
        self._state = None
        self._entry_data = entry_data
        self._sensor_type = sensor_type
        self._consent_uuid = consent_uuid
        self._api_token = api_token
        self._sum = 0
        self._configured = False
        self._earliest = earliest
        self._latest = latest

    async def async_update(self):
        """Fetches historic data upon initialization, with subsequent polls every hour for new data from the Powershaper API."""
        try:
            if not self._configured:
                # fetch historic data upon initialization
                response = await async_data_orchestrator(self.hass, self, self._sum, self._earliest, self._latest)
                self._sum = response['sum']
                self._latest = response['latest_timestamp']
                _LOGGER.debug("Successfully imported historic gas data")
                self._configured = True
            else:
                _LOGGER.debug("polling gas")
                response = await async_poll_new_data(self.hass, self)
                if (response):
                    _LOGGER.debug("new data is available")
                else:
                    _LOGGER.debug("no new data available")
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

    def __init__(self, entry_data, sensor_type, consent_uuid, api_token, earliest, latest):
        """Initialize a Electricity sensor."""
        self._attr_unique_id = "powershaper"+sensor_type+"123"
        self._state = None
        self._entry_data = entry_data
        self._sensor_type = sensor_type
        self._consent_uuid = consent_uuid
        self._api_token = api_token
        self._sum = 0
        self._configured = False
        self._earliest = earliest
        self._latest = latest

    async def async_update(self):
        """Fetches historic data upon initialization, with subsequent polls every hour for new data from the Powershaper API."""
        try:
            if not self._configured:
                # fetch historic data upon initialization
                response = await async_data_orchestrator(self.hass, self, self._sum, self._earliest, self._latest)
                self._sum = response['sum']
                self._latest = response['latest_timestamp']
                _LOGGER.debug(
                    "Successfully imported historic electricity data")
                self._configured = True
            else:
                _LOGGER.debug("polling electricity")
                response = await async_poll_new_data(self.hass, self)
                if (response):
                    _LOGGER.debug("new data is available")
                else:
                    _LOGGER.debug("no new data available")
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


class ElectricityCo2Emissions(SensorEntity):
    """Representation of an electricity carbon sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_unit_of_measurement = "KG"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry_data, sensor_type, consent_uuid, api_token, earliest, latest):
        """Initialize a ElectricityCo2Emissions sensor."""
        self._attr_unique_id = "powershaper"+sensor_type+"123"
        self._state = None
        self._entry_data = entry_data
        self._sensor_type = sensor_type
        self._consent_uuid = consent_uuid
        self._api_token = api_token
        self._sum = 0
        self._configured = False
        self._earliest = earliest
        self._latest = latest

    async def async_update(self):
        """Fetches historic data upon initialization, with subsequent polls every hour for new data from the Powershaper API."""
        try:
            if not self._configured:
                # fetch historic data upon initialization
                response = await async_data_orchestrator(self.hass, self, self._sum, self._earliest, self._latest)
                self._sum = response['sum']
                self._latest = response['latest_timestamp']
                _LOGGER.debug(
                    "Successfully imported historic ElectricityCo2Emissions data")
                self._configured = True
            else:
                _LOGGER.debug("polling ElectricityCo2Emissions")
                response = await async_poll_new_data(self.hass, self)
                if (response):
                    _LOGGER.debug("new data is available")
                else:
                    _LOGGER.debug("no new data available")
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
        return ICON_MOLECULE_CO2

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._attr_device_class
