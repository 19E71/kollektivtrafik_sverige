# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Sensor platform for Kollektivtrafik Sverige."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ATTR_LINE,
    ATTR_DESTINATION,
    ATTR_DIRECTION,
    ATTR_EXPECTED_TIME,
    ATTR_SCHEDULED_TIME,
    ATTR_MINUTES,
    ATTR_TIMESTAMP,
    ATTR_TRANSPORT_MODE,
    ATTR_DEVIATIONS,
)
from .entity import KollektivtrafikSverigeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    # Note: Accessing via "instances" sub-key as defined in your new __init__.py
    coordinator = hass.data[DOMAIN]["instances"][entry.entry_id]

    entities: list[SensorEntity] = []

    # Add the 5 departure sensors
    entities.extend(DepartureSensor(coordinator, entry, index) for index in range(5))

    # Add the Quota Usage sensor
    entities.append(KollektivtrafikQuotaSensor(coordinator, entry))

    async_add_entities(entities)


class DepartureSensor(KollektivtrafikSverigeEntity, SensorEntity):
    """A departure sensor with dynamic bracket naming for perfect UI sorting."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: Any, entry: ConfigEntry, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, index)

    @property
    def name(self) -> str | None:
        """Return name like '1. (5 - Gångviken)' or fallback if empty."""
        data = self._get_departure()
        prefix = f"{self._index + 1}."

        if not data:
            # Check if we are currently inside an active polling window
            # using the logic we already have in the coordinator
            from .coordinator.polling import _in_time_window
            from homeassistant.util import dt as dt_util

            is_active = _in_time_window(dt_util.now(), self.coordinator.time_windows)

            if is_active:
                return f"{prefix} (No more departures in 60m)"
            return f"{prefix} (Outside active window)"

        line = data.get(ATTR_LINE)
        destination = data.get(ATTR_DESTINATION)

        if line and destination:
            return f"{prefix} ({line} - {destination})"

        return f"{prefix} (Departure)"

    @property
    def native_value(self) -> int | datetime | None:
        """Return the sensor state (minutes or timestamp)."""
        data = self._get_departure()
        if not data:
            return None

        mins = data.get(ATTR_MINUTES)
        if mins is not None:
            return mins

        timestamp = data.get(ATTR_TIMESTAMP)
        if not timestamp:
            return None

        parsed = dt_util.parse_datetime(timestamp)
        if parsed and parsed.tzinfo is None:
            parsed = dt_util.as_local(parsed)
        return parsed

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Only show 'min' when state is minutes."""
        data = self._get_departure()
        if data and data.get(ATTR_MINUTES) is not None:
            return "min"
        return None

    @property
    def state_class(self) -> SensorStateClass | None:
        data = self._get_departure()
        if data and data.get(ATTR_MINUTES) is not None:
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        data = self._get_departure()
        if not data or data.get(ATTR_MINUTES) is not None:
            return None
        if data.get(ATTR_TIMESTAMP) is not None:
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose bus details and the next poll time."""
        data = self._get_departure()
        attrs = {}

        if data:
            attrs.update(
                {
                    ATTR_LINE: data.get(ATTR_LINE),
                    ATTR_DESTINATION: data.get(ATTR_DESTINATION),
                    ATTR_DIRECTION: data.get(ATTR_DIRECTION),
                    ATTR_EXPECTED_TIME: data.get(ATTR_EXPECTED_TIME),
                    ATTR_SCHEDULED_TIME: data.get(ATTR_SCHEDULED_TIME),
                    ATTR_MINUTES: data.get(ATTR_MINUTES),
                    ATTR_TIMESTAMP: data.get(ATTR_TIMESTAMP),
                    ATTR_TRANSPORT_MODE: data.get(ATTR_TRANSPORT_MODE),
                    ATTR_DEVIATIONS: data.get(ATTR_DEVIATIONS, []),
                }
            )

        # Add global integration info
        attrs["next_poll_seconds"] = self.coordinator.data.get("next_poll_seconds")

        return attrs


class KollektivtrafikQuotaSensor(KollektivtrafikSverigeEntity, SensorEntity):
    """Sensor to track API quota usage for this specific stop."""

    _attr_has_entity_name = True
    _attr_name = "API Quota Usage"
    _attr_icon = "mdi:chart-donut"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: Any, entry: ConfigEntry) -> None:
        """Initialize the quota sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_quota_usage"

    @property
    def native_value(self) -> float:
        """Return the percentage of the daily budget used."""
        used = self.coordinator.quota.calls_last_day()
        total = self.coordinator.quota.daily_allowance

        if total == 0:
            return 0.0

        return round((used / total) * 100, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose raw call counts and throttling status."""
        tracker = self.coordinator.quota
        return {
            "calls_last_24h": tracker.calls_last_day(),
            "calls_last_hour": tracker.calls_last_hour(),
            "daily_allowance": tracker.daily_allowance,
            "hourly_allowance": tracker.hourly_allowance,
            "throttle_factor": tracker.throttle_factor(),
            "active_stops_sharing_quota": tracker.stop_count,
        }
