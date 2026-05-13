# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/

"""Realtime API client used by the Kollektivtrafik Sverige integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from yarl import URL

BASE_URL = "https://realtime-api.trafiklab.se/v1"

_LOGGER = logging.getLogger(__name__)


class KollektivtrafikApiError(Exception):
    """Exception for Realtime API errors."""


class KollektivtrafikApiClient:
    """Client for the Trafiklab Realtime API v1."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 15,
    ) -> None:
        """Initialize the API client."""
        self.api_key = api_key
        self._session = session
        self._close_session = False
        self.timeout = timeout

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    async def close(self) -> None:
        """Close session if created internally."""
        if self._close_session and self._session:
            await self._session.close()

    # -------------------------------------------------------------------------
    # DEPARTURES
    # -------------------------------------------------------------------------

    async def get_departures(self, stop_id: str) -> dict[str, Any]:
        """Fetch realtime departures for a stop_group ID."""
        url = URL(BASE_URL) / "departures" / stop_id
        return await self._async_request(url)

    # -------------------------------------------------------------------------
    # STOP SEARCH (FIXED)
    # -------------------------------------------------------------------------

    async def search_stops(self, search_value: str) -> list[dict[str, Any]]:
        """Search for stops by name.

        Returns a list of stop_groups, each containing:
        - id (stop_group ID, CORRECT)
        - name
        - group_name
        - transport_modes
        - stops (list of stop IDs + names)
        """
        url = URL(BASE_URL) / "stops" / "name" / search_value
        data = await self._async_request(url)

        results = []

        for group in data.get("stop_groups", []):
            results.append(
                {
                    "id": group.get("id"),  # <-- CORRECT stop_group ID
                    "name": group.get("name"),
                    "group_name": group.get("name"),
                    "transport_modes": group.get("transport_modes", []),
                    "stops": group.get("stops", []),
                }
            )

        return results

    # -------------------------------------------------------------------------
    # INTERNAL REQUEST HANDLER
    # -------------------------------------------------------------------------

    async def _async_request(self, url: URL) -> dict[str, Any]:
        """Make a request to the API with unified error handling."""
        params = {"key": self.api_key}
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with self.session.get(
                url, params=params, timeout=timeout
            ) as response:

                if response.status in (401, 403):
                    raise KollektivtrafikApiError("Unauthorized: Invalid API key")
                if response.status == 404:
                    raise KollektivtrafikApiError(f"Not Found: {url}")
                if response.status == 429:
                    raise KollektivtrafikApiError("Rate limit exceeded")

                response.raise_for_status()

                try:
                    return await response.json()
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise KollektivtrafikApiError(
                        f"Malformed API response: {err}"
                    ) from err

        except asyncio.TimeoutError as err:
            raise KollektivtrafikApiError("API request timed out") from err
        except aiohttp.ClientError as err:
            raise KollektivtrafikApiError(f"Connection error: {err}") from err

    # -------------------------------------------------------------------------
    # API KEY VALIDATION
    # -------------------------------------------------------------------------

    async def validate_api_key(self, test_stop_id: str = "740000001") -> bool:
        """Validate API key by making a test request."""
        try:
            await self.get_departures(test_stop_id)
            return True
        except KollektivtrafikApiError:
            return False
