"""Tests for the refresh cycle, driven through the real coordinator.

The coordinator is split across mixins (update / storage / alternatives /
fx / events) and the existing tests drive those individually on stand-in
objects. That is the right shape for a unit test, but it leaves the
orchestration between them uncovered: whether one poll actually writes a
history row, moves the extremes and fires the events an automation is
built on, in that order, on the real object HA constructs.

So these load a config entry for real and then control what the page
returns, one poll at a time, through a small `_Page` holder. Each test
asserts on what a user or an automation would see afterwards: the
listing's result, its history, its lowest/highest, and the bus.

Event semantics worth keeping straight, since they are easy to get
backwards (see coordinator_update around the transition events):

  new_low      only once a lowest exists — never on the first observation
  price_drop   needs a known previous result, so never on the first poll
               after a restart
  target_hit   fires on the CROSSING, not on every poll under target
  discount     the retailer's own sale flag appearing, not any drop
"""

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components import price_watch as pw
from custom_components.price_watch import coordinator as coordinator_mod
from custom_components.price_watch import coordinator_update as cu
from custom_components.price_watch.const import (
    CONF_TARGET_PRICE,
    CONF_URL,
    DOMAIN,
    ENTRY_TYPE_PRODUCT,
    EVENT_BACK_IN_STOCK,
    EVENT_DISCOUNT,
    EVENT_NEW_LOW,
    EVENT_PRICE_DROP,
    EVENT_TARGET_HIT,
)
from custom_components.price_watch.extractor import ExtractionError, ExtractionResult

URL = "https://www.tolvutek.is/vara/rtx-5080"
START = 129900.0


def _result(
    price: float = START,
    *,
    in_stock: bool = True,
    original_price: float | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        title="RTX 5080",
        price=price,
        currency="ISK",
        in_stock=in_stock,
        retailer="Tolvutek",
        content_hash=f"hash-{price}-{in_stock}-{original_price}",
        method="jsonld",
        original_price=original_price,
    )


class _Page:
    """The retailer page, as the coordinator sees it.

    One instance per test; assign `.result` to decide what the next poll
    returns. A distinct content_hash per result matters — the update path
    skips extraction entirely when the page is unchanged, so two polls
    that returned identical objects would not produce two history rows.
    """

    def __init__(self, result: ExtractionResult | None = None) -> None:
        self.result = result if result is not None else _result()
        self.polls = 0

    async def extract(
        self, *args: Any, previous_hash: str | None = None, **kwargs: Any
    ) -> ExtractionResult:
        """Stand in for extract_product, including its UNCHANGED protocol.

        The real one raises ExtractionError("UNCHANGED") when the page it
        fetched hashes to the previous_hash the caller passed in, rather
        than returning a result — that is how the free tier avoids paying
        to re-extract a page that hasn't moved. Honouring it here is what
        makes the short-circuit observable from this seam.
        """
        self.polls += 1
        if previous_hash is not None and previous_hash == self.result.content_hash:
            raise ExtractionError("UNCHANGED")
        return self.result


@contextlib.contextmanager
def _offline(page: _Page):
    """Swap the fetch layer for `page` and keep HA's real session out.

    The session matters for teardown, not the assertions: HA's shared
    session resolves through aiodns, whose pycares resolver leaves a
    thread behind that the harness reports as a leak.
    """
    with patch.object(cu, "extract_product", page.extract), patch.object(
        cu, "async_get_clientsession", lambda hass: None
    ), patch.object(
        coordinator_mod, "async_get_clientsession", lambda hass: None
    ), patch.object(pw.random, "uniform", lambda a, b: 0):
        yield


async def _load(hass, page: _Page, *, target: float | None = None):
    """Load a by-URL product and let its first poll land.

    Returns the coordinator, already holding one observation — the state
    an entry is in moments after HA starts.
    """
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    options: dict[str, Any] = {}
    if target is not None:
        options[CONF_TARGET_PRICE] = target
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="RTX 5080",
        data={"entry_type": ENTRY_TYPE_PRODUCT, CONF_URL: URL},
        options=options,
    )
    entry.add_to_hass(hass)

    with _offline(page):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.last_update_success, coordinator.last_exception
    return coordinator


async def _poll(hass, coordinator, page: _Page, result: ExtractionResult):
    """Run one more poll returning `result`."""
    page.result = result
    with _offline(page):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert coordinator.last_update_success, coordinator.last_exception


# --- one poll ------------------------------------------------------------


async def test_first_poll_records_price_history_and_extremes(hass):
    page = _Page()
    coordinator = await _load(hass, page)

    listing_id = coordinator.primary_listing_id
    assert coordinator.get_listing_result(listing_id).price == START
    assert len(coordinator.history) == 1
    assert coordinator.history[-1]["price"] == START
    # With one observation the extremes are both that observation.
    assert coordinator.lowest == START
    assert coordinator.highest == START


