"""ELKO preset — price lives in embedded JSON, not JSON-LD.

elko.is (a major Icelandic electronics retailer) renders product pages
client-side; the page has no Schema.org Product, so the free JSON-LD path
finds no price. The current price is, however, present in the embedded page
state as `"price": <number>`. A regex parser reads it directly — no AI needed.
"""

from __future__ import annotations

import re
from typing import Any

NAME = "ELKO"
DOMAINS = ("elko.is",)

# Product URLs look like elko.is/vorur/<slug>-<id>/<model-code>
URL_PATTERN = re.compile(r"elko\.is/vorur/", re.IGNORECASE)


def matches(url: str) -> bool:
    """Return True if this preset can handle the URL."""
    return bool(URL_PATTERN.search(url))


def build_parser(url: str) -> dict[str, Any] | None:
    """Build a regex custom_parser for an ELKO product URL."""
    if not matches(url):
        return None
    return {
        "type": "regex",
        "selectors": {
            "price": r'"price"\s*:\s*"?([0-9]+(?:[.,][0-9]+)?)"?',
            "title": [
                r'<meta[^>]*property="og:title"[^>]*content="([^"|]+)',
                r"<title[^>]*>([^<|]+)",
            ],
            "image_url": r'<meta[^>]*property="og:image"[^>]*content="([^"]+)',
        },
        "transforms": {"price": "price_clean"},
        "default_currency": "ISK",
        "default_retailer": "ELKO",
        # Reject an accidental tiny match (e.g. a shipping or unit field).
        "min_price": 100,
    }
