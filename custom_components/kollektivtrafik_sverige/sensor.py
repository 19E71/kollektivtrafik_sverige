# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Sensor platform for Kollektivtrafik Sverige."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """A single departure sensor (one of five)."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: Any, entry: ConfigEntry, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._entry = entry
        self._index = index

        # Unique ID must be truly unique across the whole HA instance
        self._attr_unique_id = f"{entry.entry_id}_departure_{index}"

        # Translation key allows for localized names via strings.json
        self._attr_translation_key = f"departure_{index + 1}"

        # Link all sensors to a single device in the UI
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="19E71",
            model="Kollektivtrafik Sverige",
        )

    @property
    def native_value(self) -> int | str | None:
        """Return minutes until departure or timestamp if far away."""
        data = self._get_departure()
        if not data:
            return None

        # If the queue decided minutes are too far off (>60min),
        # it provides a 'timestamp'. We return that as the state.
        return data.get("minutes") or data.get("timestamp")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return 'min' only if the value is numeric."""
        data = self._get_departure()
        if data and data.get("minutes") is not None:
            return "min"
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return TIMESTAMP device class if showing a timestamp."""
        data = self._get_departure()
        if data and data.get("timestamp"):
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        data = self._get_departure()
        if not data:
            return {}

        return {
            ATTR_LINE: data.get("line"),
            ATTR_DESTINATION: data.get("destination"),
            ATTR_DIRECTION: data.get("direction"),
            ATTR_EXPECTED_TIME: data.get("expected_time"),
            ATTR_SCHEDULED_TIME: data.get("scheduled_time"),
            ATTR_TRANSPORT_MODE: data.get("transport_mode"),
            ATTR_DEVIATIONS: data.get("deviations"),
        }

    def _get_departure(self) -> dict[str, Any] | None:
        """Return the departure dict for this sensor index from coordinator data."""
        if not self.coordinator.data:
            return None

        deps = self.coordinator.data.get("departures")
        # Ensure the index exists in the current 10-buffer/5-exposed list
        if not deps or self._index >= len(deps):
            return None

        return deps[self._index]
