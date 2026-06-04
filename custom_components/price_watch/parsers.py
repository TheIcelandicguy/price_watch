"""Custom parser support for Price Watch.

Users can define their own parsers per URL to skip API calls entirely.
Parsers are dicts with shape:

{
    "type": "css" | "regex" | "jsonpath" | "raw_json",
    "selectors": {
        "title": "<selector>",
        "price": "<selector>",
        "currency": "<selector or static>",
        "image_url": "<optional selector>",
        "stock_count": "<optional selector>",
        "in_stock": "<optional selector or template>",
    },
    "transforms": {
        "price": "regex:[^0-9.,]|replace:,:.|float",
    },

    # Optional: control how the page is fetched
    "request_method": "GET" | "POST",     # default GET
    "request_body": "<raw string>",       # body to send (POST only)
    "request_headers": {"Header": "v"},   # extra headers
    "url": "<override url>",              # if set, fetch this instead of entry URL

    # Optional: defaults applied when fields are missing
    "default_currency": "ISK",
    "default_retailer": "Tölvutek",
    "url_base": "https://tolvutek.is",    # prefixed via 'prefix:' transform
}

Parser types:
  - css      : BeautifulSoup CSS selectors against HTML
  - regex    : regex with one capture group, against raw HTML
  - jsonpath : extract from window.__NEXT_DATA__ or similar JS state in HTML
  - raw_json : the response body IS JSON; selector is a dotted path

Transforms (chain with `|`):
  regex:<pattern>    remove all matches of pattern
  replace:from:to    string replace
  prefix:<str>       prepend <str> to value (useful for relative URLs)
  float / int        cast
  strip / lower      cleanup
  coalesce:<key>     if value is None/empty, fall back to data[<key>]
                     (used as fallback between fields, NOT as raw transform)

The `coalesce:<key>` transform is special - it operates after the main pass
to fill missing values from other extracted fields.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class ParserError(Exception):
    """Raised when a custom parser fails."""


def _apply_transforms(value: Any, transforms: str | None, context: dict[str, Any] | None = None) -> Any:
    """Apply a pipe-separated transform pipeline.

    `context` lets `coalesce:<key>` look up other fields in the same result.
    """
    if not transforms:
        return value

    result: Any = value
    for step in transforms.split("|"):
        step = step.strip()
        if not step:
            continue

        if step.startswith("regex:"):
            pattern = step[6:]
            result = re.sub(pattern, "", str(result)) if result is not None else None
        elif step.startswith("replace:"):
            parts = step[8:].split(":", 1)
            if len(parts) == 2 and result is not None:
                result = str(result).replace(parts[0], parts[1])
        elif step.startswith("prefix:"):
            prefix = step[7:]
            if result is not None and not str(result).startswith(("http://", "https://")):
                result = f"{prefix}{result}"
        elif step.startswith("coalesce:"):
            # If current value is empty, take from another field in the result
            if (result is None or result == "" or result == 0) and context is not None:
                fallback_key = step[9:]
                fallback = context.get(fallback_key)
                if fallback is not None and fallback != "":
                    result = fallback
        elif step == "float":
            try:
                result = float(str(result).strip()) if result is not None else None
            except (ValueError, TypeError):
                result = None
        elif step == "int":
            try:
                result = int(float(str(result).strip())) if result is not None else None
            except (ValueError, TypeError):
                result = None
        elif step == "strip":
            result = str(result).strip() if result is not None else None
        elif step == "lower":
            result = str(result).lower() if result is not None else None
        elif step.startswith("contains:"):
            # Returns True if the value contains the phrase, else False.
            # Useful for converting "In stock" / "Currently unavailable"
            # text into the boolean in_stock field.
            phrase = step[9:].lower()
            result = phrase in str(result).lower() if result is not None else False
        elif step.startswith("not_contains:"):
            phrase = step[13:].lower()
            result = phrase not in str(result).lower() if result is not None else True
        elif step == "price_clean":
            # Smart price-string cleanup: handles US/UK ("1,299.99"),
            # DE/FR ("1.299,99"), JPY ("¥4,999"), Nordic ("4 999,00"), etc.
            #
            # Heuristics:
            # - If both `.` and `,` appear: the rightmost is the decimal,
            #   the other is a thousands separator.
            # - If only one separator appears: it's a thousands separator
            #   when followed by exactly 3 digits AND preceded by 1-3
            #   digits (the typical 1,234 / 1.234 form). Otherwise it's
            #   the decimal.
            # This catches: ¥4,999 (thousands), $99.99 (decimal),
            # €1.299,99 (period thousands + comma decimal), £82.99 (decimal).
            if result is not None:
                s = re.sub(r"[^\d.,]", "", str(result))
                last_comma = s.rfind(",")
                last_period = s.rfind(".")
                if last_comma >= 0 and last_period >= 0:
                    # Both present: the rightmost is the decimal.
                    if last_comma > last_period:
                        s = s.replace(".", "").replace(",", ".")
                    else:
                        s = s.replace(",", "")
                elif last_comma >= 0:
                    # Only comma. Treat as thousands separator IF followed
                    # by exactly 3 digits (rest of the string after the
                    # last comma is 3 digits and no more separators).
                    after = s[last_comma + 1 :]
                    if len(after) == 3 and after.isdigit() and s.count(",") <= 2:
                        s = s.replace(",", "")
                    else:
                        s = s.replace(",", ".")
                elif last_period >= 0:
                    # Only period. Same idea.
                    after = s[last_period + 1 :]
                    if len(after) == 3 and after.isdigit() and s.count(".") <= 2:
                        s = s.replace(".", "")
                    # else: leave the period as decimal
                try:
                    result = float(s) if s else None
                except ValueError:
                    result = None
        else:
            _LOGGER.warning("Unknown transform step: %s", step)

    return result


def _walk_dotted(data: Any, dotted: str) -> Any:
    """Walk a dotted/indexed path through a nested structure.

    Supports `key.0.subkey` for lists. Returns None if any step misses.
    """
    value = data
    for part in dotted.split("."):
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return value


def _apply_css(html: str, selectors: dict[str, str], transforms: dict[str, str]) -> dict[str, Any]:
    """Extract fields using CSS selectors.

    On failure for a required field, the error message includes the page's
    <title> tag and a small snippet so the log shows whether the server
    sent us a CAPTCHA / robot-check page instead of the real product.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, Any] = {}

    for field, selector in selectors.items():
        if not selector:
            continue
        attr = None
        if "@" in selector:
            selector, attr = selector.rsplit("@", 1)

        element = soup.select_one(selector)
        if element is None:
            if field in ("title", "price"):
                # Diagnostic: include the page's <title> and a body snippet.
                # If the page is a robot-check, the title makes that obvious.
                page_title = soup.title.string if soup.title and soup.title.string else "(no title)"
                body_text = soup.get_text(" ", strip=True)[:300] if soup.body else ""
                raise ParserError(
                    f"CSS selector for required field '{field}' returned nothing: "
                    f"{selector}. Page title: {page_title!r}. Body snippet: {body_text!r}"
                )
            continue

        if attr:
            value = element.get(attr, "")
        else:
            value = element.get_text(strip=True)

        result[field] = value

    # Apply transforms with context (for coalesce)
    for field in result:
        result[field] = _apply_transforms(result[field], transforms.get(field), result)

    return result


