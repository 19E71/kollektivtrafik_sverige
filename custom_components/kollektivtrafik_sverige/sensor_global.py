# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. You can obtain one at https://mozilla.org/MPL/2.0/

"""Global diagnostic sensor for Kollektivtrafik Sverige."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant

from .const import DOMAIN, GLOBAL_DAILY_QUOTA, QUOTA_TARGET_USAGE


def _quota_icon(percent: float) -> str:
    if percent <= 0:
        return "mdi:circle-slice-8"
    if percent <= 12:
        return "mdi:circle-slice-7"
    if percent <= 25:
        return "mdi:circle-slice-6"
    if percent <= 37:
        return "mdi:circle-slice-5"
    if percent <= 50:
        return "mdi:circle-slice-4"
    if percent <= 62:
        return "mdi:circle-slice-3"
    if percent <= 75:
        return "mdi:circle-slice-2"
    if percent <= 87:
        return "mdi:circle-slice-1"
    return "mdi:alert-circle-outline"


class GlobalQuotaSensor(SensorEntity):
    """Global quota sensor for integration-wide diagnostics."""

    _attr_has_entity_name = True
    _attr_name = "Global API Quota Usage"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unique_id = "kollektivtrafik_sverige_global_quota"

    def __init__(
        self, hass: HomeAssistant, coordinators: dict[str, Any] | None = None
    ) -> None:
        """Initialize the global quota sensor.

        Args:
            hass: Home Assistant instance
            coordinators: Optional dict of coordinators for this entry
        """
        self._hass = hass
        self._attr_device_info = self._hass.data[DOMAIN]["global"]["device_info"]
        self._listener_cleanup: dict[str, Any] = {}

        # Register initial coordinators if provided
        if coordinators:
            self.register_coordinators(coordinators)

    def register_coordinator(self, coordinator: Any) -> None:
        """Register a coordinator for update callbacks."""
        stop_id = coordinator.stop_config.get("id", "unknown")
        if stop_id in self._listener_cleanup:
            return

        self._listener_cleanup[stop_id] = coordinator.async_add_listener(
            self._handle_coordinator_update
        )

    def unregister_coordinator(self, coordinator: Any) -> None:
        """Unregister a coordinator listener."""
        stop_id = coordinator.stop_config.get("id", "unknown")
        cleanup = self._listener_cleanup.pop(stop_id, None)
        if cleanup is not None:
            cleanup()

    def register_coordinators(self, coordinators: dict[str, Any]) -> None:
        """Register all coordinators for update callbacks."""
        for stop_id, coordinator in coordinators.items():
            self.register_coordinator(coordinator)

    def unregister_coordinators(self, coordinators: dict[str, Any]) -> None:
        """Unregister a set of coordinators."""
        for stop_id, coordinator in coordinators.items():
            self.unregister_coordinator(coordinator)

    async def async_added_to_hass(self) -> None:
        """Register currently active coordinators after entity is added."""
        await super().async_added_to_hass()
        # Collect all coordinators from all config entries
        for entry_id, entry_data in self._hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and "coordinators" in entry_data:
                for coordinator in entry_data["coordinators"].values():
                    self.register_coordinator(coordinator)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up update listeners before removal."""
        for cleanup in self._listener_cleanup.values():
            cleanup()
        self._listener_cleanup.clear()
        await super().async_will_remove_from_hass()

    def _handle_coordinator_update(self) -> None:
        """Refresh sensor state when any coordinator updates."""
        self.async_write_ha_state()

    def _get_all_coordinators(self) -> list[Any]:
        """Get all coordinators from all config entries."""
        all_coordinators = []
        for entry_id, entry_data in self._hass.data.get(DOMAIN, {}).items():
            if isinstance(entry_data, dict) and "coordinators" in entry_data:
                all_coordinators.extend(entry_data["coordinators"].values())
        return all_coordinators

    @property
    def native_value(self) -> float:
        all_coordinators = self._get_all_coordinators()
        total_calls = sum(coord.quota.calls_last_day() for coord in all_coordinators)
        total_safe_quota = int(GLOBAL_DAILY_QUOTA * QUOTA_TARGET_USAGE)

        if total_safe_quota == 0:
            return 0.0

        return round((total_calls / total_safe_quota) * 100, 1)

    @property
    def icon(self) -> str | None:
        return _quota_icon(self.native_value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        global_state = self._hass.data[DOMAIN].get("global", {}).get("per_stop", {})
        all_coordinators = self._get_all_coordinators()

        next_poll_seconds = min(
            (
                item.get("next_poll_seconds")
                for item in global_state.values()
                if item.get("next_poll_seconds") is not None
            ),
            default=None,
        )
        throttle_factor = max(
            (coord.quota.throttle_factor() for coord in all_coordinators), default=1.0
        )
        calls_last_hour = max(
            (coord.quota.calls_last_hour() for coord in all_coordinators), default=0
        )
        calls_last_24h = max(
            (coord.quota.calls_last_day() for coord in all_coordinators), default=0
        )
        filtered_departures_last_cycle = sum(
            item.get("filtered_departures", 0) for item in global_state.values()
        )
        service_gap_detected = any(
            item.get("service_gap") for item in global_state.values()
        )
        time_window_active = any(
            item.get("time_window_active") for item in global_state.values()
        )
        last_api_update = max(
            (
                item.get("last_api_update")
                for item in global_state.values()
                if item.get("last_api_update")
            ),
            default=None,
        )
        percent_used = self.native_value
        if next_poll_seconds is not None:
            next_poll_minutes = int(next_poll_seconds // 60)
        else:
            next_poll_minutes = None

        if percent_used >= 100:
            quota_status = "critical"
        elif percent_used >= 88:
            quota_status = "high"
        elif percent_used >= 63:
            quota_status = "warning"
        else:
            quota_status = "normal"

        if throttle_factor >= 2.0:
            polling_mode = "throttled"
        elif throttle_factor > 1.0:
            polling_mode = "conservative"
        elif global_state and not time_window_active:
            polling_mode = "low_power"
        else:
            polling_mode = "normal"

        return {
            "quota_status": quota_status,
            "polling_mode": polling_mode,
            "time_window_active": time_window_active,
            "service_gap_detected": service_gap_detected,
            "filtered_departures_last_cycle": filtered_departures_last_cycle,
            "last_api_update": last_api_update,
            "next_poll_minutes": next_poll_minutes,
            "next_poll_seconds": next_poll_seconds,
            "throttle_factor": throttle_factor,
            "active_stops": len(all_coordinators),
            "calls_last_hour": calls_last_hour,
            "calls_last_24h": calls_last_24h,
        }
