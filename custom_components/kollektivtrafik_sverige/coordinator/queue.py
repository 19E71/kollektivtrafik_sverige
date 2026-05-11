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
        self._buffer: list[NormalizedDeparture] = []

    def update(self, departures: list[NormalizedDeparture]) -> None:
        """Replace buffer with new departures."""
        self._buffer = departures[:MAX_BUFFER]

    def exposed(self) -> list[dict[str, Any] | None]:
        """Return the 5 departures formatted as dictionaries."""
        now = dt_util.now().astimezone(dt_util.UTC)
        exposed: list[dict[str, Any] | None] = []

        for dep in self._buffer[:EXPOSED_COUNT]:
            exposed.append(self._format_departure(dep, now))

        while len(exposed) < EXPOSED_COUNT:
            exposed.append(None)
        return exposed

    def prune_expired(self, now: datetime | None = None) -> None:
        """Remove departures that have already passed."""
        curr_now = now or dt_util.now()
        now_utc = (
            curr_now.astimezone(dt_util.UTC)
            if curr_now.tzinfo
            else curr_now.replace(tzinfo=dt_util.UTC)
        )

        self._buffer = [
            dep
            for dep in self._buffer
            if (dt := _parse_iso(dep.expected_time))
            and (dt - now_utc).total_seconds() >= -60
        ][:MAX_BUFFER]

    def _format_departure(
        self, dep: NormalizedDeparture, now_utc: datetime
    ) -> dict[str, Any]:
        """Convert a NormalizedDeparture into a dict and handle >60min logic."""
        dt = _parse_iso(dep.expected_time)
        minutes = dep.minutes

        if dt:
            delta = dt - now_utc
            total_seconds = int(delta.total_seconds())

            # Re-calculate minutes relative to current time
            if -60 <= total_seconds < 60:
                minutes = 0
            else:
                minutes = total_seconds // 60

        # Toggle between "X min" and "14:55" based on 60-minute threshold
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
            "summary_deviation": dep.summary_deviation,
        }
