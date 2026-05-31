"""Tracked listing dataclass for the v2 product-with-N-listings data model.

This module defines the schema only. It is not yet wired into the
coordinator — that's a later step. Living here standalone means we
can unit-test the type and its serialization without touching the
runtime.

Naming convention:
- `Product` (top-level v2 concept) lives on the ConfigEntry: its
  options dict holds product-level config (target_price, scan_interval,
  alternatives_region, paused, etc.). The product's `listings` field
  is a list of `TrackedListing.to_dict()` outputs.
- `TrackedListing` is one URL being tracked under that product. Each
  listing has its own price history, extraction config, and sensor.

The split between per-product and per-listing config follows the
decisions in docs/search-first-refactor.md:
- Per-product: target_price + currency, scan_interval (default),
  alternatives_region, user_region, paused, force_discontinued
- Per-listing: url, retailer, currency, custom_parser, cookies,
  min_price, max_price, scan_interval_override, listing_paused,
  price_history, last_check, lkg/discontinued state, alternatives,
  ships_to_user_region

A listing's `id` is a stable identifier (ULID-style) generated at
creation time. It's used as the sensor entity_id suffix and as the
key for per-listing state lookups. It is NOT the URL because URLs
can change (retailer redirects, slug updates) but the listing
identity stays.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrackedListing:
    """One URL being tracked under a Product.

    The complete state for a single retailer's listing of a product:
    extraction config (URL, parser, cookies, sanity bounds), runtime
    state (price history, last check, last-known-good, discontinued
    status), and presentation metadata (retailer name, currency,
    ships-to-user-region flag).

    All fields except `id`, `url`, and `retailer` have sensible
    defaults so a fresh listing can be constructed minimally during
    migration or add-from-search flows.
    """

    # === Identity ===

    # Stable identifier for this listing. Generated at creation time
    # (ULID format recommended). Used as sensor entity_id suffix and
    # for lookups in the coordinator's per-listing state map. Does
    # NOT change when the URL changes.
    id: str
    # The URL being polled. CAN change over time (retailer redirects,
    # slug updates) without breaking listing identity.
    url: str
    # Display name for the retailer (e.g. "Komplett", "Newegg",
    # "Tölvutek"). Surfaced in panel rows and sensor friendly names.
    # Derived from the URL's hostname during migration / add.
    retailer: str

    # === Per-listing extraction config ===

    # Currency code as declared by this listing (3-letter ISO, but
    # tolerant of retailer quirks like "kr" → caller should normalize).
    # Empty string is the "unknown, infer from extraction" default.
    currency: str = ""
    # Custom parser config blob (see parsers.py apply_custom_parser).
    # None means "use AI fallback or JSON-LD".
    custom_parser: dict[str, Any] | None = None
    # Pinned product-variant option labels for sites that embed all
    # variant prices in the page (Wix). e.g. ["1xIR Remote", "5-48V"].
    # When set, the extractor reads THAT combo's price instead of the
    # page's default offer. Empty list = track the default.
    variant_options: list[str] = field(default_factory=list)
    # Cookies to send with the request. List of {name, value, domain}
    # dicts in the same shape parsers.py expects.
    request_cookies: list[dict[str, Any]] = field(default_factory=list)
    # Sanity bounds for extracted price. Existing behavior: extracted
    # value below min or above max raises ParserError, triggering AI
    # fallback. None means no bound.
    min_price: float | None = None
    max_price: float | None = None
    # Per-listing override of the product's scan_interval (in seconds).
    # None = use product default. Used to back off hostile retailers
    # without slowing down sibling listings.
    scan_interval_override: int | None = None
    # Per-listing pause. When the product is paused, this is ignored
    # (product pause OR-overrides). When the product is unpaused but
    # this listing is paused, the listing doesn't poll. Useful for
    # CAPTCHA'd retailers you want to keep around but not grind on.
    paused: bool = False

    # === Runtime state ===

    # Price observation history. Each entry:
    #   {"ts": iso-8601, "price": float, "currency": str, "in_stock": bool}
    # Sorted ascending by ts. Coordinator appends on each successful
    # observation; never trimmed unless reset_history is called.
    price_history: list[dict[str, Any]] = field(default_factory=list)
    # Timestamp (ISO-8601) of the most recent poll attempt, regardless
    # of whether it succeeded. Used for "last checked" UI display.
    last_check: str | None = None
    # Hash of the most recently successfully-fetched HTML, used for
    # change detection skip-extraction-when-page-unchanged optimization.
    last_hash: str | None = None
    # Lifetime cumulative cost in USD of AI calls made for this listing.
    # Carried forward across migrations.
    lifetime_cost_usd: float = 0.0

    # === Last-known-good (used when listing goes discontinued) ===

    # When the listing's URL returns 404/discontinued, we preserve the
    # last successful observation for UI display.
    lkg_price: float | None = None
    lkg_currency: str | None = None
    lkg_observed_at: str | None = None
    discontinued_title: str | None = None
    # Whether this listing is currently flagged as discontinued.
    discontinued: bool = False
    discontinued_at: str | None = None
    discontinued_reason: str | None = None

    # === Region/shipping (set by region heuristic) ===

    # Whether this retailer ships to the user's region. None = unknown
    # / no signal. True = heuristic confirmed yes. False = heuristic
    # confirmed no. Set during alternatives-search; persists on the
    # listing once known.
    ships_to_user_region: bool | None = None

    # === Convenience ===

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the per-product options blob.

        Returned shape is JSON-safe (no datetime / Decimal / custom
        objects). All optional fields included so the round-trip
        through from_dict() is lossless.
        """
        return {
            "id": self.id,
            "url": self.url,
            "retailer": self.retailer,
            "currency": self.currency,
            "custom_parser": self.custom_parser,
            "variant_options": list(self.variant_options),
            "request_cookies": list(self.request_cookies),
            "min_price": self.min_price,
            "max_price": self.max_price,
            "scan_interval_override": self.scan_interval_override,
            "paused": self.paused,
            "price_history": list(self.price_history),
            "last_check": self.last_check,
            "last_hash": self.last_hash,
            "lifetime_cost_usd": self.lifetime_cost_usd,
            "lkg_price": self.lkg_price,
            "lkg_currency": self.lkg_currency,
            "lkg_observed_at": self.lkg_observed_at,
            "discontinued_title": self.discontinued_title,
            "discontinued": self.discontinued,
            "discontinued_at": self.discontinued_at,
            "discontinued_reason": self.discontinued_reason,
            "ships_to_user_region": self.ships_to_user_region,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrackedListing:
        """Deserialize from per-product options blob.

        Defensive against missing keys (older listings might lack
        newer fields). Required fields (id/url/retailer) raise
        KeyError if missing — the caller should handle / re-migrate.
        """
        return cls(
            id=str(data["id"]),
            url=str(data["url"]),
            retailer=str(data["retailer"]),
            currency=str(data.get("currency", "") or ""),
            custom_parser=data.get("custom_parser"),
            variant_options=[str(v) for v in (data.get("variant_options") or [])],
            request_cookies=list(data.get("request_cookies") or []),
            min_price=_coerce_optional_float(data.get("min_price")),
            max_price=_coerce_optional_float(data.get("max_price")),
            scan_interval_override=_coerce_optional_int(
                data.get("scan_interval_override")
            ),
            paused=bool(data.get("paused", False)),
            price_history=list(data.get("price_history") or []),
            last_check=data.get("last_check"),
            last_hash=data.get("last_hash"),
            lifetime_cost_usd=float(data.get("lifetime_cost_usd") or 0.0),
            lkg_price=_coerce_optional_float(data.get("lkg_price")),
            lkg_currency=data.get("lkg_currency"),
            lkg_observed_at=data.get("lkg_observed_at"),
            discontinued_title=data.get("discontinued_title"),
            discontinued=bool(data.get("discontinued", False)),
            discontinued_at=data.get("discontinued_at"),
            discontinued_reason=data.get("discontinued_reason"),
            ships_to_user_region=_coerce_optional_bool(
                data.get("ships_to_user_region")
            ),
        )


def _coerce_optional_float(value: Any) -> float | None:
    """Tolerant float coercion that preserves None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_int(value: Any) -> int | None:
    """Tolerant int coercion that preserves None."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_bool(value: Any) -> bool | None:
    """Tolerant bool coercion that preserves None (vs False)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return bool(value)
