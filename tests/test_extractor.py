"""Tests for the extractor module."""

from __future__ import annotations

import pytest

from custom_components.price_watch import extractor as extractor_mod
from custom_components.price_watch.extractor import (
    _normalize_cookies,
    extract_product,
    list_byko_variants,
    list_variants,
    preprocess_html,
    try_byko_variant,
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


def test_jsonld_productgroup_uses_own_offer():
    """A ProductGroup with its OWN top-level offer (JYSK.ie shape) is read
    from the wrapper — its variants omit `name` and prefix the price with a
    currency symbol ("€475") the old path couldn't parse, so it returned None.
    """
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org/","@type":"ProductGroup",
     "name":"Gazebo NORDMARKA W3xL4xH2.78m grey",
     "image":["https://cdn/247872"],
     "brand":{"@type":"Brand","name":"JYSK"},
     "offers":{"@type":"Offer","priceCurrency":"EUR","price":"475",
               "availability":"https://schema.org/InStock"},
     "hasVariant":[
       {"@type":"Product","color":"Grey","size":"300x400",
        "offers":{"@type":"Offer","priceCurrency":"EUR","price":"€475"}}]}
    </script>
    """
    result = try_jsonld(html)
    assert result is not None
    assert result["title"] == "Gazebo NORDMARKA W3xL4xH2.78m grey"
    assert result["price"] == 475.0
    assert result["currency"] == "EUR"
    assert result["in_stock"] is True


def test_jsonld_productgroup_variant_only_price_with_symbol():
    """ProductGroup whose price lives ONLY in a variant, formatted '€475',
    still parses (currency symbol stripped in _offer_price)."""
    html = """
    <script type="application/ld+json">
    {"@type":"ProductGroup","name":"X",
     "hasVariant":[{"@type":"Product","name":"X 300x400",
        "offers":{"@type":"Offer","priceCurrency":"EUR","price":"€475"}}]}
    </script>
    """
    result = try_jsonld(html)
    assert result is not None
    assert result["price"] == 475.0


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


import asyncio as _asyncio  # noqa: E402


@pytest.mark.asyncio
async def test_fetch_slot_caps_global_concurrency(monkeypatch):
    """The global semaphore caps concurrent fetches across DIFFERENT hosts."""
    monkeypatch.setattr(extractor_mod, "_HOST_MIN_INTERVAL", 0.0)
    monkeypatch.setattr(extractor_mod, "_fetch_semaphore", None)
    monkeypatch.setattr(extractor_mod, "_MAX_CONCURRENT_FETCHES", 2)

    active = 0
    peak = 0

    async def worker(i: int) -> None:
        nonlocal active, peak
        async with extractor_mod._fetch_slot(f"https://h{i}.example/x"):
            active += 1
            peak = max(peak, active)
            await _asyncio.sleep(0.02)
            active -= 1

    await _asyncio.gather(*[worker(i) for i in range(6)])
    assert peak == 2


@pytest.mark.asyncio
async def test_fetch_slot_serializes_same_host(monkeypatch):
    """The per-host lock fully serializes fetches to the SAME host."""
    monkeypatch.setattr(extractor_mod, "_HOST_MIN_INTERVAL", 0.0)
    monkeypatch.setattr(extractor_mod, "_fetch_semaphore", None)
    monkeypatch.setattr(extractor_mod, "_MAX_CONCURRENT_FETCHES", 5)

    active = 0
    peak = 0

    async def worker() -> None:
        nonlocal active, peak
        async with extractor_mod._fetch_slot("https://same.example/x"):
            active += 1
            peak = max(peak, active)
            await _asyncio.sleep(0.02)
            active -= 1

    await _asyncio.gather(*[worker() for _ in range(4)])
    assert peak == 1


def test_searxng_normalizes_base_url():
    from custom_components.price_watch.search.searxng import SearxngSearchProvider

    assert SearxngSearchProvider("http://x:8080/")._base_url == "http://x:8080"
    assert SearxngSearchProvider("http://x:8080/search")._base_url == "http://x:8080"
    assert SearxngSearchProvider("http://x:8080/search/")._base_url == "http://x:8080"


@pytest.mark.asyncio
async def test_searxng_parses_results(monkeypatch):
    from custom_components.price_watch.search.searxng import SearxngSearchProvider

    p = SearxngSearchProvider("http://searx.local", session=object())

    async def fake_fetch(_query):
        return {
            "results": [
                {"url": "https://shop.is/a", "title": "Widget A", "content": "buy"},
                {"url": "", "title": "no url"},  # dropped: no url
                {"url": "https://searx.local/x", "title": "self"},  # dropped: self host
                {"url": "https://shop2.is/b", "title": "Widget B", "content": ""},
            ]
        }

    monkeypatch.setattr(p, "_fetch_json", fake_fetch)
    hits = await p.search("widget", max_results=10)
    assert [h.url for h in hits] == ["https://shop.is/a", "https://shop2.is/b"]
    assert hits[0].title == "Widget A"
    assert hits[0].snippet == "buy"


@pytest.mark.asyncio
async def test_searxng_respects_max_results(monkeypatch):
    from custom_components.price_watch.search.searxng import SearxngSearchProvider

    p = SearxngSearchProvider("http://searx.local", session=object())

    async def fake_fetch(_query):
        return {"results": [
            {"url": f"https://s{i}.is/x", "title": f"T{i}"} for i in range(10)
        ]}

    monkeypatch.setattr(p, "_fetch_json", fake_fetch)
    hits = await p.search("q", max_results=3)
    assert len(hits) == 3


def test_match_offer_link_host_suffix():
    from custom_components.price_watch.provider_config import match_offer_link

    links = [
        {"host": "byko.is", "url": "https://byko.is/tilbod"},
        {"host": "jysk.is", "url": "https://jysk.is/tilbodsvorur/"},
    ]
    # bare + www + path all match the bare host
    assert match_offer_link("https://byko.is/vara/x", links) == "https://byko.is/tilbod"
    assert match_offer_link("https://www.byko.is/vara/x", links) == "https://byko.is/tilbod"
    assert (
        match_offer_link("https://jysk.is/stok-vara/y", links)
        == "https://jysk.is/tilbodsvorur/"
    )
    # unknown host / empty
    assert match_offer_link("https://amazon.de/dp/z", links) is None
    assert match_offer_link("", links) is None


def test_is_on_sale():
    from custom_components.price_watch.extractor import ExtractionResult, is_on_sale

    def r(price, original):
        return ExtractionResult(
            title="x", price=price, currency="ISK", original_price=original
        )

    assert is_on_sale(r(80, 100)) is True          # struck-through original > price
    assert is_on_sale(r(100, None)) is False        # no original = not on sale
    assert is_on_sale(r(100, 100)) is False         # equal = not a discount
    assert is_on_sale(r(100, 90)) is False          # original below price = not on sale
    assert is_on_sale(None) is False                # no result


def test_extract_product_meta_husa():
    from custom_components.price_watch.extractor import _extract_product_meta

    html = (
        '<p><span class="vnr">Vörunúmer: </span>'
        '<span class="main-sku">50300</span></p>'
        '<div><span class="product-description"> ÞAKBRÚNALISTI FURA FRÆSTUR </span></div>'
    )
    assert _extract_product_meta(html) == {
        "product_number": "50300",
        "description_name": "ÞAKBRÚNALISTI FURA FRÆSTUR",
    }


def test_extract_product_meta_byko_uses_shortdescription_and_variant_sku():
    from custom_components.price_watch.extractor import _extract_product_meta

    import json as _json
    data = {"props": {"pageProps": {"product": {
        "name": "FURA ALHEF 45X95 AB-GAGNV",
        "shortDescription": {"is": "Alhefluð Gagnvarin Fura 45x95", "en": ""},
        "variants": [{"sku": "0058504::300:", "name": "x",
                      "price": {"gross": 2187, "currency": "ISK"}}],
    }}}}
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        f"{_json.dumps(data)}</script>"
    )
    # Without a pinned sku → first variant's sku.
    assert _extract_product_meta(html) == {
        "description_name": "Alhefluð Gagnvarin Fura 45x95",
        "product_number": "0058504::300",
    }
    # With the tracked variant's sku → that sku (trailing colon dropped).
    assert _extract_product_meta(html, variant_sku="0058504::480:") == {
        "description_name": "Alhefluð Gagnvarin Fura 45x95",
        "product_number": "0058504::480",
    }


def test_extract_product_meta_absent_returns_empty():
    from custom_components.price_watch.extractor import _extract_product_meta

    assert _extract_product_meta("<html><body>nothing</body></html>") == {}


def test_parse_store_availability_absent_returns_none():
    from custom_components.price_watch.extractor import _parse_store_availability

    assert _parse_store_availability("<html><body>nothing here</body></html>") is None


def _jysk_li(store, status_text="Til á lager", cls="available", star=True):
    star_span = (
        '<span style="font-weight: bold; margin-left: 5px; color: #d91a00;"> *</span>'
        if star
        else ""
    )
    return (
        f'<li class="{cls}" title="{store}: {status_text} ">'
        f'<img class="svg" alt="" src="/x.svg" />{store}{star_span}</li>'
    )


def test_parse_store_availability_jysk_warehouse_stars():
    """JYSK: each store available, red asterisk → from_warehouse True."""
    from custom_components.price_watch.extractor import _parse_store_availability

    stores = ["Akureyri", "Selfoss", "Skeifan", "Grandi"]
    html = (
        '<div class="rfl-single-product__availability">'
        '<ul class="availability-list">'
        + "".join(_jysk_li(s) for s in stores)
        + "</ul></div>"
    )
    res = _parse_store_availability(html)
    assert res is not None
    assert len(res) == 4
    by_store = {r["store"]: r for r in res}
    assert by_store["Akureyri"]["status"] == "in_stock"
    assert by_store["Akureyri"]["from_warehouse"] is True
    assert all(r["from_warehouse"] for r in res)


def test_parse_store_availability_jysk_no_star_is_local():
    """A store with NO red asterisk has the stock locally (from_warehouse False)."""
    from custom_components.price_watch.extractor import _parse_store_availability

    html = (
        '<ul class="availability-list">'
        + _jysk_li("Skeifan", star=False)
        + "</ul>"
    )
    res = _parse_store_availability(html)
    assert res == [
        {"store": "Skeifan", "status": "in_stock", "from_warehouse": False}
    ]


def test_parse_store_availability_jysk_sold_out():
    """An 'unavailable' / Uppselt store maps to sold_out."""
    from custom_components.price_watch.extractor import _parse_store_availability

    html = (
        '<ul class="availability-list">'
        + _jysk_li("Akureyri", status_text="Til á lager", cls="available")
        + _jysk_li("Selfoss", status_text="Uppselt", cls="unavailable", star=False)
        + "</ul>"
    )
    res = _parse_store_availability(html)
    by_store = {r["store"]: r["status"] for r in res}
    assert by_store["Akureyri"] == "in_stock"
    assert by_store["Selfoss"] == "sold_out"


def test_parse_jysk_original_price_on_sale():
    from custom_components.price_watch.extractor import _parse_jysk_original_price

    html = (
        '<div class="product-price-container">'
        '<div class="discount-container"><div class="sticker discount-sticker">'
        '<span class="sticker-text">20%</span></div></div>'
        '<p><span class="product-price__price red-text"><strong>79.990 kr.</strong></span>'
        '<br><span class="product-price__offer-price"><strike>99.990 kr.</strike></span></p>'
        '</div>'
    )
    assert _parse_jysk_original_price(html) == 99990.0


def test_parse_jysk_original_price_not_on_sale_returns_none():
    from custom_components.price_watch.extractor import _parse_jysk_original_price

    html = '<span class="product-price__price"><strong>79.990 kr.</strong></span>'
    assert _parse_jysk_original_price(html) is None


def test_parse_jysk_sizes_resolves_urls_and_selected():
    from custom_components.price_watch.extractor import _parse_jysk_sizes

    html = (
        '<div class="size-options-container"><label>Stærðir</label>'
        '<div class="size-options">'
        '<div href="/stok-vara/NORDMARKA-solhysi-3x3x2-78-m-gratt" '
        'class="size-option-item selected">300x300</div>'
        '<div href="/stok-vara/NORDMARKA-solhysi-3x4x2-78-m-gratt" '
        'class="size-option-item">300x400</div>'
        '</div></div>'
    )
    res = _parse_jysk_sizes(html, "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x3x2-78-m-gratt/?PathId=abc")
    assert res == [
        {
            "label": "300x300",
            "url": "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x3x2-78-m-gratt",
            "selected": True,
        },
        {
            "label": "300x400",
            "url": "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x4x2-78-m-gratt",
            "selected": False,
        },
    ]


def test_parse_jysk_sizes_single_size_returns_none():
    """A lone size isn't a picker."""
    from custom_components.price_watch.extractor import _parse_jysk_sizes

    html = (
        '<div class="size-options">'
        '<div href="/x" class="size-option-item selected">300x300</div></div>'
    )
    assert _parse_jysk_sizes(html, "https://jysk.is/x") is None


