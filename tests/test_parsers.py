"""Tests for custom parsers."""

from __future__ import annotations

import pytest

from custom_components.price_watch.parsers import (
    ParserError,
    _apply_transforms,
    apply_custom_parser,
)


def test_transforms_regex_strip():
    assert _apply_transforms("kr 1.299,00", "regex:[^0-9.,]") == "1.299,00"


def test_transforms_replace_and_float():
    assert _apply_transforms("1.299,00", "replace:.: |strip|replace:,:.|float") == 1299.0


def test_transforms_chain_full_pipeline():
    """A realistic price-cleaning pipeline."""
    raw = "Now: kr 4 999,00 NOK"
    cleaned = _apply_transforms(raw, "regex:[^0-9., ]|replace: :|replace:,:.|float")
    assert cleaned == 4999.00


def test_transforms_int():
    assert _apply_transforms("4999.50", "float|int") == 4999


def test_transforms_unknown_step_logs_and_continues():
    # Unknown transforms should be skipped without crashing
    assert _apply_transforms("hello", "lower|nonsense|strip") == "hello"


def test_css_parser_basic():
    html = """
    <html><body>
      <h1 class="title">Widget</h1>
      <span class="price">99.99</span>
    </body></html>
    """
    parser = {
        "type": "css",
        "selectors": {
            "title": "h1.title",
            "price": "span.price",
        },
        "transforms": {"price": "float"},
    }
    result = apply_custom_parser(html, parser)
    assert result["title"] == "Widget"
    assert result["price"] == 99.99


def test_css_parser_attribute_extraction():
    """Selector with @attr should pull an attribute, not text."""
    html = '<html><body><img class="hero" src="https://x/y.jpg"/><h1>T</h1><span>10</span></body></html>'
    parser = {
        "type": "css",
        "selectors": {
            "title": "h1",
            "price": "span",
            "image_url": "img.hero@src",
        },
        "transforms": {"price": "float"},
    }
    result = apply_custom_parser(html, parser)
    assert result["image_url"] == "https://x/y.jpg"


def test_css_parser_missing_required_field_raises():
    html = "<html><body><span class='price'>10</span></body></html>"
    parser = {
        "type": "css",
        "selectors": {"title": "h1.does-not-exist", "price": "span.price"},
        "transforms": {"price": "float"},
    }
    with pytest.raises(ParserError, match="title"):
        apply_custom_parser(html, parser)


def test_regex_parser_basic():
    html = '<div data-product="Widget"><span data-price="42.50"></span></div>'
    parser = {
        "type": "regex",
        "selectors": {
            "title": r'data-product="([^"]+)"',
            "price": r'data-price="([\d.]+)"',
        },
        "transforms": {"price": "float"},
    }
    result = apply_custom_parser(html, parser)
    assert result["title"] == "Widget"
    assert result["price"] == 42.50


def test_jsonpath_parser_basic():
    html = """
    <html><head>
      <script>
      window.__NEXT_DATA__ = {"props":{"pageProps":{"product":{"name":"Widget","price":42.5}}}};
      </script>
    </head></html>
    """
    parser = {
        "type": "jsonpath",
        "selectors": {
            "title": "__NEXT_DATA__:props.pageProps.product.name",
            "price": "__NEXT_DATA__:props.pageProps.product.price",
        },
        "transforms": {"price": "float"},
    }
    result = apply_custom_parser(html, parser)
    assert result["title"] == "Widget"
    assert result["price"] == 42.5


def test_unknown_parser_type_raises():
    with pytest.raises(ParserError, match="Unknown parser type"):
        apply_custom_parser("<html/>", {"type": "telepathy", "selectors": {}})


def test_regex_parser_priority_list_skips_cents_prefers_formatted():
    """A list of price patterns is tried in PRIORITY order. A decimal-guarded
    numeric pattern skips an integer-cents value (4999) so a later formatted
    pattern wins — the Amazon cents-misfire fix.
    """
    html = (
        "<title>Echo Dot</title>"
        '<script>{"priceToPay":{"amount":4999},'
        '"olpMessage":"1 option from $49.99"}</script>'
    )
    parser = {
        "type": "regex",
        "selectors": {
            "title": r"<title>([^<]+)</title>",
            "price": [
                r'"amount"\s*:\s*([0-9]+\.[0-9]{1,2})\b',  # decimal-required: skips 4999
                r"[$£€]\s*([0-9][0-9.,]*)",  # formatted "$49.99"
            ],
        },
        "transforms": {"price": "price_clean"},
    }
    result = apply_custom_parser(html, parser)
    assert result["price"] == 49.99


def test_regex_parser_list_first_match_wins():
    """First pattern in the list that matches wins; later ones aren't tried."""
    html = "<title>X</title><span>A: 11.11 B: 22.22</span>"
    parser = {
        "type": "regex",
        "selectors": {
            "title": r"<title>([^<]+)</title>",
            "price": [r"A:\s*([0-9.]+)", r"B:\s*([0-9.]+)"],
        },
        "transforms": {"price": "float"},
    }
    result = apply_custom_parser(html, parser)
    assert result["price"] == 11.11


def test_price_clean_simple_decimal():
    assert _apply_transforms("$49.99", "price_clean") == 49.99


def test_price_clean_comma_thousands():
    # "4,999" -> comma is a thousands separator (3 trailing digits).
    assert _apply_transforms("4,999", "price_clean") == 4999.0


def test_price_clean_period_thousands():
    # "$1.299" -> period is a thousands separator (3 trailing digits).
    assert _apply_transforms("$1.299", "price_clean") == 1299.0


def test_price_clean_euro_format():
    # "€1.299,99" -> period thousands + comma decimal.
    assert _apply_transforms("€1.299,99", "price_clean") == 1299.99


def test_default_currency_and_retailer_applied():
    html = "<html><body><h1>P</h1><span class='p'>10</span></body></html>"
    parser = {
        "type": "css",
        "selectors": {"title": "h1", "price": "span.p"},
        "transforms": {"price": "float"},
        "default_currency": "ISK",
        "default_retailer": "Tölvutek",
    }
    result = apply_custom_parser(html, parser)
    assert result["currency"] == "ISK"
    assert result["retailer"] == "Tölvutek"
