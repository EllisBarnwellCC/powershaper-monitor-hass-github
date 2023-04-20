"""Config flow for Powershaper integration."""
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from .const import DOMAIN

import voluptuous as vol


DATA_SCHEMA = {vol.Required("api_key"): str}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the PowerShaper."""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Validate the API token here
            pass  # todo: validate api token
        else:
            # Show the form to the user
            return self.async_show_form(step_id="user",
                                        data_schema=vol.Schema(DATA_SCHEMA)
                                        )
