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

    def __init__(self) -> None:
        """Initialize flow."""
        self._api_key: str | None = None
        self._stop_id: str | None = None
        self._stop_name: str | None = None
        self._search_results: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Get and Verify API Key."""
        errors = {}
        if user_input is not None:
            try:
                await validate_api_key(self.hass, user_input[CONF_API_KEY])
                self._api_key = user_input[CONF_API_KEY]
                return await self.async_step_search()
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

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Search for stops by name."""
        errors = {}
        if user_input is not None:
            search_value = user_input.get("search_query", "").strip()
            if not search_value:
                errors["base"] = "invalid_search"
            else:
                try:
                    client = KollektivtrafikApiClient(
                        self._api_key, session=async_get_clientsession(self.hass)
                    )
                    self._search_results = await client.search_stops(search_value)

                    if not self._search_results:
                        errors["base"] = "no_results"
                    else:
                        return await self.async_step_select()
                except KollektivtrafikApiError:
                    errors["base"] = ERROR_CONNECTION
                except Exception:
                    _LOGGER.exception("Unexpected error during stop search")
                    errors["base"] = ERROR_UNKNOWN

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema({vol.Required("search_query"): str}),
            errors=errors,
            description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Select from search results."""
        if user_input is not None:
            selected_index = int(user_input.get("selected_stop", 0))
            if 0 <= selected_index < len(self._search_results):
                selected_stop = self._search_results[selected_index]
                self._stop_id = selected_stop.get("id")
                self._stop_name = selected_stop.get("name")
                return await self.async_step_filters()

        # Build options for the select list
        select_options = {}
        for idx, stop in enumerate(self._search_results):
            name = stop.get("name", "Unknown")
            group_name = stop.get("group_name", "")
            display = f"{name}"
            if group_name and group_name != name:
                display += f" ({group_name})"
            select_options[str(idx)] = display

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {vol.Required("selected_stop"): vol.In(select_options)}
            ),
            description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
        )

    async def async_step_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Set Filters and create entry."""
        if user_input is not None:
            line_filter = user_input.get(CONF_LINE_FILTER, "")
            direction_filter = user_input.get(CONF_DIRECTION_FILTER, "")

            await self.async_set_unique_id(
                f"{self._stop_id}_{line_filter}_{direction_filter}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._stop_name,
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_STOP_ID: self._stop_id,
                },
                options={
                    CONF_LINE_FILTER: line_filter,
                    CONF_DIRECTION_FILTER: direction_filter,
                    CONF_TIME_WINDOWS: [],
                },
            )

        return self.async_show_form(
            step_id="filters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LINE_FILTER, default=""): str,
                    vol.Optional(CONF_DIRECTION_FILTER, default=""): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options updates."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LINE_FILTER,
                        default=self.config_entry.options.get(CONF_LINE_FILTER, ""),
                    ): str,
                    vol.Optional(
                        CONF_DIRECTION_FILTER,
                        default=self.config_entry.options.get(
                            CONF_DIRECTION_FILTER, ""
                        ),
                    ): str,
                }
            ),
        )