def test_parse_jysk_sizes_absent_returns_none():
    from custom_components.price_watch.extractor import _parse_jysk_sizes

    assert _parse_jysk_sizes("<html><body>nope</body></html>", "https://jysk.is") is None


@pytest.mark.asyncio
async def test_extract_product_jysk_jsonld_with_store_availability(monkeypatch):
    """End-to-end: a JYSK page (JSON-LD price + availability-list) yields the
    price AND per-store availability with the warehouse flag, no AI needed."""
    page = (
        "<html><head>"
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"NORDMARKA solhysi",'
        '"offers":[{"@type":"Offer","price":"79990","priceCurrency":"ISK",'
        '"availability":"in stock"}]}'
        "</script></head><body>"
        '<ul class="availability-list">'
        + _jysk_li("Akureyri") + _jysk_li("Grandi") +
        "</ul></body></html>"
    )

    async def fake_fetch_html(url, session=None, cookies=None):
        return page

    monkeypatch.setattr(extractor_mod, "fetch_html", fake_fetch_html)

    result = await extract_product(
        url="https://jysk.is/stok-vara/NORDMARKA",
        session=None,
        ai_provider=None,
    )
    assert result.method == "jsonld"
    assert result.price == 79990.0
    assert result.currency == "ISK"
    assert result.store_availability is not None
    assert len(result.store_availability) == 2
    assert all(s["from_warehouse"] for s in result.store_availability)
    assert result.in_stock is True


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


