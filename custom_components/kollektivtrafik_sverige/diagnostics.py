# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Diagnostics support for Kollektivtrafik Sverige integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .api import KollektivtrafikApiClient, KollektivtrafikApiError
from .const import CONF_API_KEY, CONF_STOP_ID, DOMAIN

# Keys to redact from diagnostics output
TO_REDACT = {
    CONF_API_KEY,
    "api_key",
    "key",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Integration metadata
    integration = await async_get_integration(hass, DOMAIN)

    diagnostics: dict[str, Any] = {
        "integration_version": integration.version,
        "home_assistant_version": HA_VERSION,
        "config_entry": {
            "title": entry.title,
            "domain": entry.domain,
            "version": entry.version,
            "source": entry.source,
            "state": entry.state.value,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
            "unique_id": entry.unique_id,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
            "update_interval": str(coordinator.update_interval),
            "data_available": coordinator.data is not None,
        },
        "entities": {},
        "api_test": {},
    }

    # Coordinator data structure (safe, no raw payloads)
    if coordinator.data and isinstance(coordinator.data, dict):
        diagnostics["coordinator"]["data_keys"] = list(coordinator.data.keys())

        if "departures" in coordinator.data:
            deps = coordinator.data["departures"]
            diagnostics["coordinator"]["departures_count"] = len(deps)

            if deps and isinstance(deps[0], dict):
                diagnostics["coordinator"]["departure_structure"] = list(deps[0].keys())

    # Entity registry listing
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    for entity in entities:
        state = hass.states.get(entity.entity_id)
        if state:
            diagnostics["entities"][entity.entity_id] = {
                "state": state.state,
                "attributes": async_redact_data(dict(state.attributes), TO_REDACT),
                "last_changed": (
                    state.last_changed.isoformat() if state.last_changed else None
                ),
                "last_updated": (
                    state.last_updated.isoformat() if state.last_updated else None
                ),
            }

    # API connectivity test
    api_key = entry.data.get(CONF_API_KEY)
    stop_id = entry.data.get(CONF_STOP_ID)

    if api_key and stop_id:
        try:
            async with KollektivtrafikApiClient(api_key) as client:
                start = hass.loop.time()
                result = await client.get_departures(stop_id)
                end = hass.loop.time()

                diagnostics["api_test"] = {
                    "success": True,
                    "response_time_ms": round((end - start) * 1000, 2),
                    "response_structure": {
                        "is_dict": isinstance(result, dict),
                        "keys": (
                            list(result.keys()) if isinstance(result, dict) else None
                        ),
                    },
                    "endpoint_tested": f"departures/{stop_id}",
                }

                # Add sample structure info
                if isinstance(result, dict):
                    for key, value in result.items():
                        if isinstance(value, list):
                            diagnostics["api_test"]["response_structure"][
                                f"{key}_count"
                            ] = len(value)
                            if value and isinstance(value[0], dict):
                                diagnostics["api_test"]["response_structure"][
                                    f"{key}_sample_keys"
                                ] = list(value[0].keys())
                        elif isinstance(value, dict):
                            diagnostics["api_test"]["response_structure"][
                                f"{key}_keys"
                            ] = list(value.keys())

        except KollektivtrafikApiError as err:
            diagnostics["api_test"] = {
                "success": False,
                "error": str(err),
                "error_type": "KollektivtrafikApiError",
                "endpoint_tested": f"departures/{stop_id}",
            }
        except Exception as err:
            diagnostics["api_test"] = {
                "success": False,
                "error": str(err),
                "error_type": type(err).__name__,
                "endpoint_tested": f"departures/{stop_id}",
            }
    else:
        diagnostics["api_test"] = {
            "success": False,
            "error": "Missing API key or stop ID",
            "endpoint_tested": None,
        }

    return diagnostics
