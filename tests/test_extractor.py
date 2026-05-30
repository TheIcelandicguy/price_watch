"""Tests for the extractor module."""

from __future__ import annotations

import json

import pytest

from custom_components.price_watch.extractor import (
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
