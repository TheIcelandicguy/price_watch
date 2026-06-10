"""Tests for the ELKO preset (regex price from embedded JSON)."""

from __future__ import annotations

from custom_components.price_watch.parsers import apply_custom_parser
from custom_components.price_watch.presets import elko, find_preset

ELKO_URL = "https://elko.is/vorur/philips-phs5537-2022-sjonvarp-286633/24PHS553712"


def test_elko_matches_product_url():
    assert elko.matches(ELKO_URL) is True
    assert elko.matches("https://elko.is/") is False
    assert elko.matches("https://www.newegg.com/p/X") is False


def test_find_preset_picks_elko():
    preset = find_preset(ELKO_URL)
    assert preset is not None
    assert preset.NAME == "ELKO"


def test_elko_parser_extracts_price_and_title():
    html = (
        '<html><head>'
        '<meta property="og:title" content="Philips 24&quot; PHS5537 LED sjónvarp (2022)">'
        '<meta property="og:image" content="https://elko.is/img/x.jpg">'
        '</head><body>'
        '<script>window.__DATA__ = {"product":{"price":44994,"sku":"24PHS5537"}}</script>'
        '</body></html>'
    )
    parser = elko.build_parser(ELKO_URL)
    data = apply_custom_parser(html, parser)
    assert data["price"] == 44994.0
    assert data["title"].startswith("Philips 24")
    assert data["currency"] == "ISK"
    assert data["retailer"] == "ELKO"
    assert data["image_url"] == "https://elko.is/img/x.jpg"
