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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Create 5 sensors (departure_1 ... departure_5)
    async_add_entities(DepartureSensor(coordinator, entry, index) for index in range(5))


class DepartureSensor(CoordinatorEntity, SensorEntity):
    """A single departure sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: Any, entry: ConfigEntry, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._entry = entry
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_departure_{index}"
        self._attr_translation_key = f"departure_{index + 1}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="19E71",
            model="Kollektivtrafik Sverige",
        )

    @property
    def native_value(self) -> int | datetime | None:
        """Return the sensor state (minutes or timestamp)."""
        data = self._get_departure()
        if not data:
            return None

        # Logic: If we have minutes, use them as the primary state.
        # If we only have a timestamp (bus is far away), use a datetime.
        mins = data.get("minutes")
        if mins is not None:
            return mins

        timestamp = data.get("timestamp")
        if not timestamp:
            return None

        parsed = dt_util.parse_datetime(timestamp)
        if parsed is None:
            return None

        if parsed.tzinfo is None:
            parsed = dt_util.as_local(parsed)
        return parsed

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Units are 'min' only when showing minutes."""
        data = self._get_departure()
        if data and data.get("minutes") is not None:
            return "min"
        return None

    @property
    def state_class(self) -> SensorStateClass | None:
        """Measurement class applies to minutes, but NOT to timestamps."""
        data = self._get_departure()
        if data and data.get("minutes") is not None:
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Set to TIMESTAMP only if we are actually displaying a timestamp string."""
        data = self._get_departure()
        if not data:
            return None

        # If we are displaying 'minutes' (an int), device_class MUST be None.
        if data.get("minutes") is not None:
            return None

        # If we are falling back to the timestamp string, use TIMESTAMP class.
        if data.get("timestamp") is not None:
            return SensorDeviceClass.TIMESTAMP

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes with safe defaults."""
        data = self._get_departure()
        if not data:
            return {}

        return {
            ATTR_LINE: data.get("line"),
            ATTR_DESTINATION: data.get("destination"),
            ATTR_DIRECTION: data.get("direction"),
            ATTR_EXPECTED_TIME: data.get("expected_time"),
            ATTR_SCHEDULED_TIME: data.get("scheduled_time"),
            ATTR_MINUTES: data.get("minutes"),
            ATTR_TIMESTAMP: data.get("timestamp"),
            ATTR_TRANSPORT_MODE: data.get("transport_mode"),
            ATTR_DEVIATIONS: data.get("deviations", []),
        }

    def _get_departure(self) -> dict[str, Any] | None:
        """Return the departure dict for this sensor index."""
        if not self.coordinator.data or "departures" not in self.coordinator.data:
            return None

        deps = self.coordinator.data["departures"]
        if self._index >= len(deps):
            return None

        return deps[self._index]
