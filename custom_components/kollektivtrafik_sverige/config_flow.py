# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Config flow for Kollektivtrafik Sverige integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KollektivtrafikApiClient, KollektivtrafikApiError
from .const import (
    CONF_API_KEY,
    DOMAIN,
    ERROR_API_KEY_INVALID,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    PROJECT_LINK,
    REALTIME_API_LINK,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


async def validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate ONLY the API key using a known stop ID (Stockholm C)."""
    client = KollektivtrafikApiClient(api_key, session=async_get_clientsession(hass))
    try:
        # 740000001 is a permanent ID for testing
        await client.get_departures("740000001")
    except KollektivtrafikApiError as err:
        if "403" in str(err):
            raise InvalidApiKey from err
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kollektivtrafik Sverige."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Get and Verify API Key."""
        errors = {}
        if user_input is not None:
            try:
                await validate_api_key(self.hass, user_input[CONF_API_KEY])

                # Ensure only one config entry exists
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Kollektivtrafik Sverige",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                    options={"stops": []},
                )
            except InvalidApiKey:
                errors["base"] = ERROR_API_KEY_INVALID
            except CannotConnect:
                errors["base"] = ERROR_CONNECTION
            except Exception:
                _LOGGER.exception("Unexpected error during API key validation")
                errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={
                "project_link": PROJECT_LINK,
                "realtime_api_link": REALTIME_API_LINK,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow for this handler."""
        from .options_flow import OptionsFlowHandler

        return OptionsFlowHandler(config_entry)
