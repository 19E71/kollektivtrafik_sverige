# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Parsing and normalization of Trafiklab Unified Realtime API v1 responses."""

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
    """Parse ISO-like datetime strings safely and ensure they are UTC."""
    if not isinstance(dt_str, str) or not dt_str:
        return None

    dt = dt_util.parse_datetime(dt_str)
    if dt is None:
        return None

    # Force UTC if naive, or convert to UTC if it has a different offset
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_util.UTC)
    return dt.astimezone(dt_util.UTC)


def _minutes_until(target: datetime, now: datetime) -> int | None:
    """Return whole minutes from now until target."""
    # Both target and now are guaranteed UTC by the time they reach here
    delta = target - now
    total_seconds = int(delta.total_seconds())

    # If the bus left more than a minute ago, ignore it
    if total_seconds < -60:
        return None
    # If it's arriving within the minute, it's 0 minutes away
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

    # Ensure 'now' is UTC to match the parsed API timestamps
    now_utc = (
        now.astimezone(dt_util.UTC) if now.tzinfo else now.replace(tzinfo=dt_util.UTC)
    )

    departures_raw = raw.get("departures", [])
    if not isinstance(departures_raw, list):
        return []

    normalized: list[NormalizedDeparture] = []

    for item in departures_raw:
        if not isinstance(item, dict):
            continue

        # Extract nested route info
        route = item.get("route", {})
        line = str(route.get("designation") or "")
        destination = str(route.get("direction") or "")
        transport_mode = str(route.get("transport_mode") or "")

        # Unified API v1 uses 'realtime' and 'scheduled'
        expected_raw = item.get("realtime")
        scheduled_raw = item.get("scheduled")

        expected_dt = _parse_iso(expected_raw)
        scheduled_dt = _parse_iso(scheduled_raw)

        # Fallback to scheduled if realtime is missing
        effective_dt = expected_dt or scheduled_dt
        if effective_dt is None:
            continue

        # Calculate minutes using UTC comparison
        minutes = _minutes_until(effective_dt, now_utc)
        if minutes is None:
            continue

        # API v1 uses 'alerts' for deviations
        deviations = item.get("alerts", [])

        normalized.append(
            NormalizedDeparture(
                line=line,
                destination=destination,
                direction=destination,
                expected_time=effective_dt.isoformat(),
                scheduled_time=scheduled_dt.isoformat() if scheduled_dt else None,
                minutes=minutes,
                transport_mode=transport_mode,
                deviations=deviations,
            )
        )

    # Sort by the expected departure time
    normalized.sort(key=lambda d: d.expected_time)
    return normalized
