"""The Powershaper Integration"""
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
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, Platform.SENSOR)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