def _apply_regex(html: str, selectors: dict[str, Any], transforms: dict[str, str]) -> dict[str, Any]:
    """Extract fields using regex patterns.

    A selector value may be:
      - a single pattern string. Supports alternation with multiple capture
        groups; returns the first non-None group. One re.search, so the
        LEFTMOST match in the HTML wins regardless of which alternative it
        is.
      - a LIST of pattern strings, tried in PRIORITY order: the first
        pattern that matches anywhere wins, and later patterns aren't tried.
        This lets a parser rank strategies by reliability rather than page
        position — e.g. prefer a formatted "$49.99" string over a raw
        numeric field that might be in cents, even when the raw field
        appears earlier in the HTML (the Amazon cents-misfire bug).
    """
    result: dict[str, Any] = {}
    for field, pattern in selectors.items():
        if not pattern:
            continue
        patterns = pattern if isinstance(pattern, list) else [pattern]
        match = None
        for pat in patterns:
            if not pat:
                continue
            match = re.search(pat, html, re.DOTALL)
            if match is not None:
                break
        if match is None:
            if field in ("title", "price"):
                # Diagnostic for required fields - include page <title>.
                soup = BeautifulSoup(html, "html.parser")
                page_title = soup.title.string if soup.title and soup.title.string else "(no title)"
                shown = patterns[0] if patterns else ""
                raise ParserError(
                    f"Regex for required field '{field}' did not match. "
                    f"Page title: {page_title!r}. Pattern (truncated): {str(shown)[:120]}..."
                )
            continue
        # Find the first non-None capture group. Fall back to group(0) if
        # the pattern has no capture groups at all.
        value = None
        try:
            for i in range(1, (match.lastindex or 0) + 1):
                g = match.group(i)
                if g is not None:
                    value = g
                    break
        except (IndexError, AttributeError):
            pass
        if value is None:
            value = match.group(0)
        # Regex captures raw HTML, so a title like "… - H&#xFA;sasmi&#xF0;jan"
        # keeps its character references. Decode them (CSS/JSON-LD parsers get
        # this for free via BeautifulSoup). Harmless on numeric fields —
        # price strings contain no entities.
        if isinstance(value, str):
            value = _html.unescape(value)
        result[field] = value

    for field in result:
        result[field] = _apply_transforms(result[field], transforms.get(field), result)
    return result


