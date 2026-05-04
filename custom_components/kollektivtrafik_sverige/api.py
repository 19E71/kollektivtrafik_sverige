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

from .const import (
    API_BASE_URL,
    DEPARTURES_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class KollektivtrafikApiError(Exception):
    """Exception for Realtime API errors."""


class KollektivtrafikApiClient:
    """Client for the Trafiklab Realtime API."""

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
            # Note: We don't set a total timeout here because we apply it per request
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    async def close(self) -> None:
        """Close session if created internally."""
        if self._close_session and self._session:
            await self._session.close()

    async def __aenter__(self) -> KollektivtrafikApiClient:
        """Async context manager enter."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def get_departures(
        self,
        stop_id: str,
        time_offset: str | None = None,
    ) -> dict[str, Any]:
        """Fetch realtime departures for a stop."""

        # Using yarl for cleaner URL construction
        base = URL(API_BASE_URL + DEPARTURES_ENDPOINT)
        url = base / stop_id
        if time_offset:
            url = url / time_offset

        params = {"key": self.api_key}
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with self.session.get(
                url, params=params, timeout=timeout
            ) as response:
                if response.status == 200:
                    try:
                        return await response.json()
                    except (aiohttp.ContentTypeError, ValueError) as err:
                        raise KollektivtrafikApiError(
                            f"Invalid JSON response from API: {err}"
                        ) from err

                # Handle specific error codes used by our config_flow
                if response.status == 403:
                    raise KollektivtrafikApiError("403: Invalid API key")
                if response.status == 404:
                    raise KollektivtrafikApiError("404: Stop ID not found")

                # Catch-all for other HTTP errors (500, 429, etc)
                response.raise_for_status()
                return await response.json()

        except asyncio.TimeoutError as err:
            raise KollektivtrafikApiError("Realtime API request timed out") from err
        except aiohttp.ClientError as err:
            raise KollektivtrafikApiError(
                f"Realtime API connection error: {err}"
            ) from err

    async def validate_api_key(self, test_stop_id: str = "740098000") -> bool:
        """Validate API key by making a test request."""
        try:
            await self.get_departures(test_stop_id)
            return True
        except KollektivtrafikApiError as err:
            _LOGGER.debug("Validation failed: %s", err)
            return False
