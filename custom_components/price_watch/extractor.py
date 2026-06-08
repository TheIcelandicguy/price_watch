"""Price extraction logic for Price Watch.

Strategy:
1. Custom parser (if configured) — fetch + parse. On parser failure,
   AI fallback runs if an ai_provider is set.
2. Otherwise fetch the user-facing URL and try JSON-LD.
3. Otherwise (no JSON-LD), fall back to AI extraction via ai_provider.

The AI backend is pluggable — see the `ai/` subpackage. The extractor
itself knows nothing about Claude, OpenAI, Gemini, etc. — it only
talks to the AIProvider interface.

Network layer:
- curl_cffi with Chrome TLS impersonation (defeats Cloudflare TLS
  fingerprinting on Komplett, NetOnNet, etc.)
- aiohttp fallback if curl_cffi unavailable
- A persistent session cache keyed by integration ID so cookies
  accumulate across fetches. Sites like Amazon serve different
  content to "returning" sessions vs cookie-less ones.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup, Comment

from .ai import AIProvider, AIProviderError
from .const import (
    HTTP_TIMEOUT,
    USER_AGENT,
)
# Cookie normalization is shared with the services / config flow / websocket;
# re-exported under the historical name used throughout the extractor.
from .cookies import to_dict as _normalize_cookies

_LOGGER = logging.getLogger(__name__)

# Import curl_cffi at module load time. The first import does file I/O
# (importlib.metadata reads the dist-info), which blocks the event loop if
# done lazily inside an async function. HA flags that as a bug.
try:
    from curl_cffi import requests as _cffi_requests  # noqa: E402
    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _cffi_requests = None  # type: ignore[assignment]
    _CURL_CFFI_AVAILABLE = False


# A persistent curl_cffi AsyncSession lives at module scope so cookies
# accumulate across calls. Sites like Amazon track "returning visitor"
# state via cookies and serve different content (real product page vs
# "Continue shopping" interstitial) based on it.
_persistent_session: Any = None
_persistent_session_lock = asyncio.Lock()


async def _get_persistent_session() -> Any:
    """Return the shared curl_cffi AsyncSession, lazily created.

    The session keeps a cookie jar that builds up over time. First fetch
    to a new domain may hit a bot-check page; the response cookies make
    subsequent fetches look like a returning visitor.

    Returns None if curl_cffi isn't installed.
    """
    global _persistent_session
    if not _CURL_CFFI_AVAILABLE:
        return None
    if _persistent_session is None:
        async with _persistent_session_lock:
            if _persistent_session is None:
                _persistent_session = _cffi_requests.AsyncSession(impersonate="chrome")
    return _persistent_session


# --- Fetch throttle -------------------------------------------------------
# Protects the tracked retailers (and us) from a request burst when many
# products refresh at once — the worst case being an HA restart, where every
# coordinator's first poll fires together. Two limits, both module-global so
# they span ALL coordinators:
#   1. a cap on TOTAL concurrent fetches, and
#   2. a politeness gap between requests to the SAME host, so e.g. 20 Byko
#      products don't hammer byko.is back-to-back (which reads as a scrape and
#      invites CAPTCHA / rate-limiting).
# Different hosts still fetch in parallel (each has its own lock); only
# same-host requests serialize and space out.
_MAX_CONCURRENT_FETCHES = 5
_HOST_MIN_INTERVAL = 3.0  # seconds between same-host requests
_fetch_semaphore: asyncio.Semaphore | None = None
_host_locks: dict[str, asyncio.Lock] = {}
_host_last_fetch: dict[str, float] = {}


def _fetch_sem() -> asyncio.Semaphore:
    """Lazily build the global fetch semaphore on the running loop."""
    global _fetch_semaphore
    if _fetch_semaphore is None:
        _fetch_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
    return _fetch_semaphore


def _host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except (ValueError, TypeError):
        return ""


@asynccontextmanager
async def _fetch_slot(url: str, politeness: bool = True):
    """Acquire a fetch slot: global concurrency cap + (optional) per-host gap.

    With ``politeness`` (the default, for page fetches) same-host requests
    serialize and are spaced ``_HOST_MIN_INTERVAL`` apart; the politeness wait
    happens BEFORE taking a concurrency slot so a sleeping request doesn't
    occupy one. Images pass ``politeness=False`` — they hit CDNs, not the
    bot-guarded product pages, so they only need the global cap.
    """
    if not politeness:
        async with _fetch_sem():
            yield
        return
    host = _host_of(url)
    host_lock = _host_locks.setdefault(host, asyncio.Lock())
    async with host_lock:
        wait = _HOST_MIN_INTERVAL - (time.monotonic() - _host_last_fetch.get(host, 0.0))
        if wait > 0:
            await asyncio.sleep(wait)
        async with _fetch_sem():
            try:
                yield
            finally:
                _host_last_fetch[host] = time.monotonic()


async def shutdown_persistent_session() -> None:
    """Close the persistent session. Called from integration unload."""
    global _persistent_session
    if _persistent_session is not None:
        try:
            await _persistent_session.close()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error closing persistent curl_cffi session", exc_info=True)
        _persistent_session = None


# Tags to strip during preprocessing
STRIP_TAGS = ("script", "style", "svg", "noscript", "iframe", "video", "audio", "canvas")
STRIP_ATTRS = ("style", "onclick", "onload", "onerror", "data-track", "srcset", "sizes")

# Browser-realistic headers - many e-commerce sites reject thin requests
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,is;q=0.8,no;q=0.7,sv;q=0.6",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class ExtractionResult:
    """Result of a single price extraction."""

    title: str
    price: float
    currency: str
    in_stock: bool = True
    stock_count: int | None = None
    image_url: str | None = None
    sku: str | None = None
    retailer: str | None = None
    content_hash: str = ""
    cost_usd: float = 0.0
    method: str = "unknown"
    # Pre-discount ("was") price when the item is on sale. None when not on
    # sale / unknown. `price` always holds what the shopper pays NOW; this is
    # the struck-through original. on_sale is derived (original_price > price).
    original_price: float | None = None
    # Per-physical-store stock, when the retailer exposes it (e.g. Húsa lists
    # each store as Til á lager / Fá eintök / Uppselt). List of
    # {"store": name, "status": "in_stock"|"limited"|"sold_out"}. None when
    # the page has no such breakdown.
    store_availability: list[dict[str, Any]] | None = None
    # Sibling size/variant pages, when the retailer lists them as separate
    # product URLs (e.g. JYSK's "Stærðir" 300x300 / 300x400). List of
    # {"label", "url", "selected"}. None when the page has no size picker.
    size_options: list[dict[str, Any]] | None = None
    # Retailer's product number / SKU as shown to shoppers (Húsa "Vörunúmer",
    # Byko "VNR"). None when the page doesn't expose one.
    product_number: str | None = None
    # A fuller human-readable name beyond the short title — Húsa's
    # ".product-description" line, Byko's shortDescription (which expands the
    # coded variant name, e.g. "Alhefluð Gagnvarin Fura 45x95"). None when
    # absent.
    description_name: str | None = None
    # Normalized price-per-unit (e.g. Byko lumber kr/m = gross ÷ length) +
    # its label ("kr/m"). Lets the card show an apples-to-apples figure across
    # sizes. None when no unit is known.
    unit_price: float | None = None
    unit_label: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    # Set True when the AI determines the product has been permanently
    # removed from the retailer's catalog. When True:
    #  - the coordinator stops polling for this entry
    #  - the sensor surfaces a "discontinued" state instead of a price
    #  - price/in_stock reflect the LAST known good values from before
    #    the page went away; the coordinator copies them forward
    discontinued: bool = False
    discontinued_reason: str | None = None


class ExtractionError(Exception):
    """Raised when extraction fails."""


def preprocess_html(html: str) -> tuple[str, str]:
    """Clean HTML and return (cleaned_html, content_hash)."""
    soup = BeautifulSoup(html, "html.parser")

    jsonld_payloads: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        if script.string:
            jsonld_payloads.append(script.string.strip())

    for tag in soup(STRIP_TAGS):
        tag.decompose()

    if soup.body is not None and jsonld_payloads:
        for payload in jsonld_payloads:
            new_script = soup.new_tag("script", type="application/ld+json")
            new_script.string = payload
            soup.body.insert(0, new_script)

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    to_decompose = []
    for tag in soup.find_all(True):
        attrs = getattr(tag, "attrs", None)
        if attrs is None:
            continue
        for attr in STRIP_ATTRS:
            if attr in attrs:
                del attrs[attr]
        if attrs.get("hidden") is not None or attrs.get("aria-hidden") == "true":
            to_decompose.append(tag)
    for tag in to_decompose:
        tag.decompose()

    cleaned = str(soup)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    text_parts: list[str] = []
    for element in soup.find_all(string=True):
        text = str(element).strip()
        if text:
            text_parts.append(text)
    text_parts.extend(jsonld_payloads)
    text_blob = " ".join(text_parts)
    text_blob = re.sub(r"\b\d{10,}\b", "", text_blob)
    text_blob = re.sub(r"\s+", " ", text_blob).strip()
    content_hash = hashlib.sha256(text_blob.encode("utf-8", errors="ignore")).hexdigest()

    return cleaned, content_hash


_STOCK_KEYWORDS = (
    r"(?:p[åa]\s*lager|in\s*stock|on\s*hand|"
    r"available|tilg[æa]ngelig|"
    r"disponibles?|disponibili|disponivel|"
    r"verf[üu]gbar|"
    r"i\s*lager|"
    r"[áa]\s*lager|"
    r"stk\.?|szt\.?|pcs\.?|units?|stuks?)"
)
_STOCK_NUM_BEFORE = re.compile(rf"\b(\d{{1,5}})\s*{_STOCK_KEYWORDS}", re.IGNORECASE)
_STOCK_NUM_AFTER = re.compile(rf"{_STOCK_KEYWORDS}[:\s]*(\d{{1,5}})\b", re.IGNORECASE)


def guess_stock_count(html_or_text: str) -> int | None:
    """Heuristic: find a stock count near a stock keyword."""
    candidates: list[int] = []
    for pattern in (_STOCK_NUM_BEFORE, _STOCK_NUM_AFTER):
        for match in pattern.finditer(html_or_text):
            try:
                n = int(match.group(1))
            except (ValueError, IndexError):
                continue
            if 0 <= n <= 999:
                candidates.append(n)
    if not candidates:
        return None
    return min(candidates)


def find_meta_image(html: str) -> str | None:
    """Find page hero image via og:image / twitter:image / image_src meta."""
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return og["content"]
    og_url = soup.find("meta", attrs={"property": "og:image:secure_url"})
    if og_url and og_url.get("content"):
        return og_url["content"]
    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        return twitter["content"]
    link = soup.find("link", attrs={"rel": "image_src"})
    if link and link.get("href"):
        return link["href"]
    return None


def _parse_store_availability(html: str) -> list[dict[str, Any]] | None:
    """Parse per-physical-store stock from a retailer's availability block.

    Supports two Icelandic layouts (dispatched by a cheap string fast-path
    so bs4 stays off the hot path for every other site):

    - **Húsasmiðjan** — a ``product-availability-section`` with one row per
      stock status (Til á lager / Fá eintök / Uppselt), each row listing the
      stores in that state.
    - **JYSK / Rúmfatalagerinn** — an ``availability-list`` <ul> with one
      <li> per store, the store's status in the <li> ``title`` + class, and a
      red asterisk (``<span style="…#d91a00">*</span>``) marking stock that
      actually sits at the central Reykjavík warehouse rather than in that
      store (so a non-capital store would have to order it in).

    Returns a flat list of ``{"store", "status"}`` dicts — JYSK rows also
    carry ``"from_warehouse": bool`` — or None when the page has neither
    block. ``status`` is one of ``in_stock`` / ``limited`` / ``sold_out``.
    """
    has_husa = "product-availability-section" in html
    has_jysk = "availability-list" in html
    if not has_husa and not has_jysk:
        return None
    soup = BeautifulSoup(html, "html.parser")
    if has_husa:
        out = _parse_husa_availability(soup)
        if out:
            return out
    if has_jysk:
        out = _parse_jysk_availability(soup)
        if out:
            return out
    return None


def _parse_husa_availability(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Húsasmiðjan: one ``row`` per status, each listing its stores."""
    section = soup.find(class_="product-availability-section")
    if section is None:
        return []
    out: list[dict[str, Any]] = []
    for row in section.find_all(class_="row"):
        label = row.find(class_="availability-label")
        col = row.find(class_=lambda c: bool(c) and "col-md-9" in c)
        if label is None or col is None:
            continue
        text = label.get_text(" ", strip=True).lower()
        if "uppselt" in text:
            status = "sold_out"
        elif "eint" in text:  # "fá eintök" — a few left
            status = "limited"
        elif "lager" in text:  # "til á lager" — in stock
            status = "in_stock"
        else:
            continue
        seen: set[str] = set()
        for element in col.find_all(["a", "strong"]):
            name = element.get_text(strip=True).rstrip(",").strip()
            if name and name not in seen:
                seen.add(name)
                out.append({"store": name, "status": status})
    return out


