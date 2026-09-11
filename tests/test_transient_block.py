"""Tests for the bot-wall / CAPTCHA "flap" fix.

A retailer that challenges every other request used to make a listing's
sensors alternate between a price and unavailable: the wall page (or a
403/429) became a generic ExtractionError, which became UpdateFailed,
which took the whole coordinator tick down for that poll. The fetch
layer now classifies those responses as TransientBlockError and the
update path keeps the last known result instead.

The coordinator half is exercised on a stand-in object, the same way
test_implicit_primary_listing.py drives StorageMixin: UpdateMixin only
declares the attributes it borrows under TYPE_CHECKING, so a small class
with the right members is a faithful caller and no HA fixture is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.price_watch import coordinator_update as cu
from custom_components.price_watch import extractor as extractor_mod
from custom_components.price_watch.coordinator_update import UpdateMixin
from custom_components.price_watch.extractor import (
    ExtractionError,
    ExtractionResult,
    TransientBlockError,
    _raise_if_blocked,
    extract_product,
)
from custom_components.price_watch.store import empty_listing_state

URL = "https://www.example.is/vara/1"
AMAZON_WALL = """<html><body><h4>Weiter shoppen</h4>
<p>Klicke auf die Schaltfläche unten, um weiter zu shoppen.</p></body></html>"""
CAPTCHA = """<html><body><form action="/errors/validateCaptcha">
Enter the characters you see below</form></body></html>"""
PRODUCT = "<html><body><h1>RTX 5080</h1><span>129.900 kr.</span></body></html>"


# --- classification -----------------------------------------------------


def test_block_statuses_raise_transient():
    for status in (403, 429):
        with pytest.raises(TransientBlockError):
            _raise_if_blocked(status, "Access Denied", URL)


def test_bot_wall_body_at_200_raises_transient():
    with pytest.raises(TransientBlockError):
        _raise_if_blocked(200, AMAZON_WALL, URL)
    with pytest.raises(TransientBlockError):
        _raise_if_blocked(200, CAPTCHA, URL)


def test_real_page_passes():
    _raise_if_blocked(200, PRODUCT, URL)
    _raise_if_blocked(304, "", URL)


def test_missing_page_and_outage_are_not_blocks():
    # 404/410 = product gone, 5xx = retailer down. Both stay ordinary
    # ExtractionErrors raised by the callers' generic >= 400 path, so the
    # coordinator still marks them as failures rather than papering over.
    for status in (404, 410, 500, 502, 503):
        _raise_if_blocked(status, "", URL)


def test_wall_markers_are_not_matched_in_error_bodies():
    # A 4xx/5xx whose body happens to mention a marker is classified by
    # status, not body — only 2xx/3xx bodies are sniffed.
    _raise_if_blocked(500, AMAZON_WALL, URL)


def test_transient_block_is_an_extraction_error():
    # Existing `except ExtractionError` handlers keep catching it.
    assert issubclass(TransientBlockError, ExtractionError)


def test_empty_body_is_not_a_wall():
    _raise_if_blocked(200, "", URL)
    _raise_if_blocked(200, None, URL)


# --- extract_product propagates it unwrapped -----------------------------


async def test_extract_product_propagates_transient_block():
    async def walled(*args: Any, **kwargs: Any) -> str:
        raise TransientBlockError(f"Bot wall from {URL}")

    with patch.object(extractor_mod, "fetch_html", walled):
        with pytest.raises(TransientBlockError):
            await extract_product(URL, session=None)


async def test_extract_product_propagates_transient_block_via_custom_parser():
    async def walled(*args: Any, **kwargs: Any) -> str:
        raise TransientBlockError(f"HTTP 403 from {URL}")

    parser = {"type": "css", "selectors": {"price": ".price", "title": "h1"}}
    with patch.object(extractor_mod, "fetch_html", walled):
        with pytest.raises(TransientBlockError):
            await extract_product(URL, session=None, custom_parser=parser)


# --- the coordinator keeps the last known result -------------------------


def _result(price: float = 129900.0) -> ExtractionResult:
    return ExtractionResult(
        title="RTX 5080",
        price=price,
        currency="ISK",
        in_stock=True,
        stock_count=None,
        image_url=None,
        sku=None,
        retailer="Tölvutek",
        content_hash="abc",
        cost_usd=0.0,
        method="jsonld",
        raw={},
    )


class _Coord:
    """Just the members _async_update_one_listing touches before/inside
    its error handling."""

    def __init__(self, previous: ExtractionResult | None):
        self.hass = object()
        self.url = URL
        self._primary_listing_id = "l_primary"
        self._variant_options = None
        self._ai_provider = None
        self._listing_results: dict[str, ExtractionResult] = {}
        if previous is not None:
            self._listing_results["l_primary"] = previous
            self._listing_results["l_secondary"] = previous
        self.price_local_calls: list[ExtractionResult] = []

    def _get_listing_config(self, listing_id: str) -> dict[str, Any]:
        return {"url": URL} if listing_id == "l_secondary" else {}

    def effective_custom_parser(self, listing_id: str):
        return None

    async def _update_price_local(self, result: ExtractionResult) -> None:
        self.price_local_calls.append(result)


def _raising(exc: Exception):
    async def _extract(*args: Any, **kwargs: Any):
        raise exc

    return _extract


def _no_session(hass):
    return None


async def _run(coord: _Coord, listing_id: str, listing: dict, exc: Exception):
    with patch.object(cu, "extract_product", _raising(exc)), patch.object(
        cu, "async_get_clientsession", _no_session
    ):
        return await UpdateMixin._async_update_one_listing(coord, listing_id, listing)


async def test_block_on_primary_keeps_previous_result():
    previous = _result()
    coord = _Coord(previous)
    listing = empty_listing_state()

    got = await _run(coord, "l_primary", listing, TransientBlockError("HTTP 429"))

    assert got is previous
    # Nothing written: no history row, no last_check, no hash.
    assert listing["history"] == []
    assert listing.get("last_check") is None
    assert listing.get("last_hash") is None
    # FX still refreshed for the primary, as on the UNCHANGED path.
    assert coord.price_local_calls == [previous]


async def test_block_on_secondary_keeps_previous_without_fx():
    previous = _result()
    coord = _Coord(previous)

    got = await _run(coord, "l_secondary", empty_listing_state(), TransientBlockError("wall"))

    assert got is previous
    assert coord.price_local_calls == []


async def test_block_with_no_previous_still_fails():
    # First poll after a restart lands on a wall: there is nothing to keep,
    # so it is an ordinary failure and the sensors stay unavailable until a
    # real page comes back.
    coord = _Coord(previous=None)
    with pytest.raises(UpdateFailed):
        await _run(coord, "l_primary", empty_listing_state(), TransientBlockError("wall"))


async def test_ordinary_extraction_error_still_fails_even_with_previous():
    # Only blocks are soft. A page that came back but had no price is a
    # real failure and must still surface.
    coord = _Coord(_result())
    with pytest.raises(UpdateFailed):
        await _run(
            coord, "l_primary", empty_listing_state(),
            ExtractionError("No JSON-LD found and no AI provider configured"),
        )
