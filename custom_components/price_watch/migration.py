"""v1 → v2 migration helpers.

This module contains the logic to convert a v1 ConfigEntry (one URL,
single price history, alternatives as attributes) into a v2 ConfigEntry
(one product, one TrackedListing wrapping the existing URL + history).

It is NOT yet wired into the integration. The wire-in step (bumping
storage version, registering async_migrate_entry, etc.) is intentionally
separated so the migration logic can be unit-tested offline against
copies of real production .json files before any HA restart sees it.

Two transforms happen during migration:

1. **Entry data transform** — `migrate_entry_v1_to_v2(entry_data,
   entry_options)` reads the old `data` and `options` dicts and
   returns a NEW (data, options) tuple in v2 shape.

2. **Storage transform** — `migrate_storage_v1_to_v2(storage_data,
   listing_id)` reads the old per-entry storage blob (history,
   lowest, highest, last_result, alternatives, etc.) and rewrites
   it nested under a per-listing key.

The migration is pure: no HA dependencies, no I/O. Callers provide
the input dicts and receive output dicts. This makes the logic easy
to test and the side effects (writing storage, updating registry)
happen at the call site.

Migration is idempotent on the entry-data side (running it twice on
a v2 entry returns the same v2 shape). On the storage side it
detects v2 shape and returns it unchanged.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


# Storage version constants. v1 is the current production schema;
# v2 is the new shape we migrate to.
STORAGE_VERSION_V1 = 1
STORAGE_VERSION_V2 = 2


def migrate_entry_v1_to_v2(
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
    *,
    listing_id: str,
    entry_title: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Transform a v1 entry's data + options into v2 shape.

    v1 shape:
        data:    {url, title, ...settings entry keys, ...}
        options: {custom_parser, request_cookies, target_price,
                  scan_interval, paused, ai_provider, model, ...,
                  daily_alternatives, user_region, alternatives_region,
                  ...}

    v2 shape:
        data:    {entry_type: "product", ...minimal metadata}
        options: {
            product: {
                short_name, query, target_price, target_price_currency,
                scan_interval, paused, force_discontinued,
                daily_alternatives, alternatives_region, max_alternatives,
                user_region, ai_provider_override, ...,
            },
            listings: [{id, url, retailer, currency, custom_parser,
                        request_cookies, min_price, max_price, ...}]
        }

    The single existing URL becomes one listing under the product.
    The caller passes `listing_id` (a freshly-generated ULID) so this
    function stays pure.

    Idempotency: if the input already looks v2 (has "listings" key
    in options), returns it unchanged.
    """
    # Idempotency: detect already-migrated entries
    if "listings" in entry_options and isinstance(entry_options["listings"], list):
        return dict(entry_data), dict(entry_options)

    # --- Extract listing-level fields from v1 options ---
    url = entry_data.get("url") or entry_data.get("product_url") or ""
    retailer_default = _derive_retailer_from_url(url)

    # Parse custom_parser from string if needed; lift min_price/max_price
    # out to listing-level fields. v1 stored custom_parser as a JSON
    # string in entry.options; v2 stores it as a parsed dict on the
    # listing.
    raw_parser = entry_options.get("custom_parser")
    parsed_parser: dict[str, Any] | None = None
    lifted_min: float | None = None
    lifted_max: float | None = None
    lifted_cookies: list[dict[str, Any]] = []
    if raw_parser is not None:
        if isinstance(raw_parser, str):
            try:
                import json as _json
                parsed_parser = _json.loads(raw_parser)
            except (ValueError, TypeError):
                # Couldn't parse — preserve raw string under a fallback
                # key so it isn't lost; coordinator can re-parse later.
                parsed_parser = {"_raw_unparseable": raw_parser}
        elif isinstance(raw_parser, dict):
            parsed_parser = dict(raw_parser)
        if isinstance(parsed_parser, dict):
            # Mirror sanity bounds to listing-level fields. Phase 1
            # leaves them in the parser blob too (parsers.py reads
            # them from there in the v1 code path). When the
            # coordinator is fully v2-aware (Phase 3+), the parser
            # blob can be cleaned of these.
            try:
                if parsed_parser.get("min_price") is not None:
                    lifted_min = float(parsed_parser.get("min_price"))
            except (TypeError, ValueError):
                pass
            try:
                if parsed_parser.get("max_price") is not None:
                    lifted_max = float(parsed_parser.get("max_price"))
            except (TypeError, ValueError):
                pass
            # Mirror cookies to listing-level. Same reasoning — the
            # raw cookie string is still inside the parser blob for
            # v1 code paths; v2 code can find it on the listing too.
            cookie_blob = parsed_parser.get("request_cookies")
            if cookie_blob:
                lifted_cookies = [{"_raw": cookie_blob}]

    listing_dict = {
        "id": listing_id,
        "url": url,
        "retailer": retailer_default,
        "currency": "",  # will be filled at first successful poll
        "custom_parser": parsed_parser,
        "request_cookies": lifted_cookies or entry_options.get("request_cookies") or [],
        # Lifted from inside the parser blob (see above).
        "min_price": lifted_min,
        "max_price": lifted_max,
        "scan_interval_override": None,
        "paused": False,  # per-listing pause is new; defaults False
        # Runtime state migrates from the storage blob, NOT from
        # entry options. Leave empty here; migrate_storage_v1_to_v2
        # fills it in.
        "price_history": [],
        "last_check": None,
        "last_hash": None,
        "lifetime_cost_usd": 0.0,
        "lkg_price": None,
        "lkg_currency": None,
        "lkg_observed_at": None,
        "discontinued_title": None,
        "discontinued": False,
        "discontinued_at": None,
        "discontinued_reason": None,
        "ships_to_user_region": None,
    }

    # --- Extract product-level fields ---
    # Most existing per-product config lives in entry.options today;
    # we move it under a `product` namespace in v2 and add a few new
    # fields (short_name, target_price_currency).
    # Title preference: entry_title (the ConfigEntry's .title field,
    # which HA shows in the integrations UI) > entry_data.title (a
    # snapshot some integrations stash). v1 entries put nothing in
    # data.title, so we rely on entry_title.
    title = entry_title or entry_data.get("title", "")
    short_name = _derive_short_name(retailer_default, title)

    product_dict = {
        "short_name": short_name,
        "query": "",  # never had one in v1; user can set later
        # Target price: lift from v1 options unchanged. Currency
        # defaults to whatever's currently being tracked; coordinator
        # will infer at first poll if blank.
        "target_price": entry_options.get("target_price"),
        "target_price_currency": "",  # set on next poll
        # Polling cadence: lift unchanged
        "scan_interval": entry_options.get("scan_interval"),
        "paused": bool(entry_options.get("paused", False)),
        "force_discontinued": bool(entry_options.get("force_discontinued", False)),
        # Alternatives config
        "daily_alternatives": bool(entry_options.get("daily_alternatives", False)),
        "alternatives_region": entry_options.get("alternatives_region", "worldwide"),
        "max_alternatives": entry_options.get("max_alternatives"),
        "user_region": entry_options.get("user_region", ""),
        # AI provider overrides (rare but possible)
        "ai_provider": entry_options.get("ai_provider"),
        "model": entry_options.get("model"),
        "base_url": entry_options.get("base_url"),
        "api_key": entry_options.get("api_key"),
    }
    # Strip out keys whose value is None — keep options compact
    product_dict = {k: v for k, v in product_dict.items() if v is not None}

    # --- Assemble v2 entry ---
    new_data = {
        # Keep title in data for HA's entry listing UI
        "title": title,
        # Marker so future code can identify v2 entries cleanly
        "v2_schema": True,
        # Marker so coordinator can distinguish product entries from
        # the settings entry without inspecting structure
        "entry_type": "product",
    }
    # Preserve original v1 data keys we didn't migrate (e.g. anything
    # custom an integration update added). EXPLICITLY DROP api_key
    # and model — these were stale "what was in settings when this
    # product was created" snapshots that coordinator.py's precedence
    # fix (tonight) made obsolete. They also held a leaked Anthropic
    # API key that propagated through tonight's earlier cleanup.
    _DROP_KEYS = frozenset({"api_key", "model", "entry_type"})
    for k, v in entry_data.items():
        if k in _DROP_KEYS:
            continue
        if k not in new_data:
            new_data[k] = v

    # PHASE 1 COMPATIBILITY: preserve all of v1's entry_options at the
    # top level. The new v2 namespaces (product, listings) live
    # ALONGSIDE the legacy keys, not replacing them. This means the
    # coordinator's existing entry.options.get(CONF_PAUSED) and friends
    # keep working post-migration without coordinator code changes.
    # The duplication is intentional and gets cleaned up in Phase 3
    # when config_flow is refactored to produce v2-native shape.
    new_options = dict(entry_options)
    new_options["product"] = product_dict
    new_options["listings"] = [listing_dict]
    return new_data, new_options


