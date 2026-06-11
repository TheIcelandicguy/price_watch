"""Rafland preset — headless Magento (Roanuz backend) via GraphQL.

rafland.is is a Next.js storefront over a headless Magento; the price is fetched
client-side from the Magento GraphQL backend, so the page itself carries no
Schema.org price and the free path finds nothing. This preset queries that
backend directly, filtering by the product's `url_key` (the URL slug).

NOTE: the backend host + store code are rafland's current Roanuz deployment —
if Rafland re-platforms, update `_ENDPOINT` / `_STORE`.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

NAME = "Rafland"
DOMAINS = ("rafland.is",)

_ENDPOINT = "https://backend-v2-ht.roanuz.com/graphql"
_STORE = "rafland_store_view"
_QUERY = (
    "query($f:ProductAttributeFilterInput){products(filter:$f){items{"
    "name sku stock_status "
    "price_range{minimum_price{final_price{value currency}}}}}}"
)

# Product pages are a single path segment ending in .html: rafland.is/<slug>.html
_PRODUCT_RE = re.compile(r"^[^/]+\.html$", re.IGNORECASE)


def _url_key(url: str) -> str | None:
    """The Magento url_key = the URL's single path segment minus `.html`."""
    path = urlparse(url).path.strip("/")
    if not path or "/" in path or not _PRODUCT_RE.match(path):
        return None
    return path[:-5]  # strip ".html"


def matches(url: str) -> bool:
    """Return True for a rafland.is product URL."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host == "rafland.is" and _url_key(url) is not None


def build_parser(url: str) -> dict[str, Any] | None:
    """Build a raw_json custom_parser that hits rafland's GraphQL backend."""
    key = _url_key(url)
    if key is None:
        return None
    body = json.dumps({"query": _QUERY, "variables": {"f": {"url_key": {"eq": key}}}})
    return {
        "type": "raw_json",
        "url": _ENDPOINT,
        "request_method": "POST",
        "request_body": body,
        "request_headers": {"Content-Type": "application/json", "Store": _STORE},
        "selectors": {
            "title": "data.products.items.0.name",
            "price": "data.products.items.0.price_range.minimum_price.final_price.value",
            "currency": "data.products.items.0.price_range.minimum_price.final_price.currency",
            "sku": "data.products.items.0.sku",
            "in_stock": "data.products.items.0.stock_status",
        },
        "transforms": {
            "title": 'replace:&quot;:"|strip',
            "price": "float",
            "in_stock": "contains:IN_STOCK",
        },
        "default_currency": "ISK",
        "default_retailer": "Rafland",
        "min_price": 100,
    }
