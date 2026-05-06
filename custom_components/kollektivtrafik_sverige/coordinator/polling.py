# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Dynamic polling engine + quota watchdog for Kollektivtrafik Sverige."""

from __future__ import annotations

from collections import deque
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from .queue import DepartureQueue

# ---------------------------------------------------------------------------
# Quota watchdog
# ---------------------------------------------------------------------------

DAILY_QUOTA = 100_000
TARGET_USAGE = 0.90  # 90%
MAX_CALLS_PER_DAY = int(DAILY_QUOTA * TARGET_USAGE)
MAX_CALLS_PER_HOUR = MAX_CALLS_PER_DAY // 24


class QuotaTracker:
    """Tracks API calls and enforces quota-safe polling."""

    def __init__(self) -> None:
        """Initialize tracker."""
        self._calls: deque[datetime] = deque()

    def record_call(self, now: datetime | None = None) -> None:
        """Log a call and prune old history."""
        curr_now = now or dt_util.now()
        self._calls.append(curr_now)
        self._prune(curr_now)

    def _prune(self, now: datetime) -> None:
        """Remove calls older than 24 hours."""
        cutoff = now - timedelta(hours=24)
        while self._calls and self._calls[0] < cutoff:
            self._calls.popleft()

    def calls_last_hour(self, now: datetime | None = None) -> int:
        """Count calls in the moving 1-hour window."""
        curr_now = now or dt_util.now()
        cutoff = curr_now - timedelta(hours=1)
        return sum(1 for t in self._calls if t >= cutoff)

    def calls_last_day(self, now: datetime | None = None) -> int:
        """Count calls in the moving 24-hour window."""
        curr_now = now or dt_util.now()
        self._prune(curr_now)
        return len(self._calls)

    def throttle_factor(self, now: datetime | None = None) -> float:
        """Return a multiplier for polling interval based on quota usage."""
        curr_now = now or dt_util.now()

        day_calls = self.calls_last_day(curr_now)
        hour_calls = self.calls_last_hour(curr_now)

        if day_calls > MAX_CALLS_PER_DAY:
            return 2.0
        if hour_calls > MAX_CALLS_PER_HOUR:
            return 1.5
        if day_calls < MAX_CALLS_PER_DAY * 0.5:
            return 0.8

        return 1.0


# ---------------------------------------------------------------------------
# Dynamic polling logic
# ---------------------------------------------------------------------------

MIN_INTERVAL = 15
MAX_INTERVAL = 300
SERVICE_GAP_THRESHOLD_MIN = 45
HIGH_DENSITY_MIN_INTERVAL = 30

FAST_POLL_THRESHOLD = 5
MEDIUM_POLL_THRESHOLD = 10


def _parse_window(window: str) -> tuple[time, time] | None:
    """Parse 'HH:MM-HH:MM' string into time objects."""
    try:
        start_str, end_str = window.split("-")
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        return time(sh, sm), time(eh, em)
    except (ValueError, AttributeError, IndexError):
        return None


def _in_time_window(now: datetime, windows: list[str]) -> bool:
    """Check if current time falls within any defined windows."""
    if not windows:
        return True

    now_t = now.time()
    for w in windows:
        parsed = _parse_window(w)
        if parsed:
            start, end = parsed
            if start <= now_t <= end:
                return True
            if start > end and (now_t >= start or now_t <= end):
                return True
    return False


def calculate_next_interval(
    queue: DepartureQueue,
    time_windows: list[str],
    quota: QuotaTracker,
    now: datetime | None = None,
) -> int:
    """Determine the optimal seconds until the next API request."""
    curr_now = now or dt_util.now()
    throttle = quota.throttle_factor(curr_now)

    # 1. Outside Active Windows
    if not _in_time_window(curr_now, time_windows):
        return int(MAX_INTERVAL * throttle)

    # 2. Get Next Departure
    exposed = queue.exposed()
    next_dep = next((d for d in exposed if d is not None), None)

    if next_dep is None:
        return int(MAX_INTERVAL * throttle)

    # 3. FIX: Access attributes via dot notation (NormalizedDeparture is a dataclass)
    minutes = next_dep.minutes

    # Fallback if minutes missing
    if minutes is None and next_dep.expected_time:
        dt = dt_util.parse_datetime(next_dep.expected_time)
        if dt:
            # Ensure DT is aware for comparison
            if dt.tzinfo is None:
                dt = dt_util.as_local(dt)
            delta = dt - curr_now
            minutes = max(0, int(delta.total_seconds() // 60))

    # 4. Long Gaps
    if minutes is None or minutes > SERVICE_GAP_THRESHOLD_MIN:
        return int(MAX_INTERVAL * throttle)

    # 5. Density Throttling
    base = (
        HIGH_DENSITY_MIN_INTERVAL
        if len([d for d in exposed if d is not None]) >= 5
        else MIN_INTERVAL
    )

    # 6. Adaptive Step-down
    if minutes <= FAST_POLL_THRESHOLD:
        interval = base
    elif minutes <= MEDIUM_POLL_THRESHOLD:
        interval = max(base, 30)
    else:
        interval = 60

    # 7. Apply and Clamp
    final_interval = int(interval * throttle)
    return max(MIN_INTERVAL, min(final_interval, MAX_INTERVAL))
