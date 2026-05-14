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
from homeassistant.helpers import entity_registry as er
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
    ATTR_SUMMARY_DEVIATION,
    TRANSPORT_MODE_ICONS,
    DEFAULT_TRANSPORT_ICON,
)
from .coordinator.polling import _in_time_window
from .entity import KollektivtrafikSverigeEntity
from .sensor_global import GlobalQuotaSensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry.

    For each stop in the entry, creates 5 departure sensors.
    Also sets up the global quota sensor once.
    """
    # Get all coordinators for this entry
    coordinators = hass.data[DOMAIN][entry.entry_id].get("coordinators", {})

    entities: list[SensorEntity] = []

    # Create 5 departure sensors for each coordinator (stop)
    for stop_id, coordinator in coordinators.items():
        for index in range(5):
            entities.append(
                DepartureSensor(coordinator, entry, coordinator.stop_config, index)
            )

    # Add the global quota sensor
    global_data = hass.data[DOMAIN]["global"]
    global_sensor = global_data.get("sensor")
    ent_reg = er.async_get(hass)

    # Check if global sensor is already in the entity registry
    global_sensor_entity_id = "sensor.kollektivtrafik_sverige_global_api_quota_usage"
    global_sensor_exists_in_registry = (
        global_sensor_entity_id in ent_reg.entities if ent_reg.entities else False
    )

    # If sensor doesn't exist in registry or object is None, create new one
    if not global_sensor_exists_in_registry or global_sensor is None:
        global_sensor = GlobalQuotaSensor(hass, coordinators)
        entities.append(global_sensor)
        global_data["sensor_created"] = True
        global_data["sensor"] = global_sensor
    else:
        # Sensor exists in registry, just update coordinator registrations
        if hasattr(global_sensor, "register_coordinators"):
            global_sensor.register_coordinators(coordinators)

    async_add_entities(entities)


class DepartureSensor(KollektivtrafikSverigeEntity, SensorEntity):
    """A departure sensor with dynamic bracket naming for perfect UI sorting."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Any,
        entry: ConfigEntry,
        stop_config: dict[str, Any],
        index: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, stop_config, index)

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on transport mode."""
        data = self._get_departure()
        if not data:
            return DEFAULT_TRANSPORT_ICON

        transport_mode = data.get(ATTR_TRANSPORT_MODE, "").upper()
        return TRANSPORT_MODE_ICONS.get(transport_mode, DEFAULT_TRANSPORT_ICON)

    @property
    def name(self) -> str | None:
        """Return name like '1. (5 - Gångviken)' or fallback if empty."""
        data = self._get_departure()
        prefix = f"{self._index + 1}."

        if not data:
            # Check if we are currently inside an active polling window
            # using the logic we already have in the coordinator
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
                    ATTR_SUMMARY_DEVIATION: data.get(ATTR_SUMMARY_DEVIATION, ""),
                }
            )

        return attrs
