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
    CONF_DIRECTION_FILTER,
    CONF_LINE_FILTER,
    CONF_STOP_ID,
    CONF_TIME_WINDOWS,
    DOMAIN,
    ERROR_API_KEY_INVALID,
    ERROR_STOP_NOT_FOUND,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class InvalidStopId(HomeAssistantError):
    """Error to indicate the stop ID is invalid."""


class UnknownError(HomeAssistantError):
    """Catch-all for unexpected issues."""


async def validate_api_key_and_stop(
    hass: HomeAssistant, api_key: str, stop_id: str
) -> None:
    """Validate credentials via API request."""
    client = KollektivtrafikApiClient(api_key, session=async_get_clientsession(hass))
    try:
        await client.get_departures(stop_id)
    except KollektivtrafikApiError as err:
        _LOGGER.error("API validation failed: %s", err)
        if "403" in str(err):
            raise InvalidApiKey from err
        if "404" in str(err):
            raise InvalidStopId from err
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception during validation")
        raise UnknownError from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kollektivtrafik Sverige."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._api_key: str | None = None
        self._stop_id: str | None = None
        self._line_filter: str = ""
        self._direction_filter: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Get API Key."""
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            return await self.async_step_stop()

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_API_KEY): str})
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Get Stop ID and Validate."""
        errors = {}
        if user_input is not None:
            self._stop_id = user_input[CONF_STOP_ID]
            try:
                await validate_api_key_and_stop(self.hass, self._api_key, self._stop_id)
                return await self.async_step_filters()
            except InvalidApiKey:
                errors["base"] = ERROR_API_KEY_INVALID
            except InvalidStopId:
                errors[CONF_STOP_ID] = ERROR_STOP_NOT_FOUND
            except CannotConnect:
                errors["base"] = ERROR_CONNECTION
            except UnknownError:
                errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema({vol.Required(CONF_STOP_ID): str}),
            errors=errors,
        )

    async def async_step_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Set Line and Direction filters."""
        if user_input is not None:
            self._line_filter = user_input.get(CONF_LINE_FILTER, "")
            self._direction_filter = user_input.get(CONF_DIRECTION_FILTER, "")
            return await self.async_step_time_windows()

        return self.async_show_form(
            step_id="filters",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LINE_FILTER): str,
                    vol.Optional(CONF_DIRECTION_FILTER, default=""): str,
                }
            ),
        )

    async def async_step_time_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Finalize with time windows."""
        if user_input is not None:
            unique_id = f"{self._stop_id}_{self._line_filter}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Note: For simplicity in the UI, we're accepting a comma-separated string
            # and converting it to a list for storage.
            raw_windows = user_input.get(CONF_TIME_WINDOWS, "")
            windows = [w.strip() for w in raw_windows.split(",")] if raw_windows else []

            return self.async_create_entry(
                title=f"Stop {self._stop_id} (Line {self._line_filter})",
                data={CONF_API_KEY: self._api_key, CONF_STOP_ID: self._stop_id},
                options={
                    CONF_LINE_FILTER: self._line_filter,
                    CONF_DIRECTION_FILTER: self._direction_filter,
                    CONF_TIME_WINDOWS: windows,
                },
            )

        return self.async_show_form(
            step_id="time_windows",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TIME_WINDOWS, default=""): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options updates."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Convert string back to list before saving
            raw_windows = user_input.get(CONF_TIME_WINDOWS, "")
            user_input[CONF_TIME_WINDOWS] = (
                [w.strip() for w in raw_windows.split(",")] if raw_windows else []
            )

            return self.async_create_entry(title="", data=user_input)

        # Convert list to string for UI editing
        current_windows = self.config_entry.options.get(CONF_TIME_WINDOWS, [])
        windows_str = ",".join(current_windows)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LINE_FILTER): str,
                        vol.Optional(CONF_DIRECTION_FILTER): str,
                        vol.Optional(CONF_TIME_WINDOWS): str,
                    }
                ),
                {**self.config_entry.options, CONF_TIME_WINDOWS: windows_str},
            ),
        )