# --- byko.is size/length variant picker (Next.js __NEXT_DATA__) -------------

import json as _json  # noqa: E402


def _byko_html(variants: list[dict] | None = None, base: str = "FURA ALHEF 45X95 AB-GAGNV") -> str:
    """A minimal byko.is page: __NEXT_DATA__ with a product + size variants."""
    if variants is None:
        variants = [
            {"sku": "0058504::300:", "name": f"{base} 300",
             "price": {"net": 1764, "gross": 2187, "currency": "ISK"},
             "inStock": True, "webstoreInStock": False,
             "firstImage": {"image": {"productGallery": "https://img/300.jpg"}}},
            {"sku": "0058504::480:", "name": f"{base} 480",
             "price": {"net": 2946, "gross": 3653, "currency": "ISK"},
             "inStock": True, "webstoreInStock": True,
             "firstImage": {"image": {"productGallery": "https://img/480.jpg"}}},
            {"sku": "0058504::660:", "name": f"{base} 660",
             "price": {"net": 4051, "gross": 5023, "currency": "ISK"},
             "inStock": False, "webstoreInStock": False},
        ]
    data = {"props": {"pageProps": {"product": {
        "name": base, "sku": None, "defaultVariant": None, "variants": variants,
    }}}}
    return (
        '<html><head><title>Byko</title></head><body>'
        f'<script id="__NEXT_DATA__" type="application/json">{_json.dumps(data)}</script>'
        '</body></html>'
    )


