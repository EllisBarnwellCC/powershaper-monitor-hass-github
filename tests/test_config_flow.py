from unittest import mock
from unittest.mock import AsyncMock, patch
from ..const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import data_entry_flow

import pytest
from .. import config_flow


@pytest.mark.asyncio
async def test_async_validate_api_token(hass: HomeAssistant):
    """Test a ValueError is raised when the path is not valid."""

    invalid_user_input = {'api_token': "invalid-token"}
    with pytest.raises(ValueError):
        await config_flow.async_validate_api_token(hass, invalid_user_input)

# More test coverage to add
