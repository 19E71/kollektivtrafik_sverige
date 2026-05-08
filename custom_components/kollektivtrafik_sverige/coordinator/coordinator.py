# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Main orchestrator for Kollektivtrafik Sverige integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from ..api import KollektivtrafikApiClient
from .parser import parse_departures_response
from .filters import filter_departures
from .queue import DepartureQueue
from .polling import calculate_next_interval, QuotaTracker
from ..const import (
    CONF_STOP_ID,
    CONF_LINE_FILTER,
    CONF_DIRECTION_FILTER,
    CONF_TIME_WINDOWS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class KollektivtrafikSverigeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Main orchestrator for Trafiklab realtime departures."""

    def __init__(
        self, hass: HomeAssistant, client: KollektivtrafikApiClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.api = client  # Use the client passed from __init__.py

        self.queue = DepartureQueue()
        self.quota = QuotaTracker()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_STOP_ID]}",
            # Initial interval, will be dynamically adjusted by calculate_next_interval
            update_interval=timedelta(seconds=60),
        )

    @property
    def stop_id(self) -> str:
        """Return stop ID from entry data."""
        return str(self.entry.data[CONF_STOP_ID])

    @property
    def line_filter(self) -> str:
        """Return line filter from entry options."""
        return self.entry.options.get(CONF_LINE_FILTER, "")

    @property
    def direction_filter(self) -> str | None:
        """Return direction filter from entry options."""
        # Use .get() to return None if it's not set
        return self.entry.options.get(CONF_DIRECTION_FILTER)

    @property
    def time_windows(self) -> list[str]:
        """Return time windows from entry options."""
        return self.entry.options.get(CONF_TIME_WINDOWS, [])

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch, parse, filter, queue, and compute next interval."""
        now = dt_util.now()

        # 1. Fetch raw API data
        try:
            raw = await self.api.get_departures(self.stop_id)
        except Exception as err:
            _LOGGER.error("Error fetching departures for %s: %s", self.stop_id, err)
            raise UpdateFailed(f"API error: {err}") from err

        # Record quota usage for the polling logic
        self.quota.record_call(now)

        # 2. Parse raw response into normalized departure objects
        parsed = parse_departures_response(raw, now=now)

        # 3. Apply user-defined filters
        filtered = filter_departures(
            parsed,
            line_filter=self.line_filter,
            direction_filter=self.direction_filter,
        )

        # 4. Update the internal rolling buffer
        self.queue.prune_expired(now)
        self.queue.update(filtered)

        # 5. Calculate next polling interval based on traffic density and quotas
        interval_sec = calculate_next_interval(
            queue=self.queue,
            time_windows=self.time_windows,
            quota=self.quota,
            now=now,
        )

        # Dynamically adjust the coordinator timer for the next poll
        self.update_interval = timedelta(seconds=interval_sec)

        _LOGGER.debug(
            "Fetched %d departures for %s. Next poll in %d seconds",
            len(filtered),
            self.stop_id,
            interval_sec,
        )

        # 6. Return data for sensors
        return {
            "departures": self.queue.exposed(),
            "next_poll_seconds": interval_sec,
        }
