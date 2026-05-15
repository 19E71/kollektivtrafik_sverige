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
    summary_deviation: str


def _flatten_deviations(deviations: list[dict[str, Any]]) -> str:
    """Flatten deviation list into a human-readable summary string.

    Extracts 'description' or 'header' fields from each deviation
    and concatenates them with semicolons.
    """
    if not deviations:
        return ""

    summaries = []
    for deviation in deviations:
        if not isinstance(deviation, dict):
            continue
        # Try 'description' first, then 'header', then 'title'
        text = (
            deviation.get("description")
            or deviation.get("header")
            or deviation.get("title")
            or ""
        )
        if text and isinstance(text, str):
            summaries.append(text.strip())

    return "; ".join(summaries)


def _parse_iso(dt_str: Any) -> datetime | None:
    """Parse ISO datetime strings as LOCAL time."""
    if not isinstance(dt_str, str) or not dt_str:
        return None

    dt = dt_util.parse_datetime(dt_str)
    if dt is None:
        return None

    # FIXED: If the API time is naive (no TZ), assume it is LOCAL Swedish time.
    # We do NOT force UTC here anymore.
    if dt.tzinfo is None:
        return dt_util.as_local(dt)
    return dt_util.as_local(dt)


def _minutes_until(target: datetime, now: datetime) -> int | None:
    """Return whole minutes from now until target."""
    # Both target and now are now local datetimes
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
    # Use HA's local time for 'now'
    if now is None:
        now = dt_util.now()
    else:
        now = dt_util.as_local(now)

    departures_raw = raw.get("departures", [])
    if not isinstance(departures_raw, list):
        return []

    normalized: list[NormalizedDeparture] = []

    for item in departures_raw:
        if not isinstance(item, dict):
            continue

        route = item.get("route", {})
        line = str(route.get("designation") or "")
        destination = str(route.get("direction") or "")
        transport_mode = str(route.get("transport_mode") or "")

        expected_raw = item.get("realtime")
        scheduled_raw = item.get("scheduled")

        # These now return localized datetime objects
        expected_dt = _parse_iso(expected_raw)
        scheduled_dt = _parse_iso(scheduled_raw)

        effective_dt = expected_dt or scheduled_dt
        if effective_dt is None:
            continue

        # Calculate minutes based on LOCAL time comparison
        minutes = _minutes_until(effective_dt, now)
        if minutes is None:
            continue

        deviations = item.get("alerts", [])

        normalized.append(
            NormalizedDeparture(
                line=line,
                destination=destination,
                direction=destination,
                # We store the ISO format but with the correct local offset
                expected_time=effective_dt.isoformat(),
                scheduled_time=scheduled_dt.isoformat() if scheduled_dt else None,
                minutes=minutes,
                transport_mode=transport_mode,
                deviations=deviations,
                summary_deviation=_flatten_deviations(deviations),
            )
        )

    normalized.sort(key=lambda d: d.expected_time)
    return normalized
