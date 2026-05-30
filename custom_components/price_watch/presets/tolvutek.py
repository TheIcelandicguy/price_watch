"""Tölvutek preset — POSTs to FetchProduct API.

Tölvutek runs on Konakart (an Origo-bundled e-commerce platform).
The product page is a JS-rendered SPA that hits `/api//FetchProduct`
(yes, double slash — that's their actual endpoint) with prodId.
"""

from __future__ import annotations

import re
from typing import Any

NAME = "Tölvutek"
DOMAINS = ("tolvutek.is",)

# Product URLs end in `/2_<prodId>.action` (the leading 2 is a category id)
URL_PATTERN = re.compile(r"tolvutek\.is/.+?/2_(\d+)\.action", re.IGNORECASE)


def matches(url: str) -> bool:
    """Return True if this preset can handle the URL."""
    return bool(URL_PATTERN.search(url))


def build_parser(url: str) -> dict[str, Any] | None:
    """Build a custom_parser config from a Tölvutek product URL.

    Returns None if the URL doesn't match the expected shape.
    """
    match = URL_PATTERN.search(url)
    if not match:
        return None
    prod_id = match.group(1)
    return {
        "type": "raw_json",
        "url": "https://tolvutek.is/api//FetchProduct",
        "request_method": "POST",
        "request_body": (
            f'{{"prodId": {prod_id}, "displayPricesWithTax": true, '
            f'"includeCardLoan": false}}'
        ),
        "request_headers": {"Content-Type": "application/json"},
        "selectors": {
            "title": "r.name",
            "price": "r.specialPriceIncTax",
            "_price_fallback": "r.priceIncTax",
            "stock_count": "r.quantity",
            "image_url": "r.image",
            "sku": "r.sku",
            "retailer": "r.manufacturerName",
        },
        "transforms": {
            "price": "coalesce:_price_fallback|float",
            "stock_count": "int",
            "image_url": "prefix:https://tolvutek.is",
        },
        "default_currency": "ISK",
        "default_retailer": "Tölvutek",
    }
