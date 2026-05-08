# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Parsing and normalization of Trafiklab Realtime API v1 responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util


@dataclass(frozen=True)
class NormalizedDeparture:
    """Normalized representation of a single departure."""

    line: str
    destination: str
    direction: str | None
    expected_time: str
    scheduled_time: str | None
    minutes: int | None
    transport_mode: str | None
    deviations: list[dict[str, Any]]


def _parse_iso(dt_str: Any) -> datetime | None:
    """Parse ISO-like datetime strings safely."""
    if not isinstance(dt_str, str) or not dt_str:
        return None
    return dt_util.parse_datetime(dt_str)


def _minutes_until(target: datetime, now: datetime) -> int | None:
    """Return whole minutes from now until target."""
    delta = target - now
    total_seconds = int(delta.total_seconds())

    if total_seconds < -60:
        return None
    if -60 <= total_seconds < 60:
        return 0
    return total_seconds // 60


def parse_departures_response(
    raw: dict[str, Any],
    now: datetime | None = None,
) -> list[NormalizedDeparture]:
    """Parse and normalize a Trafiklab Unified API v1 response."""
    if now is None:
        now = dt_util.now()

    # The Unified API v1 puts departures in a top-level "departures" list
    departures_raw = raw.get("departures", [])
    if not isinstance(departures_raw, list):
        return []

    normalized: list[NormalizedDeparture] = []

    for item in departures_raw:
        if not isinstance(item, dict):
            continue

        # Route info is nested in the 'route' object
        route = item.get("route", {})
        line = str(route.get("designation") or "")
        destination = str(route.get("direction") or "")
        transport_mode = str(route.get("transport_mode") or "")

        # Time mapping matches your browser output: 'realtime' and 'scheduled'
        expected_raw = item.get("realtime")
        scheduled_raw = item.get("scheduled")

        expected_dt = _parse_iso(expected_raw)
        scheduled_dt = _parse_iso(scheduled_raw)

        # Fallback
        effective_dt = expected_dt or scheduled_dt
        if effective_dt is None:
            continue

        minutes = _minutes_until(effective_dt, now)
        if minutes is None:
            continue

        # Deviations are in 'alerts' in this API version
        deviations = item.get("alerts", [])

        normalized.append(
            NormalizedDeparture(
                line=line,
                destination=destination,
                direction=destination,  # Using destination as direction for this API
                expected_time=effective_dt.isoformat(),
                scheduled_time=scheduled_dt.isoformat() if scheduled_dt else None,
                minutes=minutes,
                transport_mode=transport_mode,
                deviations=deviations,
            )
        )

    # Sort by expected_time
    normalized.sort(key=lambda d: d.expected_time)
    return normalized
