from unittest import mock
from unittest.mock import AsyncMock, patch
from ..const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_PATH
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import data_entry_flow
import voluptuous as vol

import pytest
from .. import config_flow


@pytest.mark.asyncio
async def test_async_validate_api_token(hass: HomeAssistant):
    """Test a ValueError is raised when the path is not valid."""

    invalid_user_input = {'api_token': "invalid-token"}
    with pytest.raises(ValueError):
        await config_flow.async_validate_api_token(hass, invalid_user_input)

# More test coverage to add