def test_list_byko_variants_enumerates_lengths():
    data = list_byko_variants(_byko_html())
    assert data is not None
    # One option group titled "Length"; choices are bare lengths, sorted asc.
    assert len(data["options"]) == 1
    assert data["options"][0]["title"] == "Length"
    assert data["options"][0]["choices"] == ["300", "480", "660"]
    assert data["currency"] == "ISK"
    # Each combo carries its gross price + stock flag.
    by_label = {v["labels"][0]: v for v in data["variants"]}
    assert by_label["480"]["price"] == 3653
    assert by_label["480"]["in_stock"] is True
    assert by_label["660"]["in_stock"] is False


def test_list_byko_variants_sorts_numerically_not_lexically():
    """120 must precede 1500 — numeric sort, not string sort."""
    base = "BOARD"
    variants = [
        {"sku": f"x::{n}:", "name": f"{base} {n}",
         "price": {"gross": n, "currency": "ISK"}, "inStock": True}
        for n in (1500, 120, 180)
    ]
    data = list_byko_variants(_byko_html(variants=variants, base=base))
    assert data["options"][0]["choices"] == ["120", "180", "1500"]


def test_list_variants_dispatches_to_byko():
    """The generic dispatcher recognizes a byko page (no Wix data)."""
    data = list_variants(_byko_html())
    assert data is not None
    assert data["options"][0]["title"] == "Length"


