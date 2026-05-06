# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""10-buffer queue for Kollektivtrafik Sverige integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .parser import NormalizedDeparture, _parse_iso

MAX_BUFFER = 10
EXPOSED_COUNT = 5
TIMESTAMP_THRESHOLD_MINUTES = 60


class DepartureQueue:
    """Rolling queue for normalized departures."""

    def __init__(self) -> None:
        """Initialize the queue."""
        self._buffer: list[NormalizedDeparture] = []

    def update(self, departures: list[NormalizedDeparture]) -> None:
        """Replace buffer with new departures (max 10)."""
        self._buffer = departures[:MAX_BUFFER]

    def exposed(self) -> list[dict[str, Any] | None]:
        """Return the 5 departures exposed to Home Assistant."""
        now = dt_util.now()
        exposed: list[dict[str, Any] | None] = []

        for dep in self._buffer[:EXPOSED_COUNT]:
            exposed.append(self._format_departure(dep, now))

        # Pad with None for missing slots
        while len(exposed) < EXPOSED_COUNT:
            exposed.append(None)

        return exposed

    def prune_expired(self, now: datetime | None = None) -> None:
        """Remove departures that are already in the past."""
        curr_now = now or dt_util.now()

        # Keep departures that are within the 60-second grace period or in the future
        self._buffer = [
            dep
            for dep in self._buffer
            if (dt := _parse_iso(dep.expected_time))
            and (dt - curr_now).total_seconds() >= -60
        ][:MAX_BUFFER]

    def _format_departure(
        self, dep: NormalizedDeparture, now: datetime
    ) -> dict[str, Any]:
        """Convert a NormalizedDeparture into a dict for sensors."""
        dt = _parse_iso(dep.expected_time)

        # Default to the value provided by the parser
        minutes = dep.minutes

        # Recalculate minutes relative to 'now' to ensure accuracy between polls
        if dt:
            if dt.tzinfo is None:
                dt = dt_util.as_local(dt)

            delta = dt - now
            total_seconds = int(delta.total_seconds())

            # Align with Parser logic: -60s to 59s is "Now" (0 min)
            if -60 <= total_seconds < 60:
                minutes = 0
            else:
                minutes = total_seconds // 60

        # Logic: If > 60 minutes away, we show the clock time (timestamp)
        # Otherwise, we show the minutes remaining
        if minutes is not None and minutes > TIMESTAMP_THRESHOLD_MINUTES:
            minutes_display = None
            timestamp_display = dep.expected_time
        else:
            minutes_display = max(0, minutes) if minutes is not None else None
            timestamp_display = None

        return {
            "line": dep.line,
            "destination": dep.destination,
            "direction": dep.direction,
            "expected_time": dep.expected_time,
            "scheduled_time": dep.scheduled_time,
            "minutes": minutes_display,
            "timestamp": timestamp_display,
            "transport_mode": dep.transport_mode,
            "deviations": dep.deviations,
        }
