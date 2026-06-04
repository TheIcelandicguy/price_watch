"""Tests for the extractor module."""

from __future__ import annotations

import pytest

from custom_components.price_watch import extractor as extractor_mod
from custom_components.price_watch.extractor import (
    _normalize_cookies,
    extract_product,
    preprocess_html,
    try_jsonld,
)


SAMPLE_JSONLD_PRODUCT = """
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "ASRock Z890 Taichi Lite",
  "image": "https://example.com/img.jpg",
  "sku": "Z890-TAICHI-LITE",
  "brand": {"@type": "Brand", "name": "ASRock"},
  "offers": {
    "@type": "Offer",
    "price": "4999.00",
    "priceCurrency": "NOK",
    "availability": "https://schema.org/InStock"
  }
}
</script>
</head>
<body><h1>Product page</h1></body>
</html>
"""

SAMPLE_JSONLD_GRAPH = """
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "BreadcrumbList"},
    {
      "@type": "Product",
      "name": "Test product",
      "offers": {"price": 1234.5, "priceCurrency": "EUR", "availability": "OutOfStock"}
    }
  ]
}
</script>
"""

SAMPLE_NO_JSONLD = "<html><body><div>Just a price: 100 NOK</div></body></html>"


def test_jsonld_basic_product():
    result = try_jsonld(SAMPLE_JSONLD_PRODUCT)
    assert result is not None
    assert result["title"] == "ASRock Z890 Taichi Lite"
    assert result["price"] == 4999.0
    assert result["currency"] == "NOK"
    assert result["in_stock"] is True
    assert result["image_url"] == "https://example.com/img.jpg"
    assert result["sku"] == "Z890-TAICHI-LITE"
    assert result["retailer"] == "ASRock"


def test_jsonld_graph_format():
    result = try_jsonld(SAMPLE_JSONLD_GRAPH)
    assert result is not None
    assert result["title"] == "Test product"
    assert result["price"] == 1234.5
    assert result["currency"] == "EUR"
    assert result["in_stock"] is False


def test_jsonld_returns_none_when_absent():
    assert try_jsonld(SAMPLE_NO_JSONLD) is None


def test_jsonld_handles_malformed():
    bad = '<script type="application/ld+json">not json{</script>'
    assert try_jsonld(bad) is None


def test_preprocess_strips_scripts_and_styles():
    html = """
    <html>
    <head>
      <style>body { color: red; }</style>
      <script>alert(1)</script>
    </head>
    <body>
      <noscript>noscript content</noscript>
      <svg width="100"><path/></svg>
      <div>real content</div>
      <iframe src="ad"></iframe>
    </body>
    </html>
    """
    cleaned, _ = preprocess_html(html)
    assert "alert(1)" not in cleaned
    assert "color: red" not in cleaned
    assert "noscript content" not in cleaned
    assert "<svg" not in cleaned
    assert "<iframe" not in cleaned
    assert "real content" in cleaned


def test_preprocess_strips_hidden_elements():
    html = '<div><span hidden>hidden content</span><span>visible</span></div>'
    cleaned, _ = preprocess_html(html)
    assert "hidden content" not in cleaned
    assert "visible" in cleaned


def test_preprocess_collapses_whitespace():
    html = "<div>a   \n   b\t\tc</div>"
    cleaned, _ = preprocess_html(html)
    assert "a b c" in cleaned


def test_content_hash_stable_across_volatile_bits():
    """Same product page with different timestamps and CSRF tokens hashes the same."""
    html_template = """
    <html><body>
    <input type="hidden" name="csrf_token" value="{token}">
    <span data-timestamp="{ts}">Product X</span>
    <div class="price">99.00 NOK</div>
    </body></html>
    """
    _, hash1 = preprocess_html(html_template.format(token="abc123def", ts="1730000000"))
    _, hash2 = preprocess_html(html_template.format(token="zzz999www", ts="1730005000"))
    assert hash1 == hash2


def test_content_hash_changes_on_real_change():
    """Same template, different price → different hash."""
    html_template = '<html><body><div class="price">{price}</div></body></html>'
    _, hash1 = preprocess_html(html_template.format(price="99.00"))
    _, hash2 = preprocess_html(html_template.format(price="89.00"))
    assert hash1 != hash2


def test_jsonld_array_image():
    """Some sites use array of image URLs."""
    html = """
    <script type="application/ld+json">
    {"@type": "Product", "name": "X", "image": ["url1", "url2"],
     "offers": {"price": 10, "priceCurrency": "USD"}}
    </script>
    """
    result = try_jsonld(html)
    assert result is not None
    assert result["image_url"] == "url1"


def test_jsonld_offers_as_list():
    """Some sites wrap offers in a list."""
    html = """
    <script type="application/ld+json">
    {"@type": "Product", "name": "X",
     "offers": [{"price": 10, "priceCurrency": "USD"}]}
    </script>
    """
    result = try_jsonld(html)
    assert result is not None
    assert result["price"] == 10


def test_jsonld_aggregate_offer_low_price():
    """AggregateOffer (price range) has no `price`, only lowPrice/highPrice.

    Sites like logitech.com advertise a range across configurations. The
    low price is what a shopper can actually pay, so we track that. Without
    the fallback the candidate is skipped and extraction reports "No JSON-LD
    found", which hard-fails the free/no-AI tier.
    """
    html = """
    <script type="application/ld+json">
    [{"@type": "Product", "name": "MX Master 3S",
      "offers": {"@type": "AggregateOffer", "priceCurrency": "USD",
                 "availability": "https://schema.org/InStock",
                 "lowPrice": 89.99, "highPrice": 99.99, "offerCount": "1"}},
     {"@type": "BreadcrumbList", "itemListElement": []}]
    </script>
    """
    result = try_jsonld(html)
    assert result is not None
    assert result["price"] == 89.99
    assert result["currency"] == "USD"
    assert result["in_stock"] is True


