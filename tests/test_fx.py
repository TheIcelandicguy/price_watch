"""Tests for FX conversion: cross-rate, stale fallback, store-version decoupling.

These cover the bug where the FX cache Store shared the product-data
STORAGE_VERSION; bumping that to 2 orphaned every version-1 cache file, so
Store.async_load raised and silently disabled ALL home-currency conversion.
The fix decoupled the version, made convert() cross-rate through whatever
base the cached matrix has, and treat a stale matrix as a usable fallback.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.price_watch.const import STORAGE_VERSION
from custom_components.price_watch.fx import (
    FxRateError,
    FxRates,
    _FX_STORE_VERSION,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()


def test_fx_store_version_decoupled_from_product_storage():
    """The FX cache version must NOT track the product-data STORAGE_VERSION.

    Coupling them is what orphaned the version-1 cache when STORAGE_VERSION
    moved to 2 — Store.async_load then raised NotImplementedError on every
    load and disabled all conversion. Keep FX pinned at 1.
    """
    assert _FX_STORE_VERSION == 1
    # Guard against someone re-coupling them at a value other than 1.
    assert not (STORAGE_VERSION == _FX_STORE_VERSION and STORAGE_VERSION != 1)


@pytest.fixture
def fx(hass):
    # session is unused for these tests: a fresh, pair-complete cache means
    # convert() never refetches, and the failure tests monkeypatch _refetch.
    return FxRates(hass, session=None)


@pytest.mark.asyncio
async def test_convert_same_currency_is_noop(fx):
    assert await fx.convert(50.0, "USD", "USD") == 50.0


@pytest.mark.asyncio
async def test_convert_direct_base(fx):
    fx._cache = {
        "base": "USD",
        "rates": {"USD": 1.0, "ISK": 123.27},
        "fetched": _now_iso(),
    }
    assert await fx.convert(100.0, "USD", "ISK") == 12327.0


@pytest.mark.asyncio
async def test_convert_cross_rate_through_other_base(fx):
    """A NOK-based matrix converts USD->ISK without a same-base refetch."""
    fx._cache = {
        "base": "NOK",
        "rates": {"NOK": 1.0, "USD": 0.10762, "ISK": 13.2666},
        "fetched": _now_iso(),
    }
    got = await fx.convert(89.99, "USD", "ISK")
    # 89.99 * 13.2666 / 0.10762 ~= 11093
    assert got is not None
    assert round(got) == 11093


@pytest.mark.asyncio
async def test_stale_cache_used_when_refetch_fails(fx, monkeypatch):
    """A stale matrix that lists both currencies beats returning None."""
    fx._cache = {
        "base": "NOK",
        "rates": {"NOK": 1.0, "USD": 0.10762, "ISK": 13.2666},
        "fetched": _stale_iso(),
    }

    async def _boom(base):
        raise FxRateError("network down")

    monkeypatch.setattr(fx, "_refetch", _boom)
    got = await fx.convert(89.99, "USD", "ISK")
    assert got is not None
    assert round(got) == 11093


@pytest.mark.asyncio
async def test_returns_none_when_currency_unavailable(fx, monkeypatch):
    """No usable cache + failed refetch -> None (sensor Unknown, not wrong)."""
    fx._cache = None

    async def _boom(base):
        raise FxRateError("network down")

    monkeypatch.setattr(fx, "_refetch", _boom)
    assert await fx.convert(10.0, "USD", "ISK") is None
