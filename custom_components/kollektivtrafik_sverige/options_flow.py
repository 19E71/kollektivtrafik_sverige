# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Options flow for Kollektivtrafik Sverige integration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KollektivtrafikApiClient, KollektivtrafikApiError
from .const import (
    CONF_API_KEY,
    CONF_DIRECTION_FILTER,
    CONF_LINE_FILTER,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    STOP_LOOKUP_LINK,
)

_LOGGER = logging.getLogger(__name__)


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options flow for managing stops."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self.config_entry = config_entry
        self._selected_stop_id: str | None = None
        self._search_results: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show menu for stop management."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_stop", "edit_stop", "remove_stop"],
            description_placeholders={
                "current_stops": str(len(self.config_entry.options.get("stops", [])))
            },
        )

    async def async_step_add_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to add a new stop."""
        if user_input is not None:
            # User selected a stop from search results
            if "selected_stop" in user_input:
                selected_index = int(user_input["selected_stop"])
                if 0 <= selected_index < len(self._search_results):
                    selected_stop = self._search_results[selected_index]
                    self._selected_stop_id = selected_stop.get("id")
                    return await self.async_step_stop_config()

            # User submitted a search query
            if "search_query" in user_input:
                search_value = user_input["search_query"].strip()
                if not search_value:
                    return self.async_show_form(
                        step_id="add_stop",
                        data_schema=vol.Schema({vol.Required("search_query"): str}),
                        errors={"base": "invalid_search"},
                        description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
                    )

                try:
                    client = KollektivtrafikApiClient(
                        self.config_entry.data[CONF_API_KEY],
                        session=async_get_clientsession(self.hass),
                    )
                    self._search_results = await client.search_stops(search_value)

                    if not self._search_results:
                        return self.async_show_form(
                            step_id="add_stop",
                            data_schema=vol.Schema({vol.Required("search_query"): str}),
                            errors={"base": "no_results"},
                            description_placeholders={
                                "stop_lookup_link": STOP_LOOKUP_LINK
                            },
                        )

                    # Build selection list
                    select_options = {}
                    for idx, stop in enumerate(self._search_results):
                        name = stop.get("name", "Unknown")
                        group_name = stop.get("group_name", "")
                        display = (
                            name if group_name == name else f"{name} ({group_name})"
                        )
                        select_options[str(idx)] = display

                    return self.async_show_form(
                        step_id="add_stop",
                        data_schema=vol.Schema(
                            {vol.Required("selected_stop"): vol.In(select_options)}
                        ),
                        description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
                    )

                except KollektivtrafikApiError:
                    return self.async_show_form(
                        step_id="add_stop",
                        data_schema=vol.Schema({vol.Required("search_query"): str}),
                        errors={"base": ERROR_CONNECTION},
                        description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
                    )
                except Exception:
                    _LOGGER.exception("Unexpected error during stop search")
                    return self.async_show_form(
                        step_id="add_stop",
                        data_schema=vol.Schema({vol.Required("search_query"): str}),
                        errors={"base": ERROR_UNKNOWN},
                        description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
                    )

        # Initial search form
        return self.async_show_form(
            step_id="add_stop",
            data_schema=vol.Schema({vol.Required("search_query"): str}),
            description_placeholders={"stop_lookup_link": STOP_LOOKUP_LINK},
        )

    async def async_step_stop_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure stop details."""
        if user_input is not None:
            stop_config = {
                "id": str(uuid.uuid4()),
                "stop_id": self._selected_stop_id,
                "name": user_input.get("name", "Stop"),
                CONF_LINE_FILTER: user_input.get(CONF_LINE_FILTER, ""),
                CONF_DIRECTION_FILTER: user_input.get(CONF_DIRECTION_FILTER, ""),
            }

            stops = list(self.config_entry.options.get("stops", []))
            stops.append(stop_config)

            await self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, "stops": stops},
            )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="stop_config",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default="Stop"): str,
                    vol.Optional(CONF_LINE_FILTER, default=""): str,
                    vol.Optional(CONF_DIRECTION_FILTER, default=""): str,
                }
            ),
        )

    async def async_step_edit_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select stop to edit."""
        stops = self.config_entry.options.get("stops", [])
        if not stops:
            return self.async_abort(reason="no_stops_to_edit")

        if user_input is not None:
            selected_index = int(user_input["selected_stop"])
            if 0 <= selected_index < len(stops):
                self._selected_stop_id = stops[selected_index]["id"]
                return await self.async_step_edit_stop_config()

        select_options = {
            str(idx): stop.get("name", f"Stop {idx + 1}")
            for idx, stop in enumerate(stops)
        }

        return self.async_show_form(
            step_id="edit_stop",
            data_schema=vol.Schema(
                {vol.Required("selected_stop"): vol.In(select_options)}
            ),
        )

    async def async_step_edit_stop_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit selected stop."""
        stops = [dict(item) for item in self.config_entry.options.get("stops", [])]
        stop = next((s for s in stops if s["id"] == self._selected_stop_id), None)

        if stop is None:
            return self.async_abort(reason="stop_not_found")

        if user_input is not None:
            stop.update(
                {
                    "name": user_input.get("name", stop.get("name", "Stop")),
                    CONF_LINE_FILTER: user_input.get(
                        CONF_LINE_FILTER, stop.get(CONF_LINE_FILTER, "")
                    ),
                    CONF_DIRECTION_FILTER: user_input.get(
                        CONF_DIRECTION_FILTER, stop.get(CONF_DIRECTION_FILTER, "")
                    ),
                }
            )

            await self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, "stops": stops},
            )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_stop_config",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default=stop.get("name", "Stop")): str,
                    vol.Optional(
                        CONF_LINE_FILTER, default=stop.get(CONF_LINE_FILTER, "")
                    ): str,
                    vol.Optional(
                        CONF_DIRECTION_FILTER,
                        default=stop.get(CONF_DIRECTION_FILTER, ""),
                    ): str,
                }
            ),
        )

    async def async_step_remove_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a stop."""
        stops = list(self.config_entry.options.get("stops", []))
        if not stops:
            return self.async_abort(reason="no_stops_to_remove")

        if user_input is not None:
            selected_index = int(user_input["selected_stop"])
            if 0 <= selected_index < len(stops):
                stops.pop(selected_index)

                await self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, "stops": stops},
                )

                return self.async_create_entry(title="", data={})

        select_options = {
            str(idx): stop.get("name", f"Stop {idx + 1}")
            for idx, stop in enumerate(stops)
        }

        return self.async_show_form(
            step_id="remove_stop",
            data_schema=vol.Schema(
                {vol.Required("selected_stop"): vol.In(select_options)}
            ),
            description_placeholders={"warning": "This action cannot be undone."},
        )