def _parse_jysk_availability(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """JYSK: one ``<li>`` per store; red ``*`` = central-warehouse stock.

    The store name + Icelandic status text live in the ``<li title>``
    ("Akureyri: Til á lager"); the ``<li>`` class echoes it (``available`` /
    ``unavailable``). A bold red asterisk span flags stock that's at the
    Reykjavík warehouse rather than physically in that store.
    """
    ul = soup.find(class_="availability-list")
    if ul is None:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for li in ul.find_all("li"):
        classes = " ".join(li.get("class") or []).lower()
        title = (li.get("title") or "").strip()
        if ":" in title:
            name, status_text = (p.strip() for p in title.split(":", 1))
        else:
            # No title — fall back to the visible text minus the asterisk.
            name, status_text = li.get_text(strip=True).rstrip("* ").strip(), ""
        status_text = status_text.lower()
        # "unavailable" contains "available", so test the negative first.
        if "uppselt" in status_text or "unavailable" in classes:
            status = "sold_out"
        elif "eint" in status_text:  # "fá eintök" — a few left
            status = "limited"
        elif "lager" in status_text or "available" in classes:
            status = "in_stock"
        else:
            continue
        # Bold red asterisk = item lives at the Reykjavík warehouse.
        from_warehouse = any(
            "*" in span.get_text()
            and "d91a00" in (span.get("style") or "").lower().replace(" ", "")
            for span in li.find_all("span")
        )
        if name and name not in seen:
            seen.add(name)
            out.append(
                {"store": name, "status": status, "from_warehouse": from_warehouse}
            )
    return out


def _parse_jysk_original_price(html: str) -> float | None:
    """JYSK 'was' price — the strike-through offer price shown when on sale.

    On a discounted JYSK product the price box renders the current price in
    red and the pre-sale price struck through in
    ``product-price__offer-price`` ("99.990 kr."), alongside a percentage
    sticker. The page's JSON-LD only carries the current price, so we read
    the strike-through value here to drive the card's sale badge. Returns the
    original price (ISK, dot = thousands separator) or None when not on sale.
    """
    if "product-price__offer-price" not in html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find(class_="product-price__offer-price")
    if el is None:
        return None
    digits = re.sub(r"[^\d]", "", el.get_text(strip=True))
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _parse_jysk_sizes(html: str, base_url: str | None) -> list[dict[str, Any]] | None:
    """JYSK 'Stærðir' size options — each a SEPARATE product page.

    JYSK renders sibling sizes (300x300, 300x400, …) as
    ``size-option-item`` elements, each linking to that size's own product
    URL, with the current size carrying a ``selected`` class. Unlike an
    on-page variant (Byko/Wix), switching size means tracking a different
    page — so we surface ``{label, url, selected}`` and the panel swaps the
    tracked listing's URL.

    Relative hrefs are resolved against ``base_url``. Returns None when the
    page has no size picker or only a single size (nothing to switch to).
    """
    if "size-option-item" not in html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(class_="size-options")
    if container is None:
        return None
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in container.find_all(class_="size-option-item"):
        label = item.get_text(strip=True)
        href = (item.get("href") or "").strip()
        if not label or not href or label in seen:
            continue
        seen.add(label)
        url = urljoin(base_url, href) if base_url else href
        classes = " ".join(item.get("class") or [])
        out.append(
            {"label": label, "url": url, "selected": "selected" in classes.split()}
        )
    # A lone size isn't a picker — nothing to switch to.
    return out if len(out) > 1 else None


def is_on_sale(result: "ExtractionResult | None") -> bool:
    """Whether an extraction shows the retailer's own sale flag.

    True when a struck-through original price is present and strictly above
    the current price. The coordinator edge-triggers EVENT_DISCOUNT on a
    False→True transition of this.
    """
    return bool(
        result
        and result.original_price
        and result.original_price > result.price
    )


def _extract_product_meta(
    html: str, variant_sku: str | None = None
) -> dict[str, str]:
    """Retailer product number + a fuller description name, when exposed.

    Two layouts so far (cheap string fast-path gates bs4/JSON off the hot
    path for every other site):

    - **Húsasmiðjan** — ``<span class="main-sku">50300</span>`` (Vörunúmer)
      and ``<span class="product-description">…</span>`` (the descriptive
      name, distinct from the short page title).
    - **Byko** — the variant ``sku`` ("0058504::480") as the product number
      and ``__NEXT_DATA__`` ``product.shortDescription.is`` as the readable
      name (it expands the coded variant name). ``variant_sku`` lets the
      caller pass the specific tracked variant's sku; otherwise the first
      variant's is used.

    Returns a dict with optional ``product_number`` / ``description_name``
    keys (only those actually found).
    """
    out: dict[str, str] = {}

    if "main-sku" in html or 'class="product-description"' in html:
        soup = BeautifulSoup(html, "html.parser")
        sku = soup.find(class_="main-sku")
        if sku and sku.get_text(strip=True):
            out["product_number"] = sku.get_text(strip=True)
        desc = soup.find(class_="product-description")
        if desc and desc.get_text(strip=True):
            out["description_name"] = desc.get_text(strip=True)
        if out:
            return out

    if "__NEXT_DATA__" in html:
        prod = _byko_product(html)
        if prod is not None:
            short = prod.get("shortDescription")
            name = ""
            if isinstance(short, dict):
                name = str(short.get("is") or short.get("en") or "").strip()
            elif isinstance(short, str):
                name = short.strip()
            if name:
                out["description_name"] = name
            sku = variant_sku
            if not sku:
                variants = prod.get("variants") or []
                if variants and isinstance(variants[0], dict):
                    sku = variants[0].get("sku")
            if sku:
                # "0058504::480:" → "0058504::480" (drop the trailing colon)
                out["product_number"] = str(sku).rstrip(":")

    return out


def _ci_get(d: dict[str, Any], key: str) -> Any:
    """Case-insensitive dict lookup for JSON-LD properties.

    Schema.org property names are conventionally lowerCamelCase
    (``offers``, ``availability``, ``priceCurrency``), but some CMS
    platforms emit capitalized variants. Wix, for example, renders
    ``"Offers"`` and ``"Availability"`` — which made the lowercase-only
    lookup miss an otherwise-valid Product/Offer and report "No JSON-LD
    found", forcing an AI fallback that Free mode doesn't have.

    Prefer an exact match, then fall back to a case-insensitive scan so
    those non-standard pages parse without any AI provider.
    """
    if key in d:
        return d[key]
    lk = key.lower()
    for k, v in d.items():
        if isinstance(k, str) and k.lower() == lk:
            return v
    return None


def _offer_price(offers: dict[str, Any]) -> float | None:
    """Pull a usable price from an Offer or AggregateOffer node.

    A standard Schema.org ``Offer`` carries ``price``. An ``AggregateOffer``
    (used by sites that advertise a price range across configurations or
    sellers — e.g. logitech.com) has no ``price`` at all, only ``lowPrice``
    and ``highPrice``. The low price is what a shopper can actually pay, so
    we track that; ``highPrice`` is a last resort. Tolerates comma decimals
    and string/number values. Returns a positive float, or None when no
    usable price is present (caller then skips the candidate).
    """
    for key in ("price", "lowPrice", "highPrice"):
        raw = _ci_get(offers, key)
        if raw in (None, ""):
            continue
        # Strip a currency symbol/letters/whitespace some sites prefix or
        # suffix onto the price ("€475", "475 kr."), keeping only the numeric
        # part, before the comma→dot normalization.
        cleaned = re.sub(r"[^0-9.,\-]", "", str(raw))
        try:
            val = float(cleaned.replace(",", "."))
        except (ValueError, TypeError):
            continue
        if val > 0:
            return val
    return None


def try_jsonld(html: str, url: str | None = None) -> dict[str, Any] | None:
    """Try to extract from Schema.org Product JSON-LD.

    Handles three nesting patterns:
      1. Top-level Product (the common case for single-product pages).
      2. @graph array containing a Product node (many CMS-driven sites).
      3. ProductGroup wrapping multiple Product entries in hasVariant[]
         (Shopify multi-variant stores: Shelly, many fashion brands,
         etc.). Each hasVariant entry is itself a Product with its own
         offers.

    When `url` is provided and contains ?variant=<id>, the variant whose
    @id matches that ID is preferred. This matters when ProductGroup
    bundles multiple related-but-different products (not just sizes of
    one item) — picking the matching variant tracks the right product.
    Falls back to the first valid Product candidate when no URL match
    is possible.
    """
    # Extract variant ID from URL (Shopify pattern: ?variant=NNNNN)
    target_variant: str | None = None
    if url:
        variant_match = re.search(r"[?&]variant=(\d+)", url)
        if variant_match:
            target_variant = variant_match.group(1)

    soup = BeautifulSoup(html, "html.parser")

    # Collect all Product candidates across all JSON-LD blocks, then
    # apply variant matching once at the end. Two passes lets us pick
    # the right variant even when it's not the first one encountered.
    all_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates: list[Any] = []
        if isinstance(data, list):
            candidates.extend(data)
        elif isinstance(data, dict):
            if "@graph" in data:
                candidates.extend(data["@graph"])
            else:
                candidates.append(data)

        # Expand ProductGroup → its hasVariant[] entries. Schema.org's
        # ProductGroup is a wrapper for related products that share a
        # productGroupID; each variant is a separate Product with its
        # own offers. Without this expansion the parser skips
        # ProductGroup as "not a Product" and misses the actual product
        # data underneath.
        expanded: list[Any] = []
        for item in candidates:
            if not isinstance(item, dict):
                expanded.append(item)
                continue
            type_ = item.get("@type")
            is_product_group = (
                type_ == "ProductGroup"
                or (isinstance(type_, list) and "ProductGroup" in type_)
            )
            if is_product_group:
                variants = item.get("hasVariant")
                has_variants = isinstance(variants, list)
                # A ProductGroup may carry its OWN canonical offer at the top
                # level (JYSK: the clean price plus the group's name/image),
                # while the per-variant Products omit `name` and may prefix
                # the price with a currency symbol. Keep the wrapper FIRST so
                # it's the preferred candidate, then the variants as fallbacks.
                if _ci_get(item, "offers"):
                    expanded.append(item)
                if has_variants:
                    for v in variants:
                        if isinstance(v, dict):
                            expanded.append(v)
                if _ci_get(item, "offers") or has_variants:
                    continue  # already appended above; don't double-add
            expanded.append(item)

        for item in expanded:
            if not isinstance(item, dict):
                continue
            type_ = item.get("@type")
            types = type_ if isinstance(type_, list) else [type_]
            # Accept a real Product or a ProductGroup that carries its own
            # offer (the latter only reaches here when it had offers above).
            if "Product" not in types and "ProductGroup" not in types:
                continue

            offers = _ci_get(item, "offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if not isinstance(offers, dict):
                continue

            price = _offer_price(offers)
            if not price:
                continue

            all_candidates.append((item, offers))

    if not all_candidates:
        return None

    # Variant-from-URL matching. Many ProductGroup pages bundle several
    # related products, not just sizes/colors of one. Picking the
    # variant whose @id matches the URL's ?variant=<id> ensures we
    # track the right product. "variant-<id>" is the conventional
    # @id fragment on Shopify; we also accept the bare ID anywhere in
    # @id for forward-compat with other CMS conventions.
    chosen: tuple[dict[str, Any], dict[str, Any]] | None = None
    if target_variant:
        for item, offers in all_candidates:
            item_id = str(item.get("@id") or "")
            if f"variant-{target_variant}" in item_id or (
                target_variant and target_variant in item_id
            ):
                chosen = (item, offers)
                break

    # Fall back to first valid Product (matches pre-Shopify behavior)
    if chosen is None:
        chosen = all_candidates[0]
    item, offers = chosen

    availability = _ci_get(offers, "availability") or ""
    in_stock = "InStock" in str(availability) or "PreOrder" in str(availability)

    image = _ci_get(item, "image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        # Schema.org ImageObject uses "url"; Wix emits "contentUrl".
        image = _ci_get(image, "url") or _ci_get(image, "contentUrl")

    inventory = _ci_get(offers, "inventoryLevel")
    if isinstance(inventory, dict):
        inventory = _ci_get(inventory, "value")
    try:
        stock_count = int(inventory) if inventory is not None else None
    except (ValueError, TypeError):
        stock_count = None

    brand = _ci_get(item, "brand")
    retailer = _ci_get(brand, "name") if isinstance(brand, dict) else None

    return {
        "title": _ci_get(item, "name") or "",
        "price": _offer_price(offers) or 0.0,
        "currency": _ci_get(offers, "priceCurrency") or "",
        "in_stock": in_stock,
        "stock_count": stock_count,
        "image_url": image,
        "sku": _ci_get(item, "sku") or _ci_get(item, "mpn"),
        "retailer": retailer,
    }


def _coerce_price(value: Any) -> float | None:
    """Parse a price-ish value to float, tolerating commas. None on junk."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _json_array_after_key(blob: str, key: str) -> Any | None:
    """Extract and parse the JSON array that follows ``"key":`` in a blob.

    Wix embeds product option/variant data as raw JSON inside a regular
    ``<script>`` (not ld+json), so the whole page can't be json.loads'd.
    This locates ``"key":[ ... ]`` and bracket-matches to pull just that
    array, tracking string/escape state so brackets inside string values
    don't throw off the depth count. Tries successive occurrences until one
    parses. Returns the parsed array, or None when absent/unparseable.
    """
    marker = '"' + key + '"'
    pos = 0
    while True:
        i = blob.find(marker, pos)
        if i == -1:
            return None
        j = i + len(marker)
        while j < len(blob) and blob[j] in " \t\r\n":
            j += 1
        if j >= len(blob) or blob[j] != ":":
            pos = i + len(marker)
            continue
        j += 1
        while j < len(blob) and blob[j] in " \t\r\n":
            j += 1
        if j >= len(blob) or blob[j] != "[":
            pos = i + len(marker)
            continue
        depth = 0
        in_str = False
        esc = False
        end = -1
        for k in range(j, len(blob)):
            c = blob[k]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        if end == -1:
            return None
        try:
            return json.loads(blob[j:end + 1])
        except (json.JSONDecodeError, ValueError):
            pos = i + len(marker)
            continue


def try_wix_variant(
    html: str, variant_options: list[str], url: str | None = None
) -> dict[str, Any] | None:
    """Resolve a specific Wix product variant's price by its option labels.

    Wix product pages embed *all* variant combinations as a JSON
    ``productItems`` array, plus an ``options`` array mapping selection ids
    to human labels ("1xIR Remote", "5-48V", ...). The page's JSON-LD only
    exposes ONE default price; the others render only after a client-side
    option click that a server-side fetch never triggers. Reading the
    embedded data lets us track a non-default combo (e.g. "with remote")
    without a headless browser.

    ``variant_options`` are the desired option VALUES (case-insensitive),
    e.g. ``["1xIR Remote", "5-48V"]``. A productItem matches when its
    selection labels are a superset of these — options the user didn't pin
    (like a lone "WLED" firmware) are ignored.

    Returns ``{price, currency, in_stock, matched}`` for the matching
    variant, or None when the page isn't a Wix variant page or no combo
    matches (caller then falls back to JSON-LD/AI).
    """
    wanted = [
        str(v).strip().lower() for v in (variant_options or []) if str(v).strip()
    ]
    if not wanted:
        return None

    options = _json_array_after_key(html, "options")
    items = _json_array_after_key(html, "productItems")
    if not isinstance(options, list) or not isinstance(items, list) or not items:
        return None

    # selection id -> human label
    sel_label: dict[Any, str] = {}
    for opt in options:
        if not isinstance(opt, dict):
            continue
        for sel in opt.get("selections") or []:
            if isinstance(sel, dict) and "id" in sel:
                sel_label[sel["id"]] = str(sel.get("value", ""))

    currency = ""
    cur_match = re.search(r'"priceCurrency"\s*:\s*"([A-Za-z]{3})"', html)
    if cur_match:
        currency = cur_match.group(1).upper()

    for it in items:
        if not isinstance(it, dict):
            continue
        labels = {
            sel_label.get(s, "").strip().lower()
            for s in (it.get("optionsSelections") or [])
        }
        if not all(w in labels for w in wanted):
            continue

        price = _coerce_price(it.get("price"))
        compare = _coerce_price(it.get("comparePrice"))
        has_discount = bool(it.get("hasDiscount"))
        # Selling price: when on sale it's the LOWER of the two. This is
        # robust to both standard Wix (comparePrice = higher strikethrough)
        # and stores that invert the fields (athom.tech lists the sale price
        # under comparePrice). Otherwise the plain price.
        if has_discount and price and compare:
            current = min(price, compare)
        else:
            current = price if price else compare
        if not current or current <= 0:
            return None

        in_stock = it.get("inStock")
        return {
            "price": float(current),
            "currency": currency,
            "in_stock": True if in_stock is None else bool(in_stock),
            "matched": sorted(lbl for lbl in labels if lbl),
        }

    return None


def list_wix_variants(html: str) -> dict[str, Any] | None:
    """Enumerate a Wix product page's variant option groups and combos.

    Companion to ``try_wix_variant``: where that resolves ONE combo's price
    from a set of pinned labels, this lists EVERY option group (e.g.
    "Remote", "Voltage") with its choices, plus every concrete combo the
    page ships with its price. The panel uses this to render dropdowns and
    a live price preview so the user can pick a variant visually instead of
    typing labels.

    Reply shape (or None when the page isn't a Wix variant page):
        {
          "options": [
            {"title": "Remote", "choices": ["None", "1xIR Remote", ...]},
            {"title": "Voltage", "choices": ["5-24V", "5-48V"]},
          ],
          "variants": [
            {"labels": ["None", "5-24V"], "price": 16.78,
             "currency": "USD", "in_stock": true},
            ...
          ],
          "currency": "USD",
        }

    Each combo's ``labels`` are ordered to match the ``options`` group
    order, so the panel can zip a dropdown selection straight back into the
    label set ``set_variant`` / ``edit_listing`` expect.
    """
    options = _json_array_after_key(html, "options")
    items = _json_array_after_key(html, "productItems")
    if not isinstance(options, list) or not isinstance(items, list) or not items:
        return None

    # Build the ordered option groups and a selection-id -> (group_index,
    # label) map so each productItem's selections can be slotted back into
    # the right group and ordered consistently.
    groups: list[dict[str, Any]] = []
    sel_meta: dict[Any, tuple[int, str]] = {}
    for gi, opt in enumerate(options):
        if not isinstance(opt, dict):
            continue
        title = str(
            opt.get("title") or opt.get("name") or opt.get("key") or f"Option {gi + 1}"
        ).strip()
        choices: list[str] = []
        for sel in opt.get("selections") or []:
            if not isinstance(sel, dict):
                continue
            label = str(sel.get("value", "")).strip()
            if not label:
                continue
            if "id" in sel:
                sel_meta[sel["id"]] = (gi, label)
            if label not in choices:
                choices.append(label)
        if choices:
            groups.append({"title": title or f"Option {gi + 1}", "choices": choices})

    if not groups:
        return None

    currency = ""
    cur_match = re.search(r'"priceCurrency"\s*:\s*"([A-Za-z]{3})"', html)
    if cur_match:
        currency = cur_match.group(1).upper()

    variants: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        # Order each combo's labels by their group index so they line up
        # with the `options` order the panel renders.
        ordered: list[tuple[int, str]] = []
        for s in it.get("optionsSelections") or []:
            meta = sel_meta.get(s)
            if meta is not None:
                ordered.append(meta)
        ordered.sort(key=lambda m: m[0])
        labels = [lbl for _, lbl in ordered]
        if not labels:
            continue

        price = _coerce_price(it.get("price"))
        compare = _coerce_price(it.get("comparePrice"))
        has_discount = bool(it.get("hasDiscount"))
        if has_discount and price and compare:
            current = min(price, compare)
        else:
            current = price if price else compare
        if not current or current <= 0:
            continue

        key = tuple(lbl.lower() for lbl in labels)
        if key in seen:
            continue
        seen.add(key)

        in_stock = it.get("inStock")
        variants.append(
            {
                "labels": labels,
                "price": float(current),
                "currency": currency,
                "in_stock": True if in_stock is None else bool(in_stock),
            }
        )

    if not variants:
        return None

    return {"options": groups, "variants": variants, "currency": currency}


def _byko_product(html: str) -> dict[str, Any] | None:
    """Pull byko.is's Next.js ``product`` object (with its variant list).

    byko renders on Next.js, embedding the full product — every size
    variant, each with its own price and stock flag — in a
    ``<script id="__NEXT_DATA__">`` JSON blob. Returns that ``product`` dict
    (guaranteed to carry a ``variants`` list) or None when the page isn't a
    byko product page.
    """
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    try:
        prod = data["props"]["pageProps"]["product"]
    except (KeyError, TypeError):
        return None
    if not isinstance(prod, dict) or not isinstance(prod.get("variants"), list):
        return None
    return prod


def _byko_variant_label(name: str, base: str) -> str:
    """The distinguishing tail of a byko variant name (e.g. the length).

    Variant names repeat the product name plus a trailing size token
    ("FURA ALHEF 45X95 AB-GAGNV" + " 480"). Strip the shared prefix so the
    picker shows just "480" rather than the whole repeated name. Falls back
    to the full name when it doesn't start with the base.
    """
    name = (name or "").strip()
    base = (base or "").strip()
    if base and name.lower().startswith(base.lower()):
        rest = name[len(base):].strip(" -–— ")
        if rest:
            return rest
    return name


def _byko_in_stock(v: dict[str, Any]) -> bool:
    """A byko variant counts as in stock if it's in a store OR the webstore."""
    return bool(v.get("inStock") or v.get("webstoreInStock"))


def _byko_variant_image(v: dict[str, Any]) -> str | None:
    """Best image URL for a byko variant (gallery render), if any."""
    img = (v.get("firstImage") or {}).get("image") or {}
    if isinstance(img, dict):
        for key in ("productGallery2x", "productGallery", "productList"):
            url = img.get(key)
            if url:
                return str(url)
    return None


def list_byko_variants(html: str) -> dict[str, Any] | None:
    """Enumerate a byko.is product's size/length variants.

    The byko analogue of ``list_wix_variants``: every size of a product
    (e.g. lumber lengths 120-660 cm) ships in ``__NEXT_DATA__`` as
    ``product.variants[]`` with its own gross price and stock flag. Returns
    the SAME unified ``{options, variants, currency}`` shape so the panel's
    variant picker renders byko exactly like a Wix multi-option product —
    one option group ("Length", or "Variant" for non-numeric sizes).

    None when the page isn't a byko variant page.
    """
    prod = _byko_product(html)
    if prod is None:
        return None
    base = str(prod.get("name") or "")

    currency = ""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for v in prod.get("variants") or []:
        if not isinstance(v, dict):
            continue
        price = v.get("price") or {}
        gross = _coerce_price(price.get("gross"))
        if not gross or gross <= 0:
            continue
        label = _byko_variant_label(str(v.get("name") or ""), base)
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        cur = str(price.get("currency") or "").upper()
        if not currency:
            currency = cur
        rows.append(
            {
                "labels": [label],
                "price": float(gross),
                "currency": cur or currency,
                "in_stock": _byko_in_stock(v),
            }
        )
    if not rows:
        return None

    # Sort numerically when every choice is a bare size (120, 150, … 660),
    # else lexically — so the dropdown never reads 120, 1500, 180.
    def _key(r: dict[str, Any]) -> tuple[int, Any]:
        lab = r["labels"][0]
        return (0, int(lab)) if lab.isdigit() else (1, lab.lower())

    rows.sort(key=_key)
    choices = [r["labels"][0] for r in rows]
    title = "Length" if all(c.isdigit() for c in choices) else "Variant"

    return {
        "options": [{"title": title, "choices": choices}],
        "variants": rows,
        "currency": currency,
    }


def try_byko_variant(
    html: str, variant_options: list[str]
) -> dict[str, Any] | None:
    """Resolve a pinned byko.is variant's price + title by its size label.

    The byko analogue of ``try_wix_variant``: given the pinned label(s)
    (e.g. ``["480"]``), find the matching ``product.variants[]`` entry and
    return its gross price, full name (so the tile title follows the chosen
    size), stock flag and image. byko pages carry no JSON-LD, so the variant
    itself is the only source of the title here.

    Returns ``{price, currency, in_stock, matched, title, sku, image_url,
    retailer, method}`` or None when the page isn't byko or nothing matches.
    """
    wanted = [
        str(v).strip().lower() for v in (variant_options or []) if str(v).strip()
    ]
    if not wanted:
        return None
    prod = _byko_product(html)
    if prod is None:
        return None
    base = str(prod.get("name") or "")

    for v in prod.get("variants") or []:
        if not isinstance(v, dict):
            continue
        name = str(v.get("name") or "")
        label = _byko_variant_label(name, base).lower()
        sku = str(v.get("sku") or "")
        sku_mid = sku.split("::", 1)[1].strip(": ").lower() if "::" in sku else ""
        # Match the pinned value against the size token, the sku's middle
        # segment, or a trailing-token fallback.
        if not any(
            w == label or w == sku_mid or name.lower().endswith(" " + w)
            for w in wanted
        ):
            continue
        gross = _coerce_price((v.get("price") or {}).get("gross"))
        if not gross or gross <= 0:
            return None
        currency = str((v.get("price") or {}).get("currency") or "").upper()
        # Price-per-meter: byko lumber names/skus end in the length in cm
        # (…AB-GAGNV 480). kr/m = gross ÷ (length_cm / 100).
        unit_price = None
        unit_label = None
        len_match = re.search(r"(\d{2,4})\s*$", name)
        if len_match:
            length_cm = int(len_match.group(1))
            if length_cm > 0:
                unit_price = round(gross / (length_cm / 100))
                unit_label = "kr/m"
        return {
            "price": float(gross),
            "currency": currency,
            "in_stock": _byko_in_stock(v),
            "matched": [label] if label else list(wanted),
            "title": name,
            "sku": sku or None,
            "image_url": _byko_variant_image(v),
            "unit_price": unit_price,
            "unit_label": unit_label,
            "retailer": "BYKO",
            "method": "byko_variant",
        }
    return None


def list_variants(html: str) -> dict[str, Any] | None:
    """Enumerate a page's variant options, whatever the platform.

    Tries each platform-specific enumerator (Wix, then byko.is) and returns
    the first hit in the unified ``{options, variants, currency}`` shape the
    panel's variant picker consumes. None when the page has no recognizable
    variant data.
    """
    return list_wix_variants(html) or list_byko_variants(html)


async def _fetch_with_curl_cffi(
    url: str,
    method: str = "GET",
    body: str | None = None,
    extra_headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> str | None:
    """Fetch URL using curl_cffi with Chrome TLS fingerprint.

    Uses a module-level persistent AsyncSession that accumulates cookies
    across all fetches in this HA process. Cookies dramatically improve
    success rate against bot-detecting sites (especially Amazon).

    Returns response body on success, None when curl_cffi isn't installed
    (caller should fall back to aiohttp). Raises ExtractionError on
    actual fetch failures.
    """
    session = await _get_persistent_session()
    if session is None:
        _LOGGER.debug("curl_cffi not available, falling back to aiohttp")
        return None

    method = (method or "GET").upper()
    headers = dict(extra_headers) if extra_headers else None

    try:
        if method == "POST":
            response = await session.post(
                url,
                data=body,
                headers=headers,
                cookies=cookies,
                timeout=HTTP_TIMEOUT,
                allow_redirects=True,
            )
        else:
            response = await session.get(
                url,
                headers=headers,
                cookies=cookies,
                timeout=HTTP_TIMEOUT,
                allow_redirects=True,
            )
        if response.status_code >= 400:
            snippet = (response.text or "")[:200].replace("\n", " ")
            raise ExtractionError(
                f"HTTP {response.status_code} from {url}. Response preview: {snippet}"
            )
        return response.text
    except ExtractionError:
        raise
    except Exception as err:  # noqa: BLE001
        raise ExtractionError(
            f"curl_cffi error fetching {url}: {type(err).__name__}: {err}"
        ) from err


async def _fetch_with_aiohttp(
    url: str,
    session: aiohttp.ClientSession,
    method: str = "GET",
    body: str | None = None,
    extra_headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> str:
    """Fetch URL using HA's shared aiohttp session (fallback path)."""
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=10)
    method = (method or "GET").upper()
    headers = dict(BROWSER_HEADERS)
    if extra_headers:
        headers.update(extra_headers)

    try:
        if method == "POST":
            ctx = session.post(
                url,
                data=body,
                headers=headers,
                cookies=cookies,
                timeout=timeout,
                allow_redirects=True,
            )
        else:
            ctx = session.get(
                url,
                headers=headers,
                cookies=cookies,
                timeout=timeout,
                allow_redirects=True,
            )
        async with ctx as response:
            text = await response.text()
            if response.status >= 400:
                snippet = text[:200].replace("\n", " ")
                raise ExtractionError(
                    f"HTTP {response.status} from {url}. Response preview: {snippet}"
                )
            return text
    except asyncio.TimeoutError as err:
        raise ExtractionError(
            f"Timeout fetching {url} after {HTTP_TIMEOUT}s. "
            f"The site may be blocking the request or rate-limiting."
        ) from err
    except aiohttp.ClientError as err:
        raise ExtractionError(
            f"Network error fetching {url}: {type(err).__name__}: {err}"
        ) from err


async def fetch_html(
    url: str,
    session: aiohttp.ClientSession,
    method: str = "GET",
    body: str | None = None,
    extra_headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> str:
    """Fetch URL, preferring curl_cffi (Chrome TLS impersonation) over aiohttp.

    Goes through the global fetch throttle (concurrency cap + per-host
    politeness gap) so a fleet of tracked products doesn't burst-hit stores.
    """
    async with _fetch_slot(url):
        html = await _fetch_with_curl_cffi(
            url, method=method, body=body, extra_headers=extra_headers, cookies=cookies
        )
        if html is not None:
            return html
        return await _fetch_with_aiohttp(
            url, session, method=method, body=body, extra_headers=extra_headers,
            cookies=cookies,
        )


async def fetch_image_bytes(
    url: str, session: aiohttp.ClientSession
) -> tuple[bytes, str] | None:
    """Fetch image bytes for a product photo.

    Uses the persistent curl_cffi session so image CDN cookies match the
    page session. Returns (bytes, content_type) or None on failure.
    """
    if not url:
        return None

    # Image CDNs aren't the bot-guarded product pages, so only the global
    # concurrency cap applies (no per-host gap) — it still keeps images out
    # of the restart fetch burst.
    async with _fetch_slot(url, politeness=False):
        cffi_session = await _get_persistent_session()
        if cffi_session is not None:
            try:
                response = await cffi_session.get(
                    url, timeout=HTTP_TIMEOUT, allow_redirects=True
                )
                if response.status_code < 400 and response.content:
                    ct = response.headers.get("content-type", "image/jpeg")
                    ct = ct.split(";")[0].strip()
                    return bytes(response.content), ct
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("curl_cffi image fetch failed for %s: %s", url, err)

        # Fall back to aiohttp
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT, connect=10)
        try:
            async with session.get(
                url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True,
            ) as response:
                if response.status >= 400:
                    return None
                data = await response.read()
                if not data:
                    return None
                ct = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                return data, ct
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("aiohttp image fetch failed for %s: %s", url, err)
            return None


async def _extract_via_provider(
    cleaned_html: str, ai_provider: AIProvider
) -> tuple[dict[str, Any], float]:
    """Run AI extraction, translating provider errors to ExtractionError.

    Keeps the call sites simple: they only have to handle ExtractionError.
    """
    try:
        result = await ai_provider.extract_product(cleaned_html)
    except AIProviderError as err:
        raise ExtractionError(f"AI extraction failed: {err}") from err
    return result.data, result.cost_usd


async def extract_product(
    url: str,
    session: aiohttp.ClientSession,
    ai_provider: AIProvider | None = None,
    custom_parser: dict[str, Any] | None = None,
    previous_hash: str | None = None,
    variant_options: list[str] | None = None,
) -> ExtractionResult:
    """Top-level extraction entry point.

    Order of preference:
    1. Custom parser if defined (no API cost). Custom parsers may override
       the URL/method/body, allowing fetches against retailer JSON APIs.
       If the parser fails AND an ai_provider is configured, AI extraction
       is tried as a fallback before propagating the error.
    2. Wix variant override (no API cost) when ``variant_options`` is set —
       reads a specific option combo's price from the page's embedded data.
    3. JSON-LD if present (no API cost).
    4. AI extraction via ai_provider (paid for hosted providers, free for
       local).
    """
    if custom_parser and not custom_parser.get("selectors"):
        # A parser with no selectors can't extract anything (css/regex/
        # jsonpath iterate selectors; raw_json needs them too) — it's a
        # "cookies-only" config that exists purely to fetch cookie-walled
        # pages. Don't force it down the css path (which would raise "did
        # not extract a title"); instead lift its cookies and fall through
        # to the standard JSON-LD → AI pipeline so the cookied HTML is read
        # normally. This is the whole point of cookies on a site that serves
        # real content (and JSON-LD) only to returning visitors, e.g. Amazon.
        passthrough_cookies = _normalize_cookies(custom_parser.get("request_cookies"))
        custom_parser = None
    else:
        passthrough_cookies = None

    if custom_parser:
        from .parsers import apply_custom_parser, ParserError

        fetch_url = custom_parser.get("url") or url
        fetch_method = custom_parser.get("request_method", "GET")
        fetch_body = custom_parser.get("request_body")
        fetch_headers = custom_parser.get("request_headers")
        fetch_cookies = _normalize_cookies(custom_parser.get("request_cookies"))

        body = await fetch_html(
            fetch_url,
            session=session,
            method=fetch_method,
            body=fetch_body,
            extra_headers=fetch_headers,
            cookies=fetch_cookies,
        )

        if custom_parser.get("type") == "raw_json":
            content_hash = hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()
            cleaned = body
        else:
            cleaned, content_hash = preprocess_html(body)

        if previous_hash and previous_hash == content_hash:
            raise ExtractionError("UNCHANGED")

        # Try the parser first
        try:
            data = apply_custom_parser(body, custom_parser)
        except ParserError as parser_err:
            # Custom parser failed. If we have an ai_provider and the body
            # is HTML (not JSON), try AI extraction on the same response
            # as a rescue. This handles cases like Amazon's "Continue
            # shopping" interstitial: the parser misses our expected
            # selectors, but the AI can sometimes still extract from
            # whatever is there (or correctly identify a CAPTCHA and fail
            # cleanly).
            if ai_provider is not None and custom_parser.get("type") != "raw_json":
                _LOGGER.warning(
                    "Custom parser failed (%s); trying AI fallback",
                    parser_err,
                )
                try:
                    ai_data, cost = await _extract_via_provider(cleaned, ai_provider)
                    # If the AI flagged the product as discontinued, treat
                    # it as a TERMINAL successful extraction — not an
                    # error. We carry forward whatever title/retailer the
                    # AI could still read off the page, even when the
                    # price area is gone.
                    if ai_data.get("is_discontinued"):
                        ai_reason = (ai_data.get("not_found_reason") or "").strip() or None
                        # Use AI's title if it kept one, otherwise the
                        # NO_PRODUCT_FOUND sentinel becomes a placeholder.
                        disc_title = (ai_data.get("title") or "").strip()
                        if disc_title in ("", "NO_PRODUCT_FOUND", "<UNKNOWN>"):
                            disc_title = "(discontinued product)"
                        return ExtractionResult(
                            title=disc_title,
                            price=0.0,
                            currency=ai_data.get("currency") or custom_parser.get("default_currency", ""),
                            in_stock=False,
                            stock_count=0,
                            image_url=ai_data.get("image_url") or find_meta_image(body),
                            sku=ai_data.get("sku"),
                            retailer=ai_data.get("retailer") or custom_parser.get("default_retailer"),
                            content_hash=content_hash,
                            cost_usd=cost,
                            method=f"custom+{ai_provider.name}+discontinued",
                            raw=ai_data,
                            discontinued=True,
                            discontinued_reason=ai_reason,
                        )
                    # Reject the AI's "I see nothing" sentinel and obvious
                    # fabricated values. Without these checks a forced
                    # tool-use response would silently submit bogus
                    # entries when the page is a CAPTCHA or empty.
                    ai_title = (ai_data.get("title") or "").strip()
                    ai_price = ai_data.get("price")
                    if (ai_title in ("", "NO_PRODUCT_FOUND", "<UNKNOWN>", "Unknown product", "Unknown")
                            or ai_price in (None, 0, 0.0)
                            or (isinstance(ai_price, (int, float)) and ai_price <= 0)):
                        ai_reason = (ai_data.get("not_found_reason") or "").strip()
                        reason_clause = (
                            f" Reason: {ai_reason}" if ai_reason
                            else " The page is likely a bot-check or interstitial."
                        )
                        raise ExtractionError(
                            f"AI fallback found no product (title={ai_title!r}, "
                            f"price={ai_price!r}).{reason_clause} "
                            f"(Original parser error: {parser_err})"
                        )
                    stock_count = ai_data.get("stock_count") or guess_stock_count(body)
                    image_url = ai_data.get("image_url") or find_meta_image(body)
                    return ExtractionResult(
                        title=ai_title,
                        price=float(ai_price),
                        currency=ai_data.get("currency") or custom_parser.get("default_currency", ""),
                        in_stock=ai_data.get("in_stock", True),
                        stock_count=stock_count,
                        image_url=image_url,
                        sku=ai_data.get("sku"),
                        retailer=ai_data.get("retailer") or custom_parser.get("default_retailer"),
                        content_hash=content_hash,
                        cost_usd=cost,
                        method=f"custom+{ai_provider.name}",
                        raw=ai_data,
                    )
                except ExtractionError as ai_err:
                    _LOGGER.warning("AI fallback also failed: %s", ai_err)
                    # Re-raise the ORIGINAL parser error so the user sees
                    # the diagnostic info (page title, body snippet etc.)
                    raise parser_err from ai_err
            # No provider, or raw_json parser - propagate as-is
            raise

        stock_count = data.get("stock_count")
        if stock_count is None and custom_parser.get("type") != "raw_json":
            stock_count = guess_stock_count(body)
        image_url = data.get("image_url")
        if not image_url and custom_parser.get("type") != "raw_json":
            image_url = find_meta_image(body)
        # Per-store stock (Húsa-style). When present it's also the most
        # authoritative in-stock signal: in stock only if SOME store has it
        # (in_stock/limited), overriding the parser's default.
        store_avail = _parse_store_availability(body)
        in_stock_val = data.get("in_stock", True)
        if store_avail:
            in_stock_val = any(
                s["status"] in ("in_stock", "limited") for s in store_avail
            )
        meta = _extract_product_meta(body)

        return ExtractionResult(
            title=data["title"],
            price=data["price"],
            currency=data.get("currency", ""),
            in_stock=in_stock_val,
            stock_count=stock_count,
            image_url=image_url,
            sku=data.get("sku"),
            retailer=data.get("retailer"),
            original_price=data.get("original_price"),
            store_availability=store_avail,
            product_number=meta.get("product_number"),
            description_name=meta.get("description_name"),
            content_hash=content_hash,
            cost_usd=0.0,
            method="custom",
            raw=data,
        )

    # No custom parser: standard JSON-LD then Claude pipeline. passthrough_cookies
    # carries any cookies lifted from a cookies-only parser above, so a
    # cookie-walled page still reaches the JSON-LD / AI extractor.
    html = await fetch_html(url, session=session, cookies=passthrough_cookies)
    cleaned, content_hash = preprocess_html(html)

    if previous_hash and previous_hash == content_hash:
        raise ExtractionError("UNCHANGED")

    # Variant override: when the user pinned a specific option combo
    # (e.g. "With IR Remote / 5-48V"), read that variant's price from the
    # page's embedded Wix data. The page's JSON-LD only carries the default
    # combo, so without this we'd always track the cheapest/base config.
    # Falls through to JSON-LD/AI if the page isn't a Wix variant page or no
    # combo matches.
    if variant_options:
        variant = try_wix_variant(html, variant_options, url=url) or try_byko_variant(
            html, variant_options
        )
        if variant and variant.get("price"):
            # byko pages have no JSON-LD, so the variant supplies the title /
            # image / sku itself; Wix variants borrow them from JSON-LD.
            base = try_jsonld(html, url=url) or {}
            meta = _extract_product_meta(html, variant_sku=variant.get("sku"))
            return ExtractionResult(
                title=variant.get("title") or base.get("title", "") or "",
                price=variant["price"],
                currency=variant.get("currency") or base.get("currency", ""),
                in_stock=variant.get("in_stock", True),
                stock_count=base.get("stock_count"),
                image_url=variant.get("image_url")
                or base.get("image_url")
                or find_meta_image(html),
                sku=variant.get("sku") or base.get("sku"),
                retailer=variant.get("retailer") or base.get("retailer"),
                product_number=meta.get("product_number"),
                description_name=meta.get("description_name"),
                unit_price=variant.get("unit_price"),
                unit_label=variant.get("unit_label"),
                content_hash=content_hash,
                cost_usd=0.0,
                method=variant.get("method", "wix_variant"),
                raw={"variant_options": list(variant_options), **variant},
            )
        _LOGGER.warning(
            "variant_options=%r set but no matching variant found at "
            "%s; falling back to default extraction",
            variant_options, url,
        )

    jsonld = try_jsonld(html, url=url)
    if jsonld and jsonld.get("price"):
        stock_count = jsonld.get("stock_count")
        if stock_count is None:
            stock_count = guess_stock_count(html)
        image_url = jsonld.get("image_url") or find_meta_image(html)
        # Per-store stock (JYSK / Húsa). When present it's the most
        # authoritative in-stock signal — in stock only if SOME store has it.
        store_avail = _parse_store_availability(html)
        in_stock_val = jsonld.get("in_stock", True)
        if store_avail:
            in_stock_val = any(
                s["status"] in ("in_stock", "limited") for s in store_avail
            )
        # Sale 'was' price (JYSK strikethrough). JSON-LD only has the current
        # price; the sensor turns a higher original_price into the sale badge.
        original_price = jsonld.get("original_price") or _parse_jysk_original_price(
            html
        )
        # Sibling size pages (JYSK "Stærðir") — the panel uses these to swap
        # the tracked URL between sizes.
        size_options = _parse_jysk_sizes(html, url)
        meta = _extract_product_meta(html)
        return ExtractionResult(
            title=jsonld["title"],
            price=jsonld["price"],
            currency=jsonld.get("currency", ""),
            in_stock=in_stock_val,
            stock_count=stock_count,
            image_url=image_url,
            sku=jsonld.get("sku"),
            retailer=jsonld.get("retailer"),
            original_price=original_price,
            store_availability=store_avail,
            size_options=size_options,
            product_number=meta.get("product_number"),
            description_name=meta.get("description_name"),
            content_hash=content_hash,
            cost_usd=0.0,
            method="jsonld",
            raw=jsonld,
        )

    if ai_provider is None:
        raise ExtractionError(
            "No JSON-LD found and no AI provider configured for fallback extraction"
        )

    data, cost = await _extract_via_provider(cleaned, ai_provider)
    # Discontinued products return a successful (terminal) result so the
    # coordinator can persist the state and stop polling. Check this
    # BEFORE the NO_PRODUCT_FOUND sentinel handling so we don't reject
    # a legitimately-discontinued page as if it were a bot-check.
    if data.get("is_discontinued"):
        ai_reason = (data.get("not_found_reason") or "").strip() or None
        disc_title = (data.get("title") or "").strip()
        if disc_title in ("", "NO_PRODUCT_FOUND", "<UNKNOWN>"):
            disc_title = "(discontinued product)"
        return ExtractionResult(
            title=disc_title,
            price=0.0,
            currency=data.get("currency", ""),
            in_stock=False,
            stock_count=0,
            image_url=data.get("image_url") or find_meta_image(html),
            sku=data.get("sku"),
            retailer=data.get("retailer"),
            content_hash=content_hash,
            cost_usd=cost,
            method=f"{ai_provider.name}+discontinued",
            raw=data,
            discontinued=True,
            discontinued_reason=ai_reason,
        )
    ai_title = (data.get("title") or "").strip()
    ai_price = data.get("price")
    if (ai_title in ("", "NO_PRODUCT_FOUND", "<UNKNOWN>", "Unknown product", "Unknown")
            or ai_price in (None, 0, 0.0)
            or (isinstance(ai_price, (int, float)) and ai_price <= 0)):
        ai_reason = (data.get("not_found_reason") or "").strip()
        reason_clause = (
            f" Reason: {ai_reason}" if ai_reason
            else " The page may be a bot-check or interstitial."
        )
        raise ExtractionError(
            f"AI extraction found no product (title={ai_title!r}, "
            f"price={ai_price!r}).{reason_clause}"
        )
    stock_count = data.get("stock_count")
    if stock_count is None:
        stock_count = guess_stock_count(html)
    image_url = data.get("image_url") or find_meta_image(html)
    return ExtractionResult(
        title=ai_title,
        price=float(ai_price),
        currency=data.get("currency", ""),
        in_stock=data.get("in_stock", True),
        stock_count=stock_count,
        image_url=image_url,
        sku=data.get("sku"),
        retailer=data.get("retailer"),
        content_hash=content_hash,
        cost_usd=cost,
        method=ai_provider.name,
        raw=data,
    )
