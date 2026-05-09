# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Dynamic polling engine + quota watchdog for Kollektivtrafik Sverige."""

from __future__ import annotations

from collections import deque
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, GLOBAL_DAILY_QUOTA, QUOTA_TARGET_USAGE

if TYPE_CHECKING:
    from .queue import DepartureQueue

# ---------------------------------------------------------------------------
# Quota watchdog
# ---------------------------------------------------------------------------


class QuotaTracker:
    """Tracks API calls and enforces quota-safe polling across multiple instances."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the tracker with a reference to hass for global stop counting."""
        self._hass = hass
        self._calls: deque[datetime] = deque()

    @property
    def stop_count(self) -> int:
        """Get the current number of active stop instances from shared data."""
        return self._hass.data.get(DOMAIN, {}).get("active_stop_count", 1)

    @property
    def daily_allowance(self) -> int:
        """Calculate the daily call budget for this specific instance."""
        total_safe_calls = GLOBAL_DAILY_QUOTA * QUOTA_TARGET_USAGE
        return int(total_safe_calls / self.stop_count)

    @property
    def hourly_allowance(self) -> int:
        """Calculate the hourly call budget for this specific instance."""
        return self.daily_allowance // 24

    def record_call(self, now: datetime | None = None) -> None:
        """Record a successful API call."""
        curr_now = now or dt_util.now()
        self._calls.append(curr_now)
        self._prune(curr_now)

    def _prune(self, now: datetime) -> None:
        """Remove calls older than 24 hours."""
        cutoff = now - timedelta(hours=24)
        while self._calls and self._calls[0] < cutoff:
            self._calls.popleft()

    def calls_last_hour(self, now: datetime | None = None) -> int:
        """Count calls made in the last 60 minutes."""
        curr_now = now or dt_util.now()
        cutoff = curr_now - timedelta(hours=1)
        return sum(1 for t in self._calls if t >= cutoff)

    def calls_last_day(self, now: datetime | None = None) -> int:
        """Count calls made in the last 24 hours."""
        curr_now = now or dt_util.now()
        self._prune(curr_now)
        return len(self._calls)

    def throttle_factor(self, now: datetime | None = None) -> float:
        """Determine a multiplier for the polling interval based on budget usage."""
        curr_now = now or dt_util.now()
        day_calls = self.calls_last_day(curr_now)
        hour_calls = self.calls_last_hour(curr_now)

        # Use dynamic allowances instead of hardcoded constants
        if day_calls > self.daily_allowance:
            return 2.0  # Double the wait time
        if hour_calls > self.hourly_allowance:
            return 1.5  # Increase wait time by 50%
        if day_calls < (self.daily_allowance * 0.5):
            return 0.8  # Poll faster if we have a significant surplus
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
    """Parse a 'HH:MM-HH:MM' string into time objects."""
    try:
        start_str, end_str = window.split("-")
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        return time(sh, sm), time(eh, em)
    except (ValueError, AttributeError, IndexError):
        return None


def _in_time_window(now: datetime, windows: list[str]) -> bool:
    """Check if the current time falls within any of the defined active windows."""
    if not windows:
        return True

    now_t = dt_util.as_local(now).time()

    for w in windows:
        parsed = _parse_window(w)
        if parsed:
            start, end = parsed
            # Standard window (e.g., 06:00-17:00)
            if start <= now_t <= end:
                return True
            # Overnight window (e.g., 22:00-04:00)
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
    curr_now = dt_util.as_local(now or dt_util.now())

    throttle = quota.throttle_factor(curr_now)

    # Check if we should be in low-power mode based on local time windows
    if not _in_time_window(curr_now, time_windows):
        return int(MAX_INTERVAL * throttle)

    exposed = queue.exposed()
    next_dep = next((d for d in exposed if d is not None), None)

    if next_dep is None:
        return int(MAX_INTERVAL * throttle)

    minutes = next_dep.get("minutes")

    if minutes is None or minutes > SERVICE_GAP_THRESHOLD_MIN:
        return int(MAX_INTERVAL * throttle)

    # Determine base interval based on how many buses are at the stop
    base = (
        HIGH_DENSITY_MIN_INTERVAL
        if len([d for d in exposed if d is not None]) >= 5
        else MIN_INTERVAL
    )

    if minutes <= FAST_POLL_THRESHOLD:
        interval = base
    elif minutes <= MEDIUM_POLL_THRESHOLD:
        interval = max(base, 30)
    else:
        interval = 60

    final_interval = int(interval * throttle)

    # Ensure we never go faster than the hard minimum or slower than the maximum
    return max(MIN_INTERVAL, min(final_interval, MAX_INTERVAL))
