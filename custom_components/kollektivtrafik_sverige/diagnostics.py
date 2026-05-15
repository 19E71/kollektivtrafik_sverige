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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.loader import async_get_integration

from .const import CONF_API_KEY, DOMAIN

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

    # 1. Fetch relevant objects from hass.data
    domain_data = hass.data.get(DOMAIN, {})
    coordinators = domain_data.get(entry.entry_id, {}).get("coordinators", {})
    global_data = domain_data.get("global", {})
    per_stop_diagnostics = global_data.get("per_stop", {})
    entry_per_stop = {
        stop_id: per_stop_diagnostics.get(stop_id, {})
        for stop_id in coordinators.keys()
    }

    # 2. Integration metadata
    integration = await async_get_integration(hass, DOMAIN)

    # 3. Calculate Global Aggregations (matches logic in sensor_global.py)
    instances = coordinators.values()
    all_stop_stats = per_stop_diagnostics.values()

    aggregated_throttle = max(
        (coord.quota.throttle_factor() for coord in instances), default=1.0
    )
    aggregated_next_poll = min(
        (
            item.get("next_poll_seconds")
            for item in all_stop_stats
            if item.get("next_poll_seconds") is not None
        ),
        default=None,
    )
    aggregated_service_gap = any(item.get("service_gap") for item in all_stop_stats)
    aggregated_time_window = any(
        item.get("time_window_active") for item in all_stop_stats
    )
    aggregated_filtered_departures = sum(
        item.get("filtered_departures", 0) for item in all_stop_stats
    )

    # 4. Prepare Diagnostics Structure
    diagnostics: dict[str, Any] = {
        "integration": {
            "version": integration.version,
            "home_assistant_version": HA_VERSION,
        },
        "config_entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
            "unique_id": entry.unique_id,
        },
        "coordinators": {
            stop_id: {
                "last_update_success": coordinator.last_update_success,
                "last_exception": (
                    str(coordinator.last_exception)
                    if coordinator.last_exception
                    else None
                ),
                "departures_count": (
                    len(coordinator.data.get("departures", []))
                    if coordinator.data
                    else 0
                ),
                "next_poll_seconds": (
                    coordinator.data.get("next_poll_seconds")
                    if coordinator.data
                    else None
                ),
                "filtered_departures": entry_per_stop.get(stop_id, {}).get(
                    "filtered_departures"
                ),
                "service_gap": entry_per_stop.get(stop_id, {}).get("service_gap"),
                "time_window_active": entry_per_stop.get(stop_id, {}).get(
                    "time_window_active"
                ),
                "polling_mode": entry_per_stop.get(stop_id, {}).get("polling_mode"),
                "throttle_factor": coordinator.quota.throttle_factor(),
            }
            for stop_id, coordinator in coordinators.items()
        },
        "global_diagnostics": {
            "active_stop_count": domain_data.get("active_stop_count", 0),
            "aggregated_throttle": aggregated_throttle,
            "aggregated_next_poll": aggregated_next_poll,
            "aggregated_service_gap": aggregated_service_gap,
            "aggregated_time_window": aggregated_time_window,
            "aggregated_filtered_departures": aggregated_filtered_departures,
            "per_stop": per_stop_diagnostics,
            "device_info": global_data.get("device_info"),
        },
        "entities": {},
        "global_sensors": {},
    }

    # 5. Entity registry listing for THIS config entry
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    for entity in entities:
        state = hass.states.get(entity.entity_id)
        if state:
            diagnostics["entities"][entity.entity_id] = {
                "state": state.state,
                "attributes": async_redact_data(dict(state.attributes), TO_REDACT),
                "last_updated": state.last_updated.isoformat(),
            }

    # 6. Global sensor diagnostics
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "global_diagnostics")})

    if device:
        global_entities = er.async_entries_for_device(ent_reg, device.id)
        for entity in global_entities:
            state = hass.states.get(entity.entity_id)
            if state:
                diagnostics["global_sensors"][entity.entity_id] = {
                    "state": state.state,
                    "attributes": async_redact_data(dict(state.attributes), TO_REDACT),
                    "last_updated": state.last_updated.isoformat(),
                    "icon": state.attributes.get("icon"),
                }

    return diagnostics
