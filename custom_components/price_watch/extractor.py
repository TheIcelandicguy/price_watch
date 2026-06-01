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
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from bs4 import BeautifulSoup, Comment

from .ai import AIProvider, AIProviderError
from .const import (
    HTTP_TIMEOUT,
    USER_AGENT,
)

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
                if isinstance(variants, list):
                    for v in variants:
                        if isinstance(v, dict):
                            expanded.append(v)
                    continue  # Drop the wrapper itself; only variants count
            expanded.append(item)

        for item in expanded:
            if not isinstance(item, dict):
                continue
            type_ = item.get("@type")
            if type_ != "Product" and (
                not isinstance(type_, list) or "Product" not in type_
            ):
                continue

            offers = item.get("offers")
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if not isinstance(offers, dict):
                continue

            try:
                price = float(str(offers.get("price", "")).replace(",", "."))
            except (ValueError, TypeError):
                continue
            if price <= 0:
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

    availability = offers.get("availability", "")
    in_stock = "InStock" in str(availability) or "PreOrder" in str(availability)

    image = item.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")

    inventory = offers.get("inventoryLevel")
    if isinstance(inventory, dict):
        inventory = inventory.get("value")
    try:
        stock_count = int(inventory) if inventory is not None else None
    except (ValueError, TypeError):
        stock_count = None

    brand = item.get("brand")
    retailer = brand.get("name") if isinstance(brand, dict) else None

    return {
        "title": item.get("name", ""),
        "price": float(str(offers.get("price", "")).replace(",", ".")),
        "currency": offers.get("priceCurrency", ""),
        "in_stock": in_stock,
        "stock_count": stock_count,
        "image_url": image,
        "sku": item.get("sku") or item.get("mpn"),
        "retailer": retailer,
    }


def _normalize_cookies(cookies: Any) -> dict[str, str] | None:
    """Accept cookies as a dict or cookie-header string; return a dict.

    Supports the format users typically copy from browser DevTools, which
    is a single Cookie header value like:
        session-id=123-456-789; ubid-acbuk=ABC; i18n-prefs=GBP
    Also accepts a JSON dict form: {"session-id": "123", ...} and the list
    of cookie dicts form documented in services.yaml:
        [{"name": "session-id", "value": "123", ...}, ...]
    """
    if not cookies:
        return None
    if isinstance(cookies, dict):
        return {str(k): str(v) for k, v in cookies.items() if v is not None}
    if isinstance(cookies, list):
        result: dict[str, str] = {}
        for item in cookies:
            if isinstance(item, dict):
                name = item.get("name")
                value = item.get("value")
                if name is not None and value is not None:
                    result[str(name)] = str(value)
        return result or None
    if isinstance(cookies, str):
        result: dict[str, str] = {}
        for pair in cookies.split(";"):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            name, _, value = pair.partition("=")
            name = name.strip()
            value = value.strip()
            if name:
                result[name] = value
        return result or None
    return None


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
    """Fetch URL, preferring curl_cffi (Chrome TLS impersonation) over aiohttp."""
    html = await _fetch_with_curl_cffi(
        url, method=method, body=body, extra_headers=extra_headers, cookies=cookies
    )
    if html is not None:
        return html
    return await _fetch_with_aiohttp(
        url, session, method=method, body=body, extra_headers=extra_headers, cookies=cookies
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
) -> ExtractionResult:
    """Top-level extraction entry point.

    Order of preference:
    1. Custom parser if defined (no API cost). Custom parsers may override
       the URL/method/body, allowing fetches against retailer JSON APIs.
       If the parser fails AND an ai_provider is configured, AI extraction
       is tried as a fallback before propagating the error.
    2. JSON-LD if present (no API cost).
    3. AI extraction via ai_provider (paid for hosted providers, free for
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
        return ExtractionResult(
            title=data["title"],
            price=data["price"],
            currency=data.get("currency", ""),
            in_stock=data.get("in_stock", True),
            stock_count=stock_count,
            image_url=image_url,
            sku=data.get("sku"),
            retailer=data.get("retailer"),
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

    jsonld = try_jsonld(html, url=url)
    if jsonld and jsonld.get("price"):
        stock_count = jsonld.get("stock_count")
        if stock_count is None:
            stock_count = guess_stock_count(html)
        image_url = jsonld.get("image_url") or find_meta_image(html)
        return ExtractionResult(
            title=jsonld["title"],
            price=jsonld["price"],
            currency=jsonld.get("currency", ""),
            in_stock=jsonld.get("in_stock", True),
            stock_count=stock_count,
            image_url=image_url,
            sku=jsonld.get("sku"),
            retailer=jsonld.get("retailer"),
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