async def test_first_poll_fires_no_transition_events(hass):
    """Nothing to compare against yet, so a fresh start must stay quiet —
    otherwise every HA restart pings the user."""
    drops = async_capture_events(hass, EVENT_PRICE_DROP)
    lows = async_capture_events(hass, EVENT_NEW_LOW)

    await _load(hass, _Page())

    assert drops == []
    assert lows == []


# --- a second, cheaper poll ----------------------------------------------


async def test_price_drop_and_new_low_fire_together(hass):
    page = _Page()
    coordinator = await _load(hass, page)
    drops = async_capture_events(hass, EVENT_PRICE_DROP)
    lows = async_capture_events(hass, EVENT_NEW_LOW)

    await _poll(hass, coordinator, page, _result(119900.0))

    assert len(drops) == 1
    assert len(lows) == 1
    assert coordinator.lowest == 119900.0
    assert coordinator.highest == START
    assert len(coordinator.history) == 2


async def test_event_payload_carries_the_documented_fields(hass):
    """Automations read these keys, so the shape is a contract."""
    page = _Page()
    coordinator = await _load(hass, page)
    drops = async_capture_events(hass, EVENT_PRICE_DROP)

    await _poll(hass, coordinator, page, _result(119900.0))

    payload = drops[0].data
    assert payload["price"] == 119900.0
    assert payload["previous_price"] == START
    assert payload["currency"] == "ISK"
    assert payload["url"] == URL
    assert payload["retailer"] == "Tolvutek"
    assert payload["in_stock"] is True
    assert payload["entry_id"] == coordinator.entry.entry_id
    # Per-listing events carry which listing moved.
    assert payload["listing_id"] == coordinator.primary_listing_id


async def test_a_rise_moves_highest_and_fires_nothing(hass):
    page = _Page()
    coordinator = await _load(hass, page)
    drops = async_capture_events(hass, EVENT_PRICE_DROP)
    lows = async_capture_events(hass, EVENT_NEW_LOW)

    await _poll(hass, coordinator, page, _result(139900.0))

    assert drops == []
    assert lows == []
    assert coordinator.highest == 139900.0
    assert coordinator.lowest == START


async def test_new_low_needs_to_beat_the_previous_low(hass):
    """Down, up, then down but not far enough: one new_low, not two."""
    page = _Page()
    coordinator = await _load(hass, page)
    lows = async_capture_events(hass, EVENT_NEW_LOW)

    await _poll(hass, coordinator, page, _result(119900.0))
    await _poll(hass, coordinator, page, _result(134900.0))
    await _poll(hass, coordinator, page, _result(124900.0))

    assert len(lows) == 1
    assert coordinator.lowest == 119900.0


# --- target and stock ----------------------------------------------------


async def test_target_hit_fires_on_the_crossing_only(hass):
    page = _Page()
    coordinator = await _load(hass, page, target=120000.0)
    hits = async_capture_events(hass, EVENT_TARGET_HIT)

    # Still above target.
    await _poll(hass, coordinator, page, _result(125900.0))
    assert hits == []

    # Crosses.
    await _poll(hass, coordinator, page, _result(119900.0))
    assert len(hits) == 1
    assert hits[0].data["target"] == 120000.0

    # Cheaper again, but it was already under — no second ping.
    await _poll(hass, coordinator, page, _result(118900.0))
    assert len(hits) == 1


async def test_back_in_stock_fires_on_the_transition(hass):
    page = _Page(_result(in_stock=False))
    coordinator = await _load(hass, page)
    back = async_capture_events(hass, EVENT_BACK_IN_STOCK)

    await _poll(hass, coordinator, page, _result(in_stock=True))

    assert len(back) == 1
    assert back[0].data["in_stock"] is True


async def test_discount_fires_when_the_sale_flag_appears(hass):
    """A retailer sale (original_price > price) is its own event, separate
    from any price drop, and carries the discount percentage."""
    page = _Page()
    coordinator = await _load(hass, page)
    sales = async_capture_events(hass, EVENT_DISCOUNT)

    await _poll(hass, coordinator, page, _result(99900.0, original_price=129900.0))

    assert len(sales) == 1
    assert sales[0].data["original_price"] == 129900.0
    assert sales[0].data["discount_percent"] == 23


# --- the unchanged-page shortcut -----------------------------------------


async def test_an_unchanged_page_reuses_the_last_result(hass):
    """A page that hasn't moved must not add a history row.

    Otherwise a product nobody is discounting still grows its history by a
    row every six hours, and the 30-row window quietly throws away the
    real price changes.
    """
    page = _Page()
    coordinator = await _load(hass, page)
    rows = len(coordinator.history)
    before = coordinator.get_listing_result(coordinator.primary_listing_id)

    # Same result object, so the hash the coordinator sends back matches
    # and the fake raises UNCHANGED, exactly as the extractor would.
    await _poll(hass, coordinator, page, page.result)

    assert len(coordinator.history) == rows
    # The previous result is kept, not replaced by a fresh equal one.
    assert coordinator.get_listing_result(coordinator.primary_listing_id) is before
