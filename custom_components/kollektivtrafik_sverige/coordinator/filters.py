# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Filtering logic for Kollektivtrafik Sverige integration."""

from __future__ import annotations

from .parser import NormalizedDeparture


def filter_departures(
    departures: list[NormalizedDeparture],
    line_filter: str,
    direction_filter: str | None = None,
) -> list[NormalizedDeparture]:
    """Apply line and direction filtering to normalized departures.

    Parameters:
        departures: list of NormalizedDeparture objects.
        line_filter: Optional. Comma-separated list of line identifiers.
        direction_filter: Optional substring match for destination/direction.

    Returns:
        Filtered list of departures.
    """
    # 1. Normalize line filter into a set
    raw_filter = (line_filter or "").strip()

    allowed_lines = {
        part.strip().lower() for part in raw_filter.split(",") if part.strip()
    }

    # 2. Pre-process direction filter
    df = (direction_filter or "").lower().strip()

    filtered: list[NormalizedDeparture] = []

    for dep in departures:
        # Line match: If allowed_lines is empty, we allow everything.
        # If it has values, we only allow matches.
        if allowed_lines and dep.line.lower() not in allowed_lines:
            continue

        # Direction match (optional)
        if df:
            dest = (dep.destination or "").lower()
            dir_field = (dep.direction or "").lower()
            if df not in dest and df not in dir_field:
                continue

        filtered.append(dep)

    return filtered
