"""FX rate fetching and caching for Price Watch.

Uses frankfurter.dev (free, no auth, ECB rates, daily updates).
Rates are cached in HA storage for 24h to avoid hammering the API.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    FX_API_URL,
    FX_CACHE_TTL_HOURS,
    FX_STORAGE_KEY,
    HTTP_TIMEOUT,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class FxRateError(Exception):
    """Raised when an FX rate cannot be obtained."""


class FxRates:
    """Manages FX rates for converting product prices to a home currency.

    Strategy:
    - One Store per HA instance, keyed by the base currency we last fetched.
    - On each conversion, check cache age; refetch if stale.
    - Cache the full ECB rate matrix (one fetch covers all conversions).
    """

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        self.hass = hass
        self.session = session
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, FX_STORAGE_KEY)
        # In-memory cache; backed by store. Shape:
        # {"base": "EUR", "rates": {"NOK": 11.42, "ISK": 152.3, ...}, "fetched": "2026-05-01T..."}
        self._cache: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def _load(self) -> dict[str, Any] | None:
        if self._cache is None:
            self._cache = await self._store.async_load()
        return self._cache

    async def _save(self, data: dict[str, Any]) -> None:
        self._cache = data
        await self._store.async_save(data)

    def _is_fresh(self, data: dict[str, Any] | None) -> bool:
        if not data or "fetched" not in data:
            return False
        try:
            fetched = datetime.fromisoformat(data["fetched"])
        except ValueError:
            return False
        age = datetime.now(timezone.utc) - fetched
        return age < timedelta(hours=FX_CACHE_TTL_HOURS)

    async def _refetch(self, base: str) -> dict[str, Any]:
        """Fetch fresh rates from frankfurter.dev with `base` as base currency."""
        url = f"{FX_API_URL}?base={base.upper()}"
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=10)
        try:
            async with self.session.get(url, timeout=timeout) as response:
                if response.status >= 400:
                    raise FxRateError(f"FX API HTTP {response.status} for base={base}")
                payload = await response.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            raise FxRateError(f"FX API network error: {type(err).__name__}: {err}") from err

        rates = payload.get("rates")
        if not isinstance(rates, dict):
            raise FxRateError(f"FX API returned no 'rates' for base={base}")
        # Frankfurter doesn't include base->base in `rates`; add it manually for symmetry.
        rates[base.upper()] = 1.0

        data = {
            "base": base.upper(),
            "rates": rates,
            "fetched": datetime.now(timezone.utc).isoformat(),
        }
        await self._save(data)
        return data

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> float | None:
        """Convert `amount` from one currency to another. Returns None on failure.

        Failures are non-fatal; we just log and return None so the consuming
        sensor stays Unknown rather than blocking the rest of the price fetch.
        """
        if not from_currency or not to_currency:
            return None
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        if from_currency == to_currency:
            return amount

        async with self._lock:
            data = await self._load()
            base = data.get("base") if data else None

            # Use cached rates if fresh AND base matches what we need
            need_refetch = (
                not self._is_fresh(data)
                or base != from_currency
            )

            if need_refetch:
                try:
                    data = await self._refetch(from_currency)
                except FxRateError as err:
                    _LOGGER.warning("Could not refresh FX rates: %s", err)
                    # If we have stale data with the right base, use it as best-effort
                    if data and data.get("base") == from_currency:
                        _LOGGER.info("Using stale FX rates as fallback")
                    else:
                        return None

        rate = (data or {}).get("rates", {}).get(to_currency)
        if rate is None:
            _LOGGER.warning(
                "FX rate %s->%s not available (rates only cover ECB-supported currencies)",
                from_currency, to_currency,
            )
            return None
        return round(amount * float(rate), 2)
