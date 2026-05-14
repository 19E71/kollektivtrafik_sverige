# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Kollektivtrafik Sverige integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, CONF_API_KEY
from .coordinator import KollektivtrafikSverigeCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up shared Kollektivtrafik Sverige integration state."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(
        "global",
        {
            "per_stop": {},
            "sensor_created": False,
            "sensor": None,
            "device_info": None,
        },
    )
    return True


def _count_active_stops(hass: HomeAssistant) -> int:
    """Count total stops in all config entries."""
    return sum(
        len(entry.options.get("stops", []))
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kollektivtrafik Sverige from a config entry.

    This setup creates one coordinator per stop loaded from entry.options["stops"].
    All coordinators for this entry are stored in:
        hass.data[DOMAIN][entry.entry_id]["coordinators"]
    """
    # 1. Initialize shared data
    hass.data.setdefault(DOMAIN, {})
    global_data = hass.data[DOMAIN].setdefault(
        "global",
        {"per_stop": {}, "sensor_created": False, "sensor": None, "device_info": None},
    )
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    hass.data[DOMAIN][entry.entry_id].setdefault("coordinators", {})

    # 2. Get API key and stops
    api_key = entry.data[CONF_API_KEY]
    stops = entry.options.get("stops", [])

    # 3. Update active stop count across all entries
    hass.data[DOMAIN]["active_stop_count"] = _count_active_stops(hass)

    # 4. Create global diagnostics device info attached to the config entry
    global_data["device_info"] = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_global")},
        name="Kollektivtrafik Sverige (Diagnostics)",
        manufacturer="19E71",
        model="Integration Diagnostics",
    )

    # 5. Create one coordinator per stop
    coordinators = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    for stop_config in stops:
        coordinator = KollektivtrafikSverigeCoordinator(hass, api_key, stop_config)
        await coordinator.async_config_entry_first_refresh()
        coordinators[stop_config["id"]] = coordinator

    # 6. Listen for option changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # 7. Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up all coordinator state for this entry
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            hass.data[DOMAIN].pop(entry.entry_id, None)

        # Remove stale per-stop diagnostics for this entry's stops
        global_data = hass.data.get(DOMAIN, {}).get("global", {})
        for stop in entry.options.get("stops", []):
            global_data.get("per_stop", {}).pop(stop.get("id"), None)

        # Reset global sensor tracking and device_info so it can be recreated later
        global_data["sensor_created"] = False
        global_data.pop("sensor", None)
        global_data.pop("device_info", None)

        # Update active stop count across remaining entries
        hass.data[DOMAIN]["active_stop_count"] = _count_active_stops(hass)

        # If no entries remain, purge the domain data entirely
        all_entries = hass.config_entries.async_entries(DOMAIN)
        if not all_entries:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
