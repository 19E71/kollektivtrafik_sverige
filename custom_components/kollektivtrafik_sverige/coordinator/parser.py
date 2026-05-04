# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Parsing and normalization of Trafiklab Realtime API responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util


@dataclass(frozen=True)
class NormalizedDeparture:
    """Normalized representation of a single departure.

    Using frozen=True makes the data immutable and hashable,
    which is better for coordinator data stability.
    """

    line: str
    destination: str
    direction: str | None
    expected_time: str
    scheduled_time: str | None
    minutes: int | None
    transport_mode: str | None
    deviations: list[dict[str, Any]]


def _parse_iso(dt_str: Any) -> datetime | None:
    """Parse ISO-like datetime strings safely using HA's utility."""
    if not isinstance(dt_str, str) or not dt_str:
        return None

    # parse_datetime handles ISO 8601 with or without Z/Timezone offsets
    return dt_util.parse_datetime(dt_str)


def _minutes_until(target: datetime, now: datetime) -> int | None:
    """Return whole minutes from now until target, or None if past."""
    # Ensure both are aware or both are naive (HA uses aware)
    delta = target - now
    total_seconds = int(delta.total_seconds())

    # We allow 0 minutes, but negative means the bus is gone
    if total_seconds < 0:
        return None
    return total_seconds // 60


def _safe_str(value: Any) -> str:
    """Convert value to string safely."""
    return str(value) if value is not None else ""


def parse_departures_response(
    raw: dict[str, Any],
    now: datetime | None = None,
) -> list[NormalizedDeparture]:
    """Parse and normalize a Trafiklab departures response."""
    if now is None:
        now = dt_util.now()

    # Handle different possible API response structures
    departures_raw = raw.get("departures") or raw.get("Departures") or []
    if isinstance(departures_raw, dict):
        departures_raw = [departures_raw]
    if not isinstance(departures_raw, list):
        departures_raw = []

    normalized: list[NormalizedDeparture] = []

    for item in departures_raw:
        if not isinstance(item, dict):
            continue

        line = _safe_str(
            item.get("line") or item.get("LineNumber") or item.get("line_number")
        )
        destination = _safe_str(
            item.get("destination")
            or item.get("Destination")
            or item.get("direction")
            or item.get("Towards")
        )
        direction = (
            _safe_str(item.get("direction") or item.get("Direction") or "") or None
        )

        # Time mapping
        expected_raw = (
            item.get("expected_time")
            or item.get("ExpectedDateTime")
            or item.get("expected_datetime")
            or item.get("rtTime")
            or item.get("rtDateTime")
        )
        scheduled_raw = (
            item.get("scheduled_time")
            or item.get("AdvertisedTimeAtLocation")
            or item.get("time")
            or item.get("planned_datetime")
        )

        expected_dt = _parse_iso(expected_raw)
        scheduled_dt = _parse_iso(scheduled_raw)

        # Fallback logic
        effective_dt = expected_dt or scheduled_dt
        if effective_dt is None:
            continue

        minutes = _minutes_until(effective_dt, now)

        transport_mode = (
            _safe_str(
                item.get("transport_mode")
                or item.get("TransportMode")
                or item.get("Product")
            )
            or None
        )

        # Deviation parsing
        deviations_raw = item.get("deviations") or item.get("Deviations") or []
        if isinstance(deviations_raw, dict):
            deviations_raw = [deviations_raw]

        deviations: list[dict[str, Any]] = (
            deviations_raw if isinstance(deviations_raw, list) else []
        )

        normalized.append(
            NormalizedDeparture(
                line=line,
                destination=destination,
                direction=direction,
                expected_time=effective_dt.isoformat(),
                scheduled_time=scheduled_dt.isoformat() if scheduled_dt else None,
                minutes=minutes,
                transport_mode=transport_mode,
                deviations=deviations,
            )
        )

    # Sort by expected_time (string ISO format sorts chronologically)
    normalized.sort(key=lambda d: d.expected_time)
    return normalized
