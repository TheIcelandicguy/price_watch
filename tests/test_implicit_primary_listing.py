"""Tests for the implicit primary listing.

Products created by the "Add by URL" config flow or by track_product
from the panel (source panel_track) have a primary listing that exists
only as entry.data.url — nothing writes it into options["listings"].
Adding a second listing to such a product used to make that implicit
primary look like an orphan, so the next reload pruned it and its
sensors silently re-pointed at the newly added listing.

_ensure_primary_listing is exercised directly on a stand-in object.
StorageMixin borrows its attributes from the concrete coordinator via a
TYPE_CHECKING block rather than requiring them at runtime, so a plain
namespace with the right fields is a faithful caller and keeps these
tests free of a full Home Assistant fixture.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from custom_components.price_watch import _materialize_primary_listing
from custom_components.price_watch.coordinator_storage import StorageMixin
from custom_components.price_watch.store import empty_listing_state

ENTRY_ID = "01JABCDEFGHJKMNPQRSTVWXYZ"
PRIMARY_ID = f"l_{ENTRY_ID[-12:].lower()}"
PRIMARY_URL = "https://www.tolvutek.is/vara/rtx-5080"
OTHER_ID = "l_abc123abc123"


def _entry(url: str = PRIMARY_URL, listings: list | None = None):
    return SimpleNamespace(
        entry_id=ENTRY_ID,
        data={"entry_type": "product", "url": url},
        options={"listings": listings} if listings is not None else {},
    )


def _coord(entry, listings: dict[str, dict[str, Any]] | None = None):
    """A stand-in carrying only what _ensure_primary_listing touches."""
    return SimpleNamespace(
        entry=entry,
        _listings=listings if listings is not None else {},
        _primary_listing_id=PRIMARY_ID,
        _listing_results={},
        _product_state={
            "alternatives": [],
            "alternatives_fetched_at": None,
            "alternatives_error": None,
        },
        _state=empty_listing_state(),
    )


def _sync(coord) -> None:
    StorageMixin._ensure_primary_listing(coord)


def _with_history(*prices: float) -> dict[str, Any]:
    state = empty_listing_state()
    state["history"] = [{"price": p} for p in prices]
    state["lowest"] = min(prices) if prices else None
    return state


# --- the reported bug -------------------------------------------------


def test_add_listing_does_not_prune_the_implicit_primary():
    # A panel-tracked product: url in entry.data, primary never declared.
    # add_listing has since declared one other listing.
    entry = _entry(listings=[{"id": OTHER_ID, "url": "https://elko.is/x"}])
    coord = _coord(
        entry,
        {PRIMARY_ID: _with_history(129900), OTHER_ID: empty_listing_state()},
    )

    _sync(coord)

    assert PRIMARY_ID in coord._listings, "implicit primary was pruned as an orphan"
    assert OTHER_ID in coord._listings


def test_implicit_primary_keeps_its_history_and_sensor_alias():
    entry = _entry(listings=[{"id": OTHER_ID, "url": "https://elko.is/x"}])
    coord = _coord(
        entry,
        {PRIMARY_ID: _with_history(129900, 119900), OTHER_ID: empty_listing_state()},
    )

    _sync(coord)

    # The primary's own history survives...
    assert len(coord._listings[PRIMARY_ID]["history"]) == 2
    assert coord._listings[PRIMARY_ID]["lowest"] == 119900
    # ...and self._state still aliases the primary, not the new listing,
    # so its sensors keep reading the right data.
    assert coord._primary_listing_id == PRIMARY_ID
    assert coord._state is coord._listings[PRIMARY_ID]


def test_primary_survives_several_added_listings():
    entry = _entry(
        listings=[
            {"id": "l_111111111111", "url": "https://elko.is/x"},
            {"id": "l_222222222222", "url": "https://rafland.is/x"},
        ]
    )
    coord = _coord(
        entry,
        {
            PRIMARY_ID: _with_history(129900),
            "l_111111111111": empty_listing_state(),
            "l_222222222222": empty_listing_state(),
        },
    )

    _sync(coord)

    assert set(coord._listings) == {PRIMARY_ID, "l_111111111111", "l_222222222222"}


def test_primary_is_declared_even_with_no_stored_state_yet():
    # First setup after track_product: nothing in storage at all.
    entry = _entry(listings=[{"id": OTHER_ID, "url": "https://elko.is/x"}])
    coord = _coord(entry, {})

    _sync(coord)

    assert PRIMARY_ID in coord._listings
    assert coord._state is coord._listings[PRIMARY_ID]


# --- paths that must keep working ------------------------------------


def test_url_only_entry_with_nothing_declared():
    coord = _coord(_entry(), {})
    _sync(coord)
    assert set(coord._listings) == {PRIMARY_ID}


def test_v1_migrated_entry_without_an_entry_url():
    # Back-compat branch (b): no url, nothing declared, but storage holds
    # the deterministic primary.
    coord = _coord(_entry(url=""), {PRIMARY_ID: _with_history(9900)})
    _sync(coord)
    assert PRIMARY_ID in coord._listings


def test_shell_entry_does_not_conjure_a_primary():
    # No entry url — the first listing was added later with a random id
    # and becomes the runtime primary.
    entry = _entry(url="", listings=[{"id": OTHER_ID, "url": "https://elko.is/x"}])
    coord = _coord(entry, {OTHER_ID: empty_listing_state()})

    _sync(coord)

    assert PRIMARY_ID not in coord._listings
    assert coord._primary_listing_id == OTHER_ID
    assert coord._state is coord._listings[OTHER_ID]


def test_shell_entry_with_no_listings_uses_the_sentinel():
    coord = _coord(_entry(url=""), {})
    _sync(coord)
    assert coord._listings == {}
    # self._state is a throwaway dict, not wired into _listings.
    assert coord._state["history"] == []


def test_genuine_orphans_are_still_pruned():
    entry = _entry(listings=[{"id": "l_111111111111", "url": "https://elko.is/x"}])
    coord = _coord(
        entry,
        {
            PRIMARY_ID: empty_listing_state(),
            "l_111111111111": empty_listing_state(),
            "l_999999999999": _with_history(500),  # removed from options
        },
    )
    coord._listing_results["l_999999999999"] = object()

    _sync(coord)

    assert "l_999999999999" not in coord._listings
    assert "l_999999999999" not in coord._listing_results
    assert set(coord._listings) == {PRIMARY_ID, "l_111111111111"}


def test_declared_primary_is_not_duplicated():
    # Once edit_listing has materialized it, the auto-declare is a no-op.
    entry = _entry(
        listings=[
            {"id": PRIMARY_ID, "url": PRIMARY_URL},
            {"id": "l_111111111111", "url": "https://elko.is/x"},
        ]
    )
    coord = _coord(
        entry,
        {PRIMARY_ID: _with_history(129900), "l_111111111111": empty_listing_state()},
    )

    _sync(coord)

    assert set(coord._listings) == {PRIMARY_ID, "l_111111111111"}
    assert coord._state is coord._listings[PRIMARY_ID]


def test_sync_is_idempotent():
    entry = _entry(listings=[{"id": "l_111111111111", "url": "https://elko.is/x"}])
    coord = _coord(
        entry,
        {PRIMARY_ID: _with_history(129900), "l_111111111111": empty_listing_state()},
    )

    _sync(coord)
    first = set(coord._listings)
    _sync(coord)

    assert set(coord._listings) == first
    assert coord._listings[PRIMARY_ID]["lowest"] == 129900


def test_malformed_options_listings_are_tolerated():
    entry = _entry(listings=["nonsense", {"no_id": True}, {"id": ""}])
    coord = _coord(entry, {PRIMARY_ID: empty_listing_state()})

    _sync(coord)

    assert set(coord._listings) == {PRIMARY_ID}


# --- the service-side half of the fix ---------------------------------


def test_materialize_declares_the_primary_from_entry_url():
    listings: list = []
    created = _materialize_primary_listing(_entry(listings=[]), listings)

    assert created is not None
    assert listings == [created]
    assert created["id"] == PRIMARY_ID
    assert created["url"] == PRIMARY_URL
    assert created["retailer"] == "Tolvutek"


def test_materialize_is_a_noop_when_already_declared():
    listings = [{"id": PRIMARY_ID, "url": PRIMARY_URL, "retailer": "Tolvutek"}]
    assert _materialize_primary_listing(_entry(listings=listings), listings) is None
    assert len(listings) == 1


def test_materialize_is_a_noop_for_a_shell_entry():
    listings: list = []
    assert _materialize_primary_listing(_entry(url=""), listings) is None
    assert listings == []
