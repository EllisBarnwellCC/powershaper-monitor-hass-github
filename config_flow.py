"""Config flow for Powershaper integration."""
from typing import Any
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (DOMAIN, API_TOKEN_LENGTH, CONSENT_UUID_URL)

import logging
import voluptuous as vol


DATA_SCHEMA = {vol.Required("api_token"): str}

_LOGGER = logging.getLogger(__name__)


async def async_get_consent_uuid(hass: HomeAssistant, api_token: str) -> str:

    if len(api_token) != API_TOKEN_LENGTH:
        _LOGGER.debug(
            f"Wrong token length. Expected: {API_TOKEN_LENGTH} | Received: {len(api_token)}")
        raise ValueError

    session = async_get_clientsession(hass)
    api_url = CONSENT_UUID_URL
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }

    try:
        async with session.get(api_url, headers=headers) as response:
            response_data = await response.json()
    except Exception as e:
        _LOGGER.debug(
            f"Failed to fetch data from the Powershaper API: {e}")

    if response.status != 200:
        _LOGGER.debug("Failed to fetch from the Powershaper API, response status: {} ".format(
            response.status))
        raise Exception(
            f"API request failed with status code {response.status}")

    return response_data[0]['consent_uuid']


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the PowerShaper."""

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                consent_uuid = await async_get_consent_uuid(self.hass, user_input['api_token'])
                _LOGGER.debug("consent_uuid: {}".format(consent_uuid))
            except ValueError:
                errors["base"] = "invalid_token_length"
            else:
                return self.async_create_entry(title="powershaper", data=consent_uuid)

        # Show the form to the user
        return self.async_show_form(step_id="user",
                                    data_schema=vol.Schema(DATA_SCHEMA),
                                    errors=errors
                                    )