def migrate_storage_v1_to_v2(
    storage_data: dict[str, Any],
    *,
    listing_id: str,
) -> dict[str, Any]:
    """Transform a v1 per-entry storage blob into v2 shape.

    v1 storage shape:
        {
            "history": [{ts, price, currency, in_stock}, ...],
            "lowest": {...} | None,
            "highest": {...} | None,
            "last_hash": str,
            "last_result": {...},
            "lifetime_cost_usd": float,
            "alternatives": [...],
            "alternatives_fetched_at": str,
            "alternatives_error": str | None,
            "discontinued": bool,
            "discontinued_at": str,
            "discontinued_reason": str,
            "lkg_price": float,
            "lkg_currency": str,
            "lkg_observed_at": str,
            "discontinued_title": str,
        }

    v2 storage shape:
        {
            "listings": {
                <listing_id>: {
                    "price_history": [...],
                    "last_hash": str,
                    "lifetime_cost_usd": float,
                    "lkg_*": ...,
                    "discontinued*": ...,
                }
            },
            "product": {
                "alternatives": [...],         # shared across listings
                "alternatives_fetched_at": str,
                "alternatives_error": str | None,
            }
        }

    The migration moves per-URL state into the listing namespace and
    keeps product-wide state (alternatives) at the top.

    Idempotency: if the input already has "listings" + "product"
    top-level keys, returns it unchanged.
    """
    # Idempotency: detect already-migrated storage
    if "listings" in storage_data and "product" in storage_data:
        return dict(storage_data)

    # The full set of v1 per-listing keys we know about
    listing_state = {
        "price_history": list(storage_data.get("history") or []),
        "last_hash": storage_data.get("last_hash"),
        "last_check": None,  # v1 didn't store this; reset
        "lifetime_cost_usd": float(storage_data.get("lifetime_cost_usd") or 0.0),
        "lkg_price": storage_data.get("lkg_price"),
        "lkg_currency": storage_data.get("lkg_currency"),
        "lkg_observed_at": storage_data.get("lkg_observed_at"),
        "discontinued_title": storage_data.get("discontinued_title"),
        "discontinued": bool(storage_data.get("discontinued", False)),
        "discontinued_at": storage_data.get("discontinued_at"),
        "discontinued_reason": storage_data.get("discontinued_reason"),
        # lowest/highest are derived from history at runtime; v2
        # coordinator can recompute. Preserve here for now in case
        # caller wants them.
        "lowest": storage_data.get("lowest"),
        "highest": storage_data.get("highest"),
        "last_result": storage_data.get("last_result"),
    }

    # Product-level state (shared across listings of the same product)
    product_state = {
        "alternatives": list(storage_data.get("alternatives") or []),
        "alternatives_fetched_at": storage_data.get("alternatives_fetched_at"),
        "alternatives_error": storage_data.get("alternatives_error"),
    }

    return {
        "listings": {listing_id: listing_state},
        "product": product_state,
    }


