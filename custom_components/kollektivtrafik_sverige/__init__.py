# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Kollektivtrafik Sverige integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator.coordinator import KollektivtrafikSverigeCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kollektivtrafik Sverige from a config entry."""

    # 1. Initialize the coordinator
    coordinator = KollektivtrafikSverigeCoordinator(hass, entry)

    # 2. Perform initial data fetch
    # We use a try/except here or let it raise; async_config_entry_first_refresh
    # handles the setup retry logic automatically for us.
    await coordinator.async_config_entry_first_refresh()

    # 3. Store the coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 4. Listen for option updates (e.g. user changing line filters)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # 5. Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # 1. Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # 2. Shutdown the coordinator (closes the API session safely)
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api.close()

        # 3. Cleanup hass.data
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