def test_try_byko_variant_resolves_pinned_length():
    res = try_byko_variant(_byko_html(), ["480"])
    assert res is not None
    assert res["price"] == 3653
    assert res["title"] == "FURA ALHEF 45X95 AB-GAGNV 480"
    assert res["in_stock"] is True
    assert res["retailer"] == "BYKO"
    assert res["method"] == "byko_variant"
    assert res["image_url"] == "https://img/480.jpg"


def test_try_byko_variant_matches_via_sku_segment():
    """An out-of-stock length still resolves (price tracked even when 0 stock)."""
    res = try_byko_variant(_byko_html(), ["660"])
    assert res is not None
    assert res["price"] == 5023
    assert res["in_stock"] is False


def test_try_byko_variant_no_match_returns_none():
    assert try_byko_variant(_byko_html(), ["999"]) is None


def test_try_byko_variant_empty_options_returns_none():
    assert try_byko_variant(_byko_html(), []) is None


def test_byko_variant_helpers_ignore_non_byko_html():
    assert list_byko_variants(SAMPLE_NO_JSONLD) is None
    assert try_byko_variant(SAMPLE_NO_JSONLD, ["480"]) is None


@pytest.mark.asyncio
async def test_extract_product_byko_variant_drives_title_and_price(monkeypatch):
    """End-to-end: variant_options on a byko page (no JSON-LD, no AI) yields the
    pinned length's price AND its full name as the title."""

    async def fake_fetch_html(url, session=None, cookies=None):
        return _byko_html()

    monkeypatch.setattr(extractor_mod, "fetch_html", fake_fetch_html)

    result = await extract_product(
        url="https://byko.is/vara/fura-alhef-45-x95-ab-gagnv-248063",
        session=None,
        ai_provider=None,
        variant_options=["480"],
    )
    assert result.method == "byko_variant"
    assert result.price == 3653
    assert result.title == "FURA ALHEF 45X95 AB-GAGNV 480"
    assert result.currency == "ISK"
    assert result.retailer == "BYKO"