# === Helpers ===

# Common retailer hostname → display name mapping. Falls back to
# capitalizing the second-level domain.
_RETAILER_DISPLAY: dict[str, str] = {
    "amazon.com": "Amazon",
    "amazon.ca": "Amazon CA",
    "amazon.co.uk": "Amazon UK",
    "amazon.de": "Amazon DE",
    "newegg.com": "Newegg",
    "bestbuy.com": "Best Buy",
    "microcenter.com": "MicroCenter",
    "komplett.no": "Komplett",
    "komplett.se": "Komplett SE",
    "komplett.dk": "Komplett DK",
    "elkjop.no": "Elkjøp",
    "elgiganten.se": "Elgiganten",
    "elgiganten.dk": "Elgiganten DK",
    "proshop.no": "Proshop",
    "proshop.dk": "Proshop DK",
    "proshop.se": "Proshop SE",
    "netonnet.no": "NetOnNet",
    "netonnet.se": "NetOnNet SE",
    "power.no": "Power",
    "power.se": "Power SE",
    "tolvutek.is": "Tölvutek",
    "advania.is": "Advania",
    "pangoly.com": "Pangoly",
    "gigabyte.com": "GIGABYTE",
    "corsair.com": "Corsair",
    "aliexpress.com": "AliExpress",
    "ebay.com": "eBay",
}


