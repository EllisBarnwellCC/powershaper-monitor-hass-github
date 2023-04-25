"""Config flow for Powershaper integration."""
from typing import Any
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (DOMAIN, API_TOKEN_LENGTH, URL_CONSENT_UUID)
from aiohttp.client_exceptions import ClientError
from aiohttp.web import HTTPForbidden

import logging
import voluptuous as vol


DATA_SCHEMA = {vol.Required("api_token"): str}

_LOGGER = logging.getLogger(__name__)


async def async_get_consent_uuid(hass: HomeAssistant, user_input: dict[str, Any]) -> str:
    """Request the consent_uuid using the API token provided by the user"""

    api_token = user_input['api_token']
    if len(api_token) != API_TOKEN_LENGTH:
        _LOGGER.debug(
            f"Invalid token length. Expected: {API_TOKEN_LENGTH} | Received: {len(api_token)}")
        raise ValueError

    session = async_get_clientsession(hass)
    api_url = URL_CONSENT_UUID
    headers = {
        'Authorization': f'Token {api_token}',
        'Content-Type': 'application/json'
    }

    async with session.get(api_url, headers=headers) as response:
        response_data = await response.json()

    if response.status == 403:
        _LOGGER.debug(
            f"Invalid or no authorisation token supplied, response status: {response.status}")
        raise HTTPForbidden

    if response.status == 426:
        _LOGGER.debug(
            f"Call rate quota exceeded, response status: {response.status}")
        raise QuotaExceeded

    if response.status != 200:
        _LOGGER.debug(
            f"Error occurred whilst fetching Powershaper API, response status: {response.status}")
        raise ClientError

    _LOGGER.debug(
        f"Sucessfully fetched the consent_uuid from the powershaper api. Consent UUID: {response_data[0]['consent_uuid']}")

    # return the consent_uuid required to access user's powershaper service
    return response_data[0]['consent_uuid']


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the PowerShaper."""

    async def async_step_user(self, user_input=None):

        errors = {}

        if user_input is not None:
            try:
                consent_uuid = await async_get_consent_uuid(self.hass, user_input)
            except ValueError:
                errors["base"] = "invalid_token_length"
            except HTTPForbidden:
                errors['base'] = "invalid_access"
            except QuotaExceeded:
                errors['base'] = "quota_exceeded"
            except ClientError:
                errors['base'] = "client_error"
            except Exception:
                errors['base'] = "unknown_error"
            else:
                return self.async_create_entry(title="powershaper", data=consent_uuid)

        return self.async_show_form(step_id="user",
                                    data_schema=vol.Schema(DATA_SCHEMA),
                                    errors=errors
                                    )


class QuotaExceeded(exceptions.HomeAssistantError):
    """Call rate quota exceeded."""
