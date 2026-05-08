# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Constants for the Kollektivtrafik Sverige integration."""

from __future__ import annotations
from typing import Final

# ---------------------------------------------------------------------------
# Core domain
# ---------------------------------------------------------------------------

DOMAIN: Final = "kollektivtrafik_sverige"

# ---------------------------------------------------------------------------
# Logic limits
# ---------------------------------------------------------------------------

MAX_DEPARTURES: Final = 5

# ---------------------------------------------------------------------------
# Configuration keys
# ---------------------------------------------------------------------------

CONF_API_KEY: Final = "api_key"
CONF_STOP_ID: Final = "stop_id"
CONF_LINE_FILTER: Final = "line_filter"
CONF_DIRECTION_FILTER: Final = "direction_filter"
CONF_TIME_WINDOWS: Final = "time_windows"

# ---------------------------------------------------------------------------
# API endpoints (Trafiklab Unified Realtime API v1)
# ---------------------------------------------------------------------------

API_BASE_URL: Final = "https://realtime-api.trafiklab.se/v1"

# REMOVED the leading slash so yarl doesn't double-slash the URL
DEPARTURES_ENDPOINT: Final = "departures"
STOPS_ENDPOINT: Final = "stops"

# UI Links for the configuration flow documentation
PROJECT_LINK: Final = "https://developer.trafiklab.se/project/list"
REALTIME_API_LINK: Final = (
    "https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis"
)
STOP_LOOKUP_LINK: Final = (
    "https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/stop-lookup"
)

# ---------------------------------------------------------------------------
# Sensor attribute keys
# ---------------------------------------------------------------------------

ATTR_LINE: Final = "line"
ATTR_DESTINATION: Final = "destination"
ATTR_DIRECTION: Final = "direction"
ATTR_EXPECTED_TIME: Final = "expected_time"
ATTR_SCHEDULED_TIME: Final = "scheduled_time"
ATTR_MINUTES: Final = "minutes"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_TRANSPORT_MODE: Final = "transport_mode"
ATTR_DEVIATIONS: Final = "deviations"

# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

ERROR_API_KEY_INVALID: Final = "invalid_api_key"
ERROR_STOP_NOT_FOUND: Final = "stop_not_found"
ERROR_CONNECTION: Final = "connection_error"
ERROR_UNKNOWN: Final = "unknown_error"
