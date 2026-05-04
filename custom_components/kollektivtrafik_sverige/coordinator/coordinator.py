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
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..api import KollektivtrafikApiClient
from ..parser import parse_departures_response
from ..filters import filter_departures
from ..queue import DepartureQueue
from ..polling import calculate_next_interval, QuotaTracker
from ..const import (
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_LINE_FILTER,
    CONF_DIRECTION_FILTER,
    CONF_TIME_WINDOWS,
)

_LOGGER = logging.getLogger(__name__)


class KollektivtrafikSverigeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Main orchestrator for Trafiklab realtime departures."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator using the config entry."""

        # 1. Extract data from entry (Data is in .data and .options)
        api_key = entry.data[CONF_API_KEY]
        self.stop_id = entry.data[CONF_STOP_ID]

        # Options can change via Options Flow, so we grab them here
        self.line_filter = entry.options.get(CONF_LINE_FILTER, "")
        self.direction_filter = entry.options.get(CONF_DIRECTION_FILTER)
        self.time_windows = entry.options.get(CONF_TIME_WINDOWS, [])

        # 2. Initialize internal tools
        self.api = KollektivtrafikApiClient(
            api_key, session=async_get_clientsession(hass)
        )
        self.queue = DepartureQueue()
        self.quota = QuotaTracker()

        super().__init__(
            hass,
            _LOGGER,
            name=f"Kollektivtrafik {self.stop_id}",
            # Start with a safe default, polling logic will override this immediately
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch, parse, filter, queue, and compute next interval."""
        now = dt_util.now()

        # 1. Fetch raw API data
        try:
            raw = await self.api.get_departures(self.stop_id)
        except Exception as err:
            # If the API fails, we don't clear the queue!
            # We keep showing the old data until it's pruned by time.
            _LOGGER.error("Error fetching departures for %s: %s", self.stop_id, err)
            raise UpdateFailed(f"API error: {err}") from err

        # Record quota usage
        self.quota.record_call()

        # 2. Parse normalized departures
        parsed = parse_departures_response(raw, now=now)

        # 3. Apply filters
        filtered = filter_departures(
            parsed,
            line_filter=self.line_filter,
            direction_filter=self.direction_filter,
        )

        # 4. Update the rolling buffer
        # We prune first so the 'exposed' list doesn't show ghost buses
        self.queue.prune_expired(now)
        self.queue.update(filtered)

        # 5. Calculate next polling interval based on our custom logic
        interval_sec = calculate_next_interval(
            queue=self.queue,
            time_windows=self.time_windows,
            quota=self.quota,
            now=now,
        )

        # Dynamically adjust the sleep timer for the next poll
        self.update_interval = timedelta(seconds=interval_sec)
        _LOGGER.debug("Next poll for %s in %s seconds", self.stop_id, interval_sec)

        # 6. Return the data dictionary that sensors will consume
        return {
            "departures": self.queue.exposed(),
            "next_poll_seconds": interval_sec,
        }
