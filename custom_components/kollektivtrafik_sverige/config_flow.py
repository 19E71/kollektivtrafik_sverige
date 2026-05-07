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
    PROJECT_LINK,
    REALTIME_API_LINK,
    STOP_LOOKUP_LINK,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class InvalidStopId(HomeAssistantError):
    """Error to indicate the stop ID is invalid."""


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


async def validate_stop_id(hass: HomeAssistant, api_key: str, stop_id: str) -> None:
    """Validate the specific stop ID."""
    client = KollektivtrafikApiClient(api_key, session=async_get_clientsession(hass))
    try:
        await client.get_departures(stop_id)
    except KollektivtrafikApiError as err:
        if "404" in str(err):
            raise InvalidStopId from err
        raise CannotConnect from err


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
        """Step 1: Get and Verify API Key immediately."""
        errors = {}
        if user_input is not None:
            try:
                await validate_api_key(self.hass, user_input[CONF_API_KEY])
                self._api_key = user_input[CONF_API_KEY]
                return await self.async_step_stop()
            except InvalidApiKey:
                errors["base"] = ERROR_API_KEY_INVALID
            except CannotConnect:
                errors["base"] = ERROR_CONNECTION
            except Exception:
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

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Get and Verify Stop ID."""
        errors = {}
        if user_input is not None:
            try:
                await validate_stop_id(
                    self.hass, self._api_key, user_input[CONF_STOP_ID]
                )
                self._stop_id = user_input[CONF_STOP_ID]
                return await self.async_step_filters()
            except InvalidStopId:
                errors[CONF_STOP_ID] = ERROR_STOP_NOT_FOUND
            except CannotConnect:
                errors["base"] = ERROR_CONNECTION
            except Exception:
                errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema({vol.Required(CONF_STOP_ID): str}),
            errors=errors,
            description_placeholders={
                "stop_lookup_link": STOP_LOOKUP_LINK,
            },
        )

    async def async_step_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Set Filters."""
        if user_input is not None:
            self._line_filter = user_input.get(CONF_LINE_FILTER, "")
            self._direction_filter = user_input.get(CONF_DIRECTION_FILTER, "")
            return await self.async_step_time_windows()

        return self.async_show_form(
            step_id="filters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LINE_FILTER, default=""): str,
                    vol.Optional(CONF_DIRECTION_FILTER, default=""): str,
                }
            ),
        )

    async def async_step_time_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Finalize."""
        if user_input is not None:
            unique_id = f"{self._stop_id}_{self._line_filter}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return options flow."""
        # MODERNISED: We no longer pass config_entry to the constructor
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options updates (Filters and Windows)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            raw_windows = user_input.get(CONF_TIME_WINDOWS, "")
            user_input[CONF_TIME_WINDOWS] = (
                [w.strip() for w in raw_windows.split(",")] if raw_windows else []
            )
            return self.async_create_entry(title="", data=user_input)

        # MODERNISED: self.config_entry is automatically available on the base class
        current_windows = self.config_entry.options.get(CONF_TIME_WINDOWS, [])
        windows_str = ",".join(current_windows)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_LINE_FILTER, default=""): str,
                        vol.Optional(CONF_DIRECTION_FILTER, default=""): str,
                        vol.Optional(CONF_TIME_WINDOWS, default=""): str,
                    }
                ),
                {**self.config_entry.options, CONF_TIME_WINDOWS: windows_str},
            ),
        )
