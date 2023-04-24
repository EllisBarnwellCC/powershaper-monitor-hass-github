"""Config flow for Powershaper integration."""
from typing import Any
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (DOMAIN, API_TOKEN_LENGTH, CONSENT_UUID_URL)

import requests
import json
import logging
import voluptuous as vol


DATA_SCHEMA = {vol.Required("api_token"): str}

_LOGGER = logging.getLogger(__name__)


async def validate_api_token(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the api token provided."""

    print(data['api_token'])
    if len(data['api_token']) != API_TOKEN_LENGTH:
        raise vol.Invalid(
            "API token must be exactly {} characters".format(API_TOKEN_LENGTH))
    if not data['api_token'].isalnum():
        raise vol.Invalid("API token must only contain letters and numbers")

    return {"title": "testing"}


async def async_get_consent_uuid(hass: HomeAssistant, api_token: str) -> str:

    session = async_get_clientsession(hass)
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }
    api_url = CONSENT_UUID_URL

    async def call_api():
        async with session.get(api_url, headers=headers) as response:
            response_data = await response.json()
            if response.status != 200:
                _LOGGER.debug("Failed to fetch from the Powershaper API, response status: {} ".format(
                    response.status))
                raise Exception(
                    f"API request failed with status code {response.status}")
            return response_data[0]['consent_uuid']

    return await call_api()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the PowerShaper."""

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate the API token here
            try:
                # info = await validate_api_token(self.hass, user_input)
                consent_uuid = await async_get_consent_uuid(self.hass, user_input['api_token'])
                _LOGGER.debug("consent_uuid: {}".format(consent_uuid))
                return self.async_create_entry(title="powershaper", data=consent_uuid)
            except ValueError:
                errors["base"] = "invalid_api_token"
        else:
            # Show the form to the user
            return self.async_show_form(step_id="user",
                                        data_schema=vol.Schema(DATA_SCHEMA),
                                        errors=errors
                                        )
