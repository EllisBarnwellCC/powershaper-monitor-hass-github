"""
The Powershaper monitor Integration

Used for pulling meter data from the powershaper monitor API and adding as a sensor
using the hass history API

Authored by Robert Sahakyan
"""
from __future__ import annotations
from homeassistant.helpers.typing import ConfigType

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from .const import DOMAIN
import logging

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "powershaper"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Powershaper platform."""

    api_token = entry.data['api_token']

    # Store the client and sensors in the hass data for later use
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {"api_token": api_token}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"Unloading entry: {entry.entry_id}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, Platform.SENSOR)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
