"""Tests for the retailer→region shipping heuristic.

The case that matters most here is Iceland. It sits in the Nordics
geographically but not in their shipping arrangements, so the mainland
rule must not treat a .no or .se retailer as evidence that a parcel
reaches Reykjavík — and Komplett in particular has to come back as a
hard "no".
"""

from __future__ import annotations

from custom_components.price_watch.search.base import Alternative
from custom_components.price_watch.search.region_heuristic import (
    apply_to_alternative,
    evaluate_shipping,
)


def _evaluate(url: str, region: str, ai_guess: bool | None = None) -> bool | None:
    return evaluate_shipping(
        url=url,
        retailer="",
        user_region=region,
        ai_guess=ai_guess,
    )


def test_komplett_never_ships_to_iceland():
    for url in [
        "https://www.komplett.no/product/1234/some-gpu",
        "https://komplett.no/product/1234/some-gpu",
        "https://www.komplett.se/product/1234/some-gpu",
        "https://www.komplett.dk/product/1234/some-gpu",
    ]:
        assert _evaluate(url, "IS") is False, url


def test_komplett_block_overrides_a_confident_ai_yes():
    assert _evaluate("https://www.komplett.no/product/1", "IS", True) is False


def test_komplett_is_fine_for_mainland_nordic_users():
    # Blocking Komplett is region-specific, not a global ban.
    assert _evaluate("https://www.komplett.no/product/1", "NO") is True
    assert _evaluate("https://www.komplett.no/product/1", "SE") is True
    assert _evaluate("https://www.komplett.se/product/1", "DK") is True


def test_mainland_nordic_tld_is_not_a_yes_for_iceland():
    # The regression this file exists for: these used to return True
    # because IS was in the Nordic group. None means "no opinion", so
    # the AI's guess stands rather than being upgraded.
    for url in [
        "https://www.elkjop.no/product/1",
        "https://www.netonnet.se/product/1",
        "https://www.proshop.dk/product/1",
        "https://www.verkkokauppa.fi/product/1",
    ]:
        assert _evaluate(url, "IS") is None, url


def test_icelandic_tld_still_ships_to_iceland():
    assert _evaluate("https://www.tolvutek.is/vara/1", "IS") is True
    assert _evaluate("https://elko.is/vara/1", "IS") is True


def test_icelandic_tld_is_not_a_yes_for_mainland_users():
    # The reverse direction of the same mistake — Icelandic retailers
    # mostly don't ship to the mainland either.
    assert _evaluate("https://www.tolvutek.is/vara/1", "NO") is None
    assert _evaluate("https://www.tolvutek.is/vara/1", "SE") is None


def test_mainland_nordics_remain_interchangeable():
    assert _evaluate("https://www.netonnet.se/product/1", "NO") is True
    assert _evaluate("https://www.proshop.dk/product/1", "FI") is True
    assert _evaluate("https://www.elkjop.no/product/1", "DK") is True


def test_unrelated_rules_still_fire():
    assert _evaluate("https://www.newegg.com/p/1", "IS") is False
    assert _evaluate("https://www.aliexpress.com/item/1.html", "IS") is True
    assert _evaluate("https://www.prisjakt.no/produkt/1", "IS") is None
    assert _evaluate("https://www.amazon.de/dp/B01", "DE") is True
    assert _evaluate("https://www.amazon.de/dp/B01", "IS") is None


def test_no_region_means_no_opinion():
    assert _evaluate("https://www.komplett.no/product/1", "") is None


def test_region_code_is_case_insensitive():
    assert _evaluate("https://www.komplett.no/product/1", "is") is False


def test_apply_to_alternative_flips_the_ai_guess():
    alt = Alternative(
        title="RTX 5080",
        url="https://www.komplett.no/product/1234/rtx-5080",
        retailer="Komplett",
        ships_to_user_region=True,
    )
    apply_to_alternative(alt, "IS")
    assert alt.ships_to_user_region is False


def test_apply_to_alternative_leaves_unknowns_alone():
    alt = Alternative(
        title="RTX 5080",
        url="https://www.elkjop.no/product/1234/rtx-5080",
        retailer="Elkjøp",
        ships_to_user_region=True,
    )
    apply_to_alternative(alt, "IS")
    # Heuristic has no opinion, so the AI's guess survives untouched.
    assert alt.ships_to_user_region is True
