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
)

_LOGGER = logging.getLogger(__name__)

# Storage schema version for the FX rate cache. DELIBERATELY independent of
# the product-data STORAGE_VERSION: the FX cache is a trivial, fully
# disposable rate snapshot with its own (stable) shape. It was previously
# tied to STORAGE_VERSION, so bumping that to 2 for the product data-model
# migration orphaned every existing version-1 fx cache file — HA's Store
# then raised NotImplementedError ("no migration") on every load, which
# escaped convert() and silently disabled ALL home-currency conversion.
# Keep this at 1 to match existing files; never couple it to product data.
_FX_STORE_VERSION = 1


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
        self._store: Store[dict[str, Any]] = Store(
            hass, _FX_STORE_VERSION, FX_STORAGE_KEY
        )
        # In-memory cache; backed by store. Shape:
        # {"base": "EUR", "rates": {"NOK": 11.42, "ISK": 152.3, ...}, "fetched": "2026-05-01T..."}
        self._cache: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def _load(self) -> dict[str, Any] | None:
        if self._cache is None:
            try:
                self._cache = await self._store.async_load()
            except Exception as err:  # noqa: BLE001
                # A corrupt or unmigratable cache file must NOT break
                # conversion — treat it as "no cache" and let convert()
                # refetch. (Defends against any future Store schema drift.)
                _LOGGER.warning(
                    "FX rate cache could not be loaded (%s); refetching fresh",
                    err,
                )
                self._cache = None
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

        Cross-rate strategy: frankfurter returns the FULL ECB matrix on every
        call regardless of `base`, so a single cached matrix (in ANY base)
        can convert between any two currencies it lists — via
        ``amount * rate_to / rate_from`` (both expressed per the cached base).
        We therefore DON'T need the cache's base to equal `from_currency`,
        which was the old bug: a NOK-based cache forced a refetch for every
        USD product, and when that refetch failed the whole conversion
        returned None even though the cached matrix already held USD and ISK.
        We only refetch when the cache is stale or genuinely missing one of
        the two currencies, and we fall back to a stale matrix rather than
        giving up.
        """
        if not from_currency or not to_currency:
            return None
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        if from_currency == to_currency:
            return amount

        def _has_pair(d: dict[str, Any] | None) -> bool:
            rates = (d or {}).get("rates", {})
            return bool(rates.get(from_currency)) and bool(rates.get(to_currency))

        async with self._lock:
            data = await self._load()

            # Refetch only when the cache is stale OR doesn't list both
            # currencies. Reuse the existing base so the cached matrix stays
            # stable and broadly reusable across products (any base works for
            # cross-rating); fall back to from_currency when there's no cache.
            if not self._is_fresh(data) or not _has_pair(data):
                base = (data or {}).get("base") or from_currency
                try:
                    data = await self._refetch(base)
                except FxRateError as err:
                    _LOGGER.warning("Could not refresh FX rates: %s", err)
                    # Best-effort: a stale matrix that still lists both
                    # currencies beats an Unknown sensor for a price tracker.
                    if _has_pair(data):
                        _LOGGER.info(
                            "Using stale FX rates as fallback (base=%s, fetched %s)",
                            (data or {}).get("base"), (data or {}).get("fetched"),
                        )
                    else:
                        return None

        rates = (data or {}).get("rates", {})
        rate_from = rates.get(from_currency)
        rate_to = rates.get(to_currency)
        if not rate_from or not rate_to:
            _LOGGER.warning(
                "FX rate unavailable for %s or %s (cache base=%s lists %d "
                "currencies; only ECB-supported ones are covered)",
                from_currency, to_currency,
                (data or {}).get("base"), len(rates),
            )
            return None
        # Cross-rate through the cached base: 1 from_currency = (1/rate_from)
        # base; times rate_to converts to the target.
        return round(amount * float(rate_to) / float(rate_from), 2)
