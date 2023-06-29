import logging

_LOGGER = logging.getLogger(__name__)


async def aysnc_push_half_hourly_data(value: float, timestamp: str):
    _LOGGER.debug(f"Pushing data to cofycloud. timestamp: {timestamp}, value: {value}")