def _derive_retailer_from_url(url: str) -> str:
    """Best-effort retailer display name from a URL hostname."""
    if not url:
        return ""
    try:
        host = (urlparse(url).hostname or "").lower()
    except (ValueError, AttributeError):
        return ""
    if not host:
        return ""
    # Strip leading "www."
    if host.startswith("www."):
        host = host[4:]
    # Check exact / suffix match in mapping
    if host in _RETAILER_DISPLAY:
        return _RETAILER_DISPLAY[host]
    for suffix, name in _RETAILER_DISPLAY.items():
        if host.endswith("." + suffix):
            return name
    # Fallback: second-level domain, capitalized
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return host.capitalize()


# Regexes used to clean noisy product titles into something usable as
# a short_name. Applied in order.
# 1. Strip "at <retailer>.com" or "at <retailer>" trailers.
# 2. Strip " | <retailer>" trailers (common SEO pattern).
# 3. Strip parenthesized SKUs at the end of the title like
#    "(CMP32GX5M2B6000Z30)". They're identifying but noise for a name.
# 4. Strip parenthesized capacity duplications like "(2x16GB)" — the
#    important capacity is usually already mentioned outside parens.
_TITLE_NOISE_TRAILER = re.compile(
    r"\s+at\s+[\w.]+\.com\b|\s+at\s+[\w.]+\s*$|\s*\|\s*[\w.\s]+\s*$",
    re.IGNORECASE,
)
_TITLE_NOISE_PAREN_SKU = re.compile(r"\s*\([A-Z0-9]{6,}\)\s*$")
_TITLE_NOISE_PAREN_GENERIC = re.compile(r"\s*\([^)]+\)\s*$")


def _derive_short_name(retailer: str, title: str) -> str:
    """Pick a default short name for the migrated product.

    Per the design doc Q3 decision (refined): short name defaults
    to the PRODUCT TITLE (cleaned and trimmed). Long retailer-SEO
    titles get noise stripped (trailing "at Amazon.com", trailing
    "(SKU123)", trailing " | Retailer", etc.) and then truncated
    to ~40 chars at a word boundary.

    Falls back to retailer name if title is empty/missing, and
    finally to literal "Product" if both are empty.

    The user can override in the options flow after migration.
    """
    if title:
        cleaned = title.strip()
        # Apply trailer-stripping passes; each pass may expose another
        # one beneath it (e.g. "Foo (SKU) | Retailer" → "Foo (SKU)" →
        # "Foo"). Loop until no further reduction.
        for _ in range(4):
            before = cleaned
            cleaned = _TITLE_NOISE_TRAILER.sub("", cleaned).strip()
            cleaned = _TITLE_NOISE_PAREN_SKU.sub("", cleaned).strip()
            if cleaned == before:
                break
        # If the title is still very long (>50 chars), try stripping
        # one trailing parenthesized clause (e.g. "(2x16GB)") to
        # tighten it further. Only one pass — don't strip mid-title
        # parens which often carry essential info.
        if len(cleaned) > 50:
            shorter = _TITLE_NOISE_PAREN_GENERIC.sub("", cleaned).strip()
            if 0 < len(shorter) < len(cleaned):
                cleaned = shorter
        # Truncate to 40 chars at a word boundary if still too long
        if len(cleaned) > 40:
            cut = cleaned[:40].rsplit(" ", 1)[0]
            cleaned = (cut or cleaned[:40]).rstrip(",-:;|")
        if cleaned:
            return cleaned
    if retailer:
        return retailer
    return "Product"
