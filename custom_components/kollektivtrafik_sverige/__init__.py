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
from .coordinator import KollektivtrafikCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kollektivtrafik Sverige from a config entry."""

    # 1. Initialize the API Client
    # We use the session managed by Home Assistant
    session = async_get_clientsession(hass)
    client = KollektivtrafikApiClient(
        api_key=entry.data[CONF_API_KEY],
        session=session,
    )

    # 2. Initialize the coordinator with the client and entry
    coordinator = KollektivtrafikCoordinator(hass, client, entry)

    # 3. Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # 4. Store the coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # 5. Listen for option updates (Filters/Time Windows)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # 6. Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
