# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Kollektivtrafik Sverige integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KollektivtrafikApiClient
from .const import DOMAIN, CONF_API_KEY
from .coordinator import KollektivtrafikSverigeCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kollektivtrafik Sverige from a config entry."""

    # 1. Initialize shared data and update the global stop count
    hass.data.setdefault(DOMAIN, {})

    # Calculate how many stops are currently configured
    all_entries = hass.config_entries.async_entries(DOMAIN)
    hass.data[DOMAIN]["active_stop_count"] = len(all_entries)

    # 2. Set up the API Client
    session = async_get_clientsession(hass)
    client = KollektivtrafikApiClient(
        api_key=entry.data[CONF_API_KEY],
        session=session,
    )

    # 3. Initialize the Coordinator
    coordinator = KollektivtrafikSverigeCoordinator(hass, client, entry)

    # Fetch initial data so the sensors aren't empty on startup
    await coordinator.async_config_entry_first_refresh()

    # 4. Store the coordinator instance using its entry_id
    # We use a sub-key "instances" to keep it separate from our global count
    hass.data[DOMAIN].setdefault("instances", {})[entry.entry_id] = coordinator

    # Listen for option changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up the coordinator from memory
        if "instances" in hass.data[DOMAIN]:
            hass.data[DOMAIN]["instances"].pop(entry.entry_id)

        # Update the global stop count for remaining instances
        all_entries = hass.config_entries.async_entries(DOMAIN)
        if all_entries:
            hass.data[DOMAIN]["active_stop_count"] = len(all_entries)
        else:
            # If no entries remain, purge the domain data entirely
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
