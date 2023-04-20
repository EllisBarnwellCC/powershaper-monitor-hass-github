"""Config flow for Powershaper integration."""
from typing import Any
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from .const import DOMAIN

import voluptuous as vol


DATA_SCHEMA = {vol.Required("api_token"): str}


async def validate_api_token(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    if len(data['api_token']) != 40:
        raise vol.Invalid("API token must be exactly 40 characters")
    if not data['api_token'].isalnum():
        raise vol.Invalid("API token must only contain letters and numbers")

    return {"title": "testing"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the PowerShaper."""

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate the API token here
            try:
                info = await validate_api_token(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except ValueError:
                errors["base"] = "invalid_api_token"
        else:
            # Show the form to the user
            return self.async_show_form(step_id="user",
                                        data_schema=vol.Schema(DATA_SCHEMA),
                                        errors=errors
                                        )