def _apply_jsonpath(html: str, selectors: dict[str, str], transforms: dict[str, str]) -> dict[str, Any]:
    """Extract from a JSON state object embedded in the HTML."""
    result: dict[str, Any] = {}

    for field, selector in selectors.items():
        if not selector or ":" not in selector:
            continue
        var_name, dotted = selector.split(":", 1)
        match = re.search(
            rf'(?:window\.{re.escape(var_name)}|id="{re.escape(var_name)}"[^>]*)>?\s*=?\s*({{.*?}})\s*(?:</script>|;)',
            html,
            re.DOTALL,
        )
        if not match:
            if field in ("title", "price"):
                raise ParserError(f"Could not find JSON state '{var_name}' for field '{field}'")
            continue

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as err:
            raise ParserError(f"Could not parse JSON state '{var_name}': {err}") from err

        value = _walk_dotted(data, dotted)
        if value is None and field in ("title", "price"):
            raise ParserError(f"JSONPath for '{field}' resolved to null: {selector}")
        result[field] = value

    for field in result:
        result[field] = _apply_transforms(result[field], transforms.get(field), result)
    return result


def _apply_raw_json(body: str, selectors: dict[str, str], transforms: dict[str, str]) -> dict[str, Any]:
    """Extract fields from a JSON response body. Selector is a dotted path.

    Example:
      selectors: {"title": "r.name", "price": "r.priceIncTax"}
      body:     {"r": {"name": "Lenovo Yoga", "priceIncTax": 269990}}
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError as err:
        raise ParserError(f"Response body is not valid JSON: {err}") from err

    result: dict[str, Any] = {}
    for field, dotted in selectors.items():
        if not dotted:
            continue
        value = _walk_dotted(data, dotted)
        if value is None and field in ("title", "price"):
            raise ParserError(f"Path for required field '{field}' resolved to null: {dotted}")
        result[field] = value

    # Apply transforms with context so coalesce works
    for field in result:
        result[field] = _apply_transforms(result[field], transforms.get(field), result)
    return result


def apply_custom_parser(body: str, parser: dict[str, Any]) -> dict[str, Any]:
    """Apply a custom parser definition to a response body, return extracted dict.

    `body` is the response text. For css/regex/jsonpath parsers it's HTML;
    for raw_json it's a JSON string.
    """
    parser_type = parser.get("type", "css")
    selectors = parser.get("selectors", {})
    transforms = parser.get("transforms", {})

    if parser_type == "css":
        data = _apply_css(body, selectors, transforms)
    elif parser_type == "regex":
        data = _apply_regex(body, selectors, transforms)
    elif parser_type == "jsonpath":
        data = _apply_jsonpath(body, selectors, transforms)
    elif parser_type == "raw_json":
        data = _apply_raw_json(body, selectors, transforms)
    else:
        raise ParserError(f"Unknown parser type: {parser_type}")

    # Required-field validation
    if "title" not in data or not data["title"]:
        raise ParserError("Custom parser did not extract a title")
    if "price" not in data or data["price"] in (None, "", 0):
        raise ParserError("Custom parser did not extract a price")

    # Coerce price to float
    if not isinstance(data["price"], (int, float)):
        try:
            data["price"] = float(str(data["price"]).replace(",", "."))
        except ValueError as err:
            raise ParserError(f"Could not coerce price to float: {data['price']}") from err

    # Optional original ("was") price for on-sale items. Unlike price it's
    # never required — a parser that doesn't extract it (or a product that
    # isn't on sale) simply leaves it absent. Coerce when present; drop it
    # rather than fail if it's junk or not above the current price (a
    # "was-price" at or below the sale price isn't a real discount).
    if data.get("original_price") not in (None, ""):
        ov = data["original_price"]
        if not isinstance(ov, (int, float)):
            try:
                ov = float(str(ov).replace(",", "."))
            except ValueError:
                ov = None
        if ov is not None and ov > float(data["price"]):
            data["original_price"] = ov
        else:
            data.pop("original_price", None)

    # Optional sanity bound: parsers can declare a min_price (and/or
    # max_price) to reject obviously-wrong matches. When the regex
    # pattern picks up a sponsored-ad price or a per-unit field
    # instead of the real product price (Amazon is the canonical
    # offender), the extracted value will be far outside the
    # expected range. Raising ParserError here lets the existing AI
    # fallback path in extract_product() take over, instead of
    # committing the bad value to history.
    #
    # No bound is enforced unless the parser config explicitly
    # opts in. This keeps existing parsers (Tölvutek, Komplett, etc.)
    # behaving identically.
    min_price = parser.get("min_price")
    if min_price is not None:
        try:
            min_price_f = float(min_price)
        except (TypeError, ValueError):
            min_price_f = None
        if min_price_f is not None and data["price"] < min_price_f:
            raise ParserError(
                f"Extracted price {data['price']} is below min_price "
                f"{min_price_f} — likely a regex misfire"
            )

    max_price = parser.get("max_price")
    if max_price is not None:
        try:
            max_price_f = float(max_price)
        except (TypeError, ValueError):
            max_price_f = None
        if max_price_f is not None and data["price"] > max_price_f:
            raise ParserError(
                f"Extracted price {data['price']} is above max_price "
                f"{max_price_f} — likely a regex misfire"
            )

    # Coerce stock_count to int if present
    if data.get("stock_count") is not None and not isinstance(data["stock_count"], int):
        try:
            data["stock_count"] = int(float(str(data["stock_count"])))
        except (ValueError, TypeError):
            data["stock_count"] = None

    # Coerce in_stock to a real bool. Custom parsers may return strings
    # (e.g. "in stock") that the `contains:` transform converts to bool;
    # but if a parser returns a raw string, treat truthy strings as True.
    if "in_stock" in data and data["in_stock"] is not None:
        v = data["in_stock"]
        if isinstance(v, str):
            v_lower = v.strip().lower()
            # Common "out" markers for safety
            if any(m in v_lower for m in ("out of stock", "currently unavailable",
                                          "not available", "sold out", "ekki til")):
                data["in_stock"] = False
            elif v_lower in ("", "false", "0", "no"):
                data["in_stock"] = False
            else:
                data["in_stock"] = True
        else:
            data["in_stock"] = bool(v)

    # If stock_count is set but in_stock isn't, derive it
    if "in_stock" not in data or data["in_stock"] is None:
        if data.get("stock_count") is not None:
            data["in_stock"] = data["stock_count"] > 0

    # Sensible defaults
    data.setdefault("currency", parser.get("default_currency", ""))
    data.setdefault("in_stock", True)
    data.setdefault("image_url", None)
    data.setdefault("sku", None)
    data.setdefault("retailer", parser.get("default_retailer"))

    return data
