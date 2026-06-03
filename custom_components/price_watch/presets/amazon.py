"""Amazon preset — URL normalization + multi-strategy product parser.

Amazon stopped shipping Schema.org Product JSON-LD on most regional
domains. We use a layered approach:

1. CSS selectors against the visible DOM (most reliable for "Buy Now" pages)
2. Regex against embedded JSON state (catches "buying options" pages where
   the visible DOM hides the price behind a button)

Caveats:
- Amazon aggressively bot-blocks. curl_cffi (Chrome TLS impersonation)
  helps but you may need to paste cookies (see docs/custom_parsers.md).
- Selectors and JSON keys aren't bulletproof - Amazon A/B-tests page
  layouts. AI fallback (Anthropic API key) catches the cases where
  neither selector nor regex finds the price.
- Stock count is NOT exposed reliably; we only get the boolean.
- Regional pricing differs by domain - same ASIN on amazon.com and
  amazon.de will return different prices/currency.
"""

from __future__ import annotations

import re
from typing import Any

NAME = "Amazon"
DOMAINS = (
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.es",
    "amazon.it",
    "amazon.nl",
    "amazon.se",
    "amazon.pl",
    "amazon.co.jp",
    "amazon.ca",
    "amazon.com.au",
    "amazon.com.mx",
    "amazon.com.br",
    "amazon.in",
    "amazon.ae",
)

URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(amazon\.[a-z.]+)/(?:[^/]+/)?(?:dp|gp/product)/([A-Z0-9]{10})",
    re.IGNORECASE,
)

CURRENCY_BY_DOMAIN = {
    "amazon.com": "USD",
    "amazon.co.uk": "GBP",
    "amazon.de": "EUR",
    "amazon.fr": "EUR",
    "amazon.es": "EUR",
    "amazon.it": "EUR",
    "amazon.nl": "EUR",
    "amazon.se": "SEK",
    "amazon.pl": "PLN",
    "amazon.co.jp": "JPY",
    "amazon.ca": "CAD",
    "amazon.com.au": "AUD",
    "amazon.com.mx": "MXN",
    "amazon.com.br": "BRL",
    "amazon.in": "INR",
    "amazon.ae": "AED",
}


def matches(url: str) -> bool:
    return bool(URL_PATTERN.search(url))


def normalize_url(url: str) -> str | None:
    """Return the canonical `/dp/<ASIN>` form of an Amazon product URL."""
    match = URL_PATTERN.search(url)
    if not match:
        return None
    domain, asin = match.group(1).lower(), match.group(2).upper()
    return f"https://www.{domain}/dp/{asin}"


def _domain_from_url(url: str) -> str:
    match = URL_PATTERN.search(url)
    if not match:
        return "amazon.com"
    return match.group(1).lower()


def build_parser(url: str) -> dict[str, Any] | None:
    """Build a regex-based custom parser for Amazon product pages.

    Why regex instead of CSS: Amazon's "buying options" pages hide the
    visible price behind a button click, but the price is always present
    in the HTML inside JSON state blobs and data-* attributes. Regex
    finds it regardless of which page variant Amazon serves.

    The patterns try (in priority order):
    1. ASIN data block: `"priceAmount":82.99,` (numeric, deal/visible price)
    2. Display price: `"displayPrice":"£82.99"` (formatted string)
    3. desktop_buybox: `"priceToPay":{"value":{"amount":82.99}}`
    4. .a-offscreen text in HTML (visible price for simpler pages)

    Each is wrapped in `(?:...)` non-capturing groups, with a SINGLE
    `([0-9.,]+)` capture group that picks up the numeric value. The
    regex engine returns the first match, which is the most authoritative.
    """
    domain = _domain_from_url(url)
    currency = CURRENCY_BY_DOMAIN.get(domain, "")

    return {
        "type": "regex",
        "selectors": {
            # Title - try the page <title> first (always present, includes
            # full product name), fall back to #productTitle text.
            "title": (
                r'<span\s+id="productTitle"[^>]*>\s*([^<]+?)\s*</span>'
                r'|<title[^>]*>([^<:|]+?)(?:\s*[:|]\s*Amazon|\s*</title>)'
            ),
            # Price - strategies tried in PRIORITY order (a list = first
            # match wins, not leftmost-in-HTML). Ranked most-reliable first
            # so a formatted "$49.99" string beats a raw numeric field that
            # might be in cents or belong to a different on-page widget.
            "price": [
                # Currency-anchored FORMATTED strings first — they're
                # unambiguous (symbol + proper decimal), unlike Amazon's raw
                # JSON numbers, which the site inconsistently stores in
                # dollars OR cents (4999 = $49.99) with no way to tell from
                # the value alone. These are tied to the actual offer.
                r'"displayPrice"\s*:\s*"[^"0-9]*([0-9][0-9.,]*)"',
                # "1 option from $49.99" marketplace offer message. Anchored
                # on a currency symbol so we get the PRICE, not the count.
                r'"olpMessage"\s*:\s*"[^"]*?[$£€]\s*([0-9][0-9.,]*)',
                # Raw JSON numeric fields — ONLY with a decimal point, so a
                # bare integer (cents) can't 100x the price. A genuine
                # whole-dollar price is caught by a formatted string above
                # or the a-offscreen text below.
                r'"priceToPay"\s*:\s*\{[^}]*"amount"\s*:\s*([0-9]+\.[0-9]{1,2})\b',
                r'"priceAmount"\s*:\s*([0-9]+\.[0-9]{1,2})\b',
                r'"buyingPrice"\s*:\s*([0-9]+\.[0-9]{1,2})\b',
                # Visible .a-offscreen text — LAST: it's generic (every price
                # on the page uses it, including recommendations), so it's the
                # least trustworthy and only used when nothing else matched.
                r'<span\s+class="a-offscreen">[^0-9]*([0-9][0-9.,]*)</span>',
            ],
            # Image - reliable across all layouts
            "image_url": (
                r'<img\s+[^>]*id="landingImage"[^>]*src="([^"]+)"'
                r'|"hiRes"\s*:\s*"([^"]+\.jpg)"'
            ),
        },
        "transforms": {
            "price": "price_clean",
        },
        "default_currency": currency,
        "default_retailer": "Amazon",
    }
