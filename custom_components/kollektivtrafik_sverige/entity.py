# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Base entity helpers for the Kollektivtrafik Sverige integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class KollektivtrafikSverigeEntity(CoordinatorEntity):
    """Base class for Kollektivtrafik Sverige entities."""

    def __init__(
        self,
        coordinator: Any,
        entry: ConfigEntry,
        stop_config: dict[str, Any],
        index: int | None = None,
    ) -> None:
        """Initialize the base entity with shared metadata.

        Args:
            coordinator: The update coordinator for this stop
            entry: The config entry (main entry, not per-stop)
            stop_config: The stop configuration dict
            index: Optional index for departure sensors (0-4)
        """
        super().__init__(coordinator)
        self._entry = entry
        self._stop_config = stop_config
        self._index = index

        # Create per-stop device info
        stop_id = stop_config.get("stop_id", "unknown")
        stop_name = stop_config.get("name", f"Stop {stop_id}")
        internal_id = stop_config.get("id", "unknown")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{internal_id}")},
            name=stop_name,
            manufacturer="19E71",
            model="Kollektivtrafik Sverige",
            suggested_area=None,  # User can organize by area
        )

        if index is not None:
            # Ensure unique_id is unique per stop and per departure index
            self._attr_unique_id = f"{entry.entry_id}_{internal_id}_departure_{index}"

    @property
    def available(self) -> bool:
        """Return True when the entity should be available in the UI."""
        if not super().available:
            return False

        if self._index is None:
            return True

        return self._get_departure() is not None

    def _get_departure(self) -> dict[str, Any] | None:
        """Safe access to the coordinator's departure list."""
        if not self.coordinator.data or "departures" not in self.coordinator.data:
            return None

        departures = self.coordinator.data["departures"]
        if self._index >= len(departures):
            return None

        return departures[self._index]