def test_jsonld_aggregate_offer_high_price_fallback():
    """When only highPrice is present, fall back to it rather than failing."""
    html = """
    <script type="application/ld+json">
    {"@type": "Product", "name": "Y",
     "offers": {"@type": "AggregateOffer", "priceCurrency": "EUR",
                "highPrice": 42.0}}
    </script>
    """
    result = try_jsonld(html)
    assert result is not None
    assert result["price"] == 42.0


# --- cookie normalization (the shape the extractor reads at fetch time) ---

def test_normalize_cookies_header_string():
    """The common DevTools copy-paste form: a single Cookie header value."""
    assert _normalize_cookies("session-id=123; ubid=ABC; prefs=GBP") == {
        "session-id": "123",
        "ubid": "ABC",
        "prefs": "GBP",
    }


def test_normalize_cookies_dict():
    """A {name: value} mapping is accepted and stringified."""
    assert _normalize_cookies({"a": 1, "b": "2"}) == {"a": "1", "b": "2"}


def test_normalize_cookies_list_of_dicts():
    """The list-of-dicts form documented in services.yaml (and produced by
    browser cookie APIs) must also be accepted."""
    cookies = [
        {"name": "session-id", "value": "123", "domain": ".amazon.com"},
        {"name": "ubid", "value": "ABC", "path": "/"},
    ]
    assert _normalize_cookies(cookies) == {"session-id": "123", "ubid": "ABC"}


def test_normalize_cookies_empty_and_garbage():
    assert _normalize_cookies("") is None
    assert _normalize_cookies(None) is None
    assert _normalize_cookies([]) is None
    assert _normalize_cookies([{"no": "name"}]) is None
    assert _normalize_cookies(42) is None


def test_parse_store_availability_husa():
    """Per-store stock parsed from a Húsa-style availability section."""
    from custom_components.price_watch.extractor import _parse_store_availability

    html = """
    <div class="product-availability-section">
      <div class="row">
        <div class="col-md-3"><span class="availability-label">Til á lager</span></div>
        <div class="col-md-9"><strong><a href="#">Selfoss</a>, </strong>
          <strong><a href="#">Borgarnes</a></strong></div>
      </div>
      <div class="row">
        <div class="col-md-3"><span class="availability-label">Fá eintök</span></div>
        <div class="col-md-9"><strong>Hafnarfjörður</strong></div>
      </div>
      <div class="row">
        <div class="col-md-3"><span class="availability-label">Uppselt</span></div>
        <div class="col-md-9"><strong>Akureyri</strong></div>
      </div>
    </div>
    """
    res = _parse_store_availability(html)
    assert res is not None
    by_store = {r["store"]: r["status"] for r in res}
    assert by_store["Selfoss"] == "in_stock"
    assert by_store["Borgarnes"] == "in_stock"
    assert by_store["Hafnarfjörður"] == "limited"
    assert by_store["Akureyri"] == "sold_out"


def test_parse_store_availability_absent_returns_none():
    from custom_components.price_watch.extractor import _parse_store_availability

    assert _parse_store_availability("<html><body>nothing here</body></html>") is None


# --- cookies-only parser must fetch WITH cookies, then use JSON-LD ---
# Regression: a parser carrying only request_cookies (no selectors) used to be
# forced down the CSS path, which raised "did not extract a title" and — with
# no AI provider — failed the whole extraction, never reaching JSON-LD.

@pytest.mark.asyncio
async def test_cookies_only_parser_falls_through_to_jsonld(monkeypatch):
    captured = {}

    async def fake_fetch_html(url, session=None, method="GET", body=None,
                              extra_headers=None, cookies=None):
        captured["url"] = url
        captured["cookies"] = cookies
        return SAMPLE_JSONLD_PRODUCT

    monkeypatch.setattr(extractor_mod, "fetch_html", fake_fetch_html)

    # No AI provider — the previously-broken free-tier case.
    result = await extract_product(
        url="https://example.com/dp/X",
        session=None,
        ai_provider=None,
        custom_parser={"request_cookies": "session-id=123; ubid=ABC"},
    )

    # Reached JSON-LD rather than failing on an empty CSS parse.
    assert result.method == "jsonld"
    assert result.price == 4999.0
    # And the cookies were actually applied to the fetch.
    assert captured["cookies"] == {"session-id": "123", "ubid": "ABC"}


@pytest.mark.asyncio
async def test_real_css_parser_still_uses_custom_path(monkeypatch):
    """A parser WITH selectors must not be treated as cookies-only."""
    html = '<html><body><h1>Widget</h1><span class="p">19.99</span></body></html>'

    async def fake_fetch_html(url, session=None, method="GET", body=None,
                              extra_headers=None, cookies=None):
        return html

    monkeypatch.setattr(extractor_mod, "fetch_html", fake_fetch_html)

    result = await extract_product(
        url="https://example.com/p",
        session=None,
        ai_provider=None,
        custom_parser={
            "type": "css",
            "selectors": {"price": ".p", "title": "h1"},
            "transforms": {"price": "price_clean"},
        },
    )
    assert result.method == "custom"
    assert result.price == 19.99
