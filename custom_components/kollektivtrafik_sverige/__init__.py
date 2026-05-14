# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Kollektivtrafik Sverige integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
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
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # 2. Get API key and stops
    api_key = entry.data[CONF_API_KEY]
    stops = entry.options.get("stops", [])

    # 3. Update active stop count across all entries
    hass.data[DOMAIN]["active_stop_count"] = _count_active_stops(hass)

    # 4. Create global diagnostics device info attached to the integration once.
    if global_data.get("device_info") is None:
        global_data["device_info"] = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_global")},
            name="Kollektivtrafik Sverige (Diagnostics)",
            manufacturer="19E71",
            model="Integration Diagnostics",
        )

    # 5. Reuse or create coordinators for this entry
    if "coordinators" not in entry_data:
        entry_data["coordinators"] = {}

    coordinators = entry_data["coordinators"]
    stop_ids_now = {stop["id"] for stop in stops}
    stop_ids_before = set(coordinators.keys())

    # Remove coordinators for stops that were deleted
    for stop_id in stop_ids_before - stop_ids_now:
        coordinators.pop(stop_id, None)

    # Create new coordinators, or keep existing ones
    for stop_config in stops:
        stop_id = stop_config["id"]
        if stop_id not in coordinators:
            coordinator = KollektivtrafikSverigeCoordinator(hass, api_key, stop_config)
            await coordinator.async_config_entry_first_refresh()
            coordinators[stop_id] = coordinator

    # 6. Listen for option changes (only once)
    if "reload_listener_registered" not in entry_data:
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        entry_data["reload_listener_registered"] = True

    # 7. Forward entry setup to platforms (only once)
    if "platforms_forwarded" not in entry_data:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry_data["platforms_forwarded"] = True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up all devices and entities."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        global_data = domain_data.get("global", {})
        entry_data = domain_data.get(entry.entry_id, {})
        entry_coordinators = entry_data.get("coordinators", {})

        # 1. Remove per-stop devices from device registry
        dev_reg = dr.async_get(hass)
        for stop in entry.options.get("stops", []):
            stop_id = stop.get("id")
            # Remove per-stop device
            device = dev_reg.async_get_device(
                identifiers={(DOMAIN, f"{entry.entry_id}_{stop_id}")}
            )
            if device:
                dev_reg.async_remove_device(device.id)
            # Remove stale per-stop diagnostics
            global_data.get("per_stop", {}).pop(stop_id, None)

        # 2. Unregister entry coordinators from global sensor if it exists
        global_sensor = global_data.get("sensor")
        if global_sensor is not None and entry_coordinators:
            if hasattr(global_sensor, "unregister_coordinators"):
                global_sensor.unregister_coordinators(entry_coordinators)

        # 3. Check if other entries remain
        other_entries = [
            config_entry
            for config_entry in hass.config_entries.async_entries(DOMAIN)
            if config_entry.entry_id != entry.entry_id
        ]

        # 4. If no other entries, remove global sensor device and reset global state
        if not other_entries:
            # Remove global diagnostics device from registry
            global_device = dev_reg.async_get_device(
                identifiers={(DOMAIN, f"{entry.entry_id}_global")}
            )
            if global_device:
                dev_reg.async_remove_device(global_device.id)
            # Clear all domain data
            hass.data.pop(DOMAIN, None)

        # 5. Clean up this entry's data
        if entry.entry_id in domain_data:
            domain_data.pop(entry.entry_id, None)

        # 6. Update active stop count
        if DOMAIN in hass.data:
            hass.data[DOMAIN]["active_stop_count"] = _count_active_stops(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
