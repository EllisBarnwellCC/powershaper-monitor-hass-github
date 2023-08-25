import logging
import httpx
from .const import COFYCLOUD_TOKEN_URL

_LOGGER = logging.getLogger(__name__)

async def aysnc_push_half_hourly_data(value: float, timestamp: str, sensor):
    if sensor.cofycloud_token == "":
        _LOGGER.debug("First time we've pushed. Set cofycloud token")
        sensor.cofycloud_token = get_cofycloud_token(sensor)

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


## TODO: push the actual data! Should be straightforward now but needs testing
## Also, should change things like text in setup so it's a bit obvious that we need the powershaper monitor API key


# ### TAKEN DIRECTLY FROM COFYBOX-BELINA. NOT IDEAL!!!
# def post_data_to_cofycloud_data_queue(
#     cofyboxinfo: CofyBoxInfo, cofyboxconfig: CofyBoxConfig, payload: str
# ) -> CofyBoxInfoCloudStatus:
#     """
#     Attempt to send data payloads passed to this function upstream to the cofycloud.

#     This data will likely have been received from either the MQTT bus or retrieved from InfluxDB.

#     This assumes that the device has already been provisioned to the cofycloud but this may not be the case.
#     If this is not the case it should log an informative error message.
#     """

#     status = CofyBoxInfoCloudStatus.failed  # TODO: a better status may be possible...

#     _LOGGER.info(f"Polling the CoFyCloud data queue endpoint.")
#     try:
#         headers = {
#             "Authorization": cofyboxinfo.cofycloud.authorization_header_value,
#             "Content-Type": "application/json",
#         }

#         r = httpx.post(
#             cofyboxinfo.cofycloud.assigned_queue, headers=headers, data=payload
#         )
#     except httpx.RequestError as exc:
#         _LOGGER.error(
#             f"An error occurred while polling the CoFyCloud data queue endpoint: {exc.request.url!r} {headers}."
#         )
#         _LOGGER.error(f"Request will be retried at a later time.")
#         status = CofyBoxInfoCloudStatus.disconnected

#     match r.status_code:  # type: ignore
#         case 201:
#             _LOGGER.info(
#                 f"A response was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
#             )
#             status = CofyBoxInfoCloudStatus.connected
#         case 400:
#             _LOGGER.error(
#                 f"A bad status code was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
#             )
#             status = CofyBoxInfoCloudStatus.failed
#         case _:
#             _LOGGER.info(
#                 f"An undefined status code was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
#             )
#             _LOGGER.info(
#                 "This may indicate some sort of problem requiring further investigation."
#             )
#             # TODO: status = CofyBoxInfoCloudStatus.unknown?

#     _LOGGER.info(
#         f"A response was received from the CoFyCloud data queue endpoint: {r.request} / {r.request.headers['Authorization']} / {r.text} / {r.status_code}"
#     )

#     return status