import logging
import httpx
import uuid
from typing import Optional
from .const import COFYCLOUD_TOKEN_URL
from pydantic import BaseModel

_LOGGER = logging.getLogger(__name__)

class CofyCloudDQPayload(BaseModel):
    # TODO: import same models from glue for better validation
    deviceId: uuid.UUID
    sensorId: str
    sensorName: Optional[str]
    metric: str
    metricKind: str
    unit: str
    timestamp: str
    value: str

async def aysnc_push_half_hourly_data(value: float, timestamp, sensor):
    if sensor.cofycloud_token == "":
        _LOGGER.debug("First time we've pushed. Set cofycloud token")
        sensor.cofycloud_token = get_cofycloud_token(sensor)

    payload = CofyCloudDQPayload(
        deviceId=sensor.balena_uuid,
        sensorId="powershaper_monitor",
        sensorName="powershaper.total_energy_consumed",
        metric="GridElectricityImport",
        metricKind="delta",
        unit="kWh",
        timestamp=timestamp,
        value=value,
    )

    # _LOGGER.debug("Request payload:")
    # _LOGGER.debug(payload.json(exclude_unset=True))

    post_data_to_cofycloud_data_queue(sensor, payload.json(exclude_unset=True))
    # _LOGGER.debug(f"Pushing data to cofycloud. timestamp: {timestamp}, value: {value}, token: {sensor.cofycloud_token}")


def get_cofycloud_token(sensor):
    _LOGGER.info(f"Preparing request. balena_uuid: {sensor.balena_uuid}, balena_friendly_name: {sensor.balena_friendly_name}")
    request_params = {
        "registrationToken": sensor.balena_uuid,
        "properties.displayName": sensor.balena_friendly_name,
    }
    try:
        r = httpx.post(COFYCLOUD_TOKEN_URL, params=request_params)
        _LOGGER.info(f"A request was sent: {request_params}")
    except httpx.RequestError as exc:
        _LOGGER.error(
            f"An error occurred while requesting from the DPS endpoint: {exc.request.url!r}."
        )
        _LOGGER.error(f"Request will be retried at a later time.")
    else:
        match r.status_code:  # type: ignore
            case 200:
                sensor.cofycloud_assigned_queue_url = r.json()["serviceBus"]["assignedQueue"]
                sensor.cofycloud_authorization_header_value = r.json()["serviceBus"]["authorizationHeaderValue"]
                _LOGGER.debug(f"Response: {r.json()}")
                _LOGGER.debug(f"Queue: " + sensor.cofycloud_assigned_queue_url)
                _LOGGER.debug(f"Auth header: " + sensor.cofycloud_authorization_header_value)

def post_data_to_cofycloud_data_queue(
    sensor, payload: str
):
    """
    Attempt to send data payloads passed to this function upstream to the cofycloud.

    This data will likely have been received from either the MQTT bus or retrieved from InfluxDB.

    This assumes that the device has already been provisioned to the cofycloud but this may not be the case.
    If this is not the case it should log an informative error message.
    """

    _LOGGER.info(f"Polling the CoFyCloud data queue endpoint.")
    try:
        headers = {
            "Authorization": sensor.cofycloud_authorization_header_value,
            "Content-Type": "application/json",
        }

        r = httpx.post(
            sensor.cofycloud_assigned_queue_url, headers=headers, data=payload
        )
    except httpx.RequestError as exc:
        _LOGGER.error(
            f"An error occurred while polling the CoFyCloud data queue endpoint: {exc.request.url!r} {headers}."
        )
        _LOGGER.error(f"Request will be retried at a later time.")
        return

    match r.status_code:  # type: ignore
        case 200:
            _LOGGER.debug(
                f"A response was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
            )
        case 201:
            _LOGGER.info(
                f"A response was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
            )
        case 400:
            _LOGGER.error(
                f"A bad status code was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
            )
        case _:
            _LOGGER.info(
                f"An undefined status code was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
            )
            _LOGGER.info(
                "This may indicate some sort of problem requiring further investigation."
            )

    _LOGGER.info(
        f"A response was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
    )