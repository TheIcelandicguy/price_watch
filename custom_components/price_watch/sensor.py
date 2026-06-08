"""Sensor platform for Price Watch.

Phase 2.3: per-listing sensors. Each product has N listings; each listing
gets its own price/lowest/highest/target_diff/stock_count sensors. The
primary listing keeps legacy unique_ids ({entry}_{key}) for back-compat
with existing entity registry entries and the panel; secondary listings
use extended unique_ids ({entry}_{listing}_{key}) which the panel's
key-splitting logic gracefully ignores (so secondary listings are
invisible in the current panel — Phase 4 will extend the panel UI).

price_local is only created for the primary listing — FX conversion is
product-level in Phase 2 (see coordinator._update_price_local).
"""

from __future__ import annotations

import statistics
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import ENTRY_TYPE_PRODUCT
from .cookies import to_header_str as _cookies_to_header_str
from .const import (
    ATTR_ALTERNATIVES,
    ATTR_ALTERNATIVES_ERROR,
    ATTR_ALTERNATIVES_FETCHED_AT,
    ATTR_CURRENCY,
    ATTR_IMAGE_URL,
    ATTR_LAST_CHECK,
    ATTR_PRICE_HISTORY,
    ATTR_PRODUCT_URL,
    ATTR_RETAILER,
    ATTR_SKU,
    ATTR_STOCK_COUNT,
    ATTR_TITLE,
    DOMAIN,
)
from .coordinator import PriceWatchCoordinator
from .search.region_heuristic import evaluate_shipping

# Monetary sensors all behave the same (price/lowest/highest/target_diff/price_local)
MONETARY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="price",
        translation_key="price",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        icon="mdi:tag",
    ),
    SensorEntityDescription(
        key="lowest",
        translation_key="lowest",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        icon="mdi:arrow-down-bold",
    ),
    SensorEntityDescription(
        key="highest",
        translation_key="highest",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        icon="mdi:arrow-up-bold",
    ),
    SensorEntityDescription(
        key="target_diff",
        translation_key="target_diff",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        icon="mdi:bullseye-arrow",
    ),
    SensorEntityDescription(
        key="price_local",
        translation_key="price_local",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        icon="mdi:cash-multiple",
    ),
)

STOCK_COUNT_DESCRIPTION = SensorEntityDescription(
    key="stock_count",
    translation_key="stock_count",
    icon="mdi:numeric",
    native_unit_of_measurement="units",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a product entry.

    Phase 2.3: iterates over coordinator.listing_ids. For the primary
    listing, creates the full set (5 monetary + 1 stock count) with
    legacy unique_ids. For secondary listings, creates 4 monetary
    (no price_local) + 1 stock count with listing-prefixed unique_ids.
    """
    if entry.data.get("entry_type") != ENTRY_TYPE_PRODUCT:
        return

    coordinator: PriceWatchCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    primary_id = coordinator.primary_listing_id

    for listing_id in coordinator.listing_ids:
        is_primary = listing_id == primary_id
        for description in MONETARY_DESCRIPTIONS:
            # price_local only makes sense for the primary listing in
            # Phase 2 (FX conversion is product-level, see coordinator
            # ._update_price_local). Skip on secondary listings to
            # avoid creating sensors that always report None.
            if description.key == "price_local" and not is_primary:
                continue
            entities.append(
                PriceWatchMonetarySensor(coordinator, description, listing_id)
            )
        entities.append(
            PriceWatchStockCountSensor(coordinator, STOCK_COUNT_DESCRIPTION, listing_id)
        )

    async_add_entities(entities)


class _BasePriceWatchSensor(CoordinatorEntity[PriceWatchCoordinator], SensorEntity):
    """Common base for Price Watch sensors.

    Each sensor is bound to a specific listing_id. For the primary
    listing, unique_id retains the legacy {entry_id}_{key} format so
    existing entity registry entries match. For secondary listings,
    unique_id is {entry_id}_{listing_id}_{key}.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PriceWatchCoordinator,
        description: SensorEntityDescription,
        listing_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._listing_id = listing_id

        entry_id = coordinator.entry.entry_id
        if listing_id == coordinator.primary_listing_id:
            # Legacy form — matches existing entity registry entries
            self._attr_unique_id = f"{entry_id}_{description.key}"
        else:
            # Per-listing form for secondary listings (no existing
            # entities to preserve)
            self._attr_unique_id = (
                f"{entry_id}_{listing_id}_{description.key}"
            )
            # Prefix the entity name with the retailer for clarity
            # in the entity list. e.g. "Newegg Price" alongside the
            # primary listing's plain "Price". Only set when we can
            # resolve a retailer name; otherwise fall back to the
            # translation_key default.
            config = coordinator.get_listing_config(listing_id) or {}
            retailer = config.get("retailer")
            if retailer:
                # Use translation_key-style name with the retailer
                # appended. The translation_key handles the base
                # ("Price", "Lowest", etc.); we just prepend retailer.
                self._attr_name = f"{retailer} {self._description_label(description.key)}"

    @staticmethod
    def _description_label(key: str) -> str:
        """Human-readable label for a description key.

        Used to construct entity names for secondary listings without
        going through the translation_key machinery (which would
        require translation files for any per-listing variant). The
        labels mirror what the translation files would produce.
        """
        return {
            "price": "Price",
            "lowest": "Lowest seen",
            "highest": "Highest seen",
            "target_diff": "Target diff",
            "price_local": "Price (local)",
            "stock_count": "Stock count",
        }.get(key, key.replace("_", " ").title())

    @property
    def device_info(self) -> dict[str, Any]:
        return self.coordinator.device_info

    # Convenience accessors — sensors below use these instead of
    # talking to the coordinator's primary-listing-fronted properties.
    @property
    def _result(self):
        """Latest ExtractionResult for THIS sensor's listing (or None)."""
        return self.coordinator.get_listing_result(self._listing_id)

    @property
    def _listing_state(self) -> dict[str, Any]:
        """Runtime state dict for THIS sensor's listing (or empty dict)."""
        return self.coordinator.get_listing_state(self._listing_id) or {}


class PriceWatchMonetarySensor(_BasePriceWatchSensor):
    """Sensor for any monetary value (price, lowest, highest, target_diff, price_local)."""

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Currency for this sensor.

        For price_local: the user's home currency (set in settings).
        For everything else: the listing's source currency.
        """
        result = self._result
        if result is None:
            return None
        if self.entity_description.key == "price_local":
            return self.coordinator.home_currency or None
        return result.currency or None

    @property
    def native_value(self) -> float | None:
        """Return the value for this sensor."""
        result = self._result
        state = self._listing_state
        key = self.entity_description.key

        if key == "price":
            if result is None:
                return None
            # For a discontinued listing, the live page returns 0 — but
            # the user's expectation is "show me what it cost when it
            # was still sold." Surface the LKG price for THIS listing;
            # the discontinued binary sensor and attributes tell the
            # rest of the story.
            if result.discontinued:
                return state.get("lkg_price")
            return result.price
        if key == "lowest":
            return state.get("lowest")
        if key == "highest":
            return state.get("highest")
        if key == "target_diff":
            target = self.coordinator.target_price
            if result is None or target is None:
                return None
            # Don't compute target_diff against a discontinued listing.
            if result.discontinued:
                return None
            return round(result.price - target, 2)
        if key == "price_local":
            # price_local sensor only exists on the primary listing;
            # the value is product-level (computed once per tick from
            # the primary listing's result).
            return self.coordinator.price_local
        return None

    @property
    def available(self) -> bool:
        """Availability per sensor kind.

        price_local: hidden until we actually have a converted value
        (avoids "unavailable" noise on products with no FX rate yet).

        price: stays available even when the coordinator's last update
        failed, AS LONG AS we have a URL to track. A product whose first
        fetch failed (free-mode page with no JSON-LD, a cookie wall, or a
        parser not configured yet) must remain available so it shows as a
        card with state "unknown" and its extra_state_attributes (URL,
        title) reach the panel — HA strips ALL attributes from an
        `unavailable` entity, which would otherwise hide the URL the ✎
        editor's "Test on live page" button needs. Once an extraction
        succeeds the state becomes the real price.
        """
        if self.entity_description.key == "price_local":
            return (
                super().available
                and self._result is not None
                and self.coordinator.price_local is not None
            )
        if self.entity_description.key == "price" and not super().available:
            config = self.coordinator.get_listing_config(self._listing_id) or {}
            return bool(config.get("url") or self.coordinator.url)
        return super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose full product context on the price sensor.

        Per-listing attributes (title, URL, retailer, history) come
        from THIS listing's result and state. Product-level fields
        (alternatives) appear only on the primary listing's price
        sensor — they're shared across the product and showing them
        on every listing would be duplicative.
        """
        if self.entity_description.key != "price":
            return None
        config = self.coordinator.get_listing_config(self._listing_id) or {}
        # Listing URL: prefer the listing config's URL; fall back to
        # the coordinator's product-level URL (primary listing).
        product_url = config.get("url") or self.coordinator.url
        # Retailer's seasonal-offers page for this listing's host (config-
        # based, so it's available even when extraction has failed).
        offer_page_url = self.coordinator.offer_page_url_for(product_url)
        result = self._result
        if result is None:
            # Extraction hasn't succeeded yet (first fetch failed: no
            # JSON-LD, a cookie/CAPTCHA wall, or a custom parser not
            # configured yet). Still surface the URL and a title so the
            # panel renders the card and the ✎ editor's "Test on live page"
            # button has a URL to act on — otherwise the user can't reach
            # the tools that would fix this very listing.
            minimal = {
                ATTR_TITLE: self.coordinator.entry.title or "",
                ATTR_PRODUCT_URL: product_url,
                ATTR_RETAILER: config.get("retailer"),
            }
            if offer_page_url:
                minimal["offer_page_url"] = offer_page_url
            return minimal
        state = self._listing_state

        attrs: dict[str, Any] = {
            ATTR_TITLE: result.title,
            ATTR_PRODUCT_URL: product_url,
            ATTR_IMAGE_URL: result.image_url,
            ATTR_RETAILER: result.retailer,
            ATTR_CURRENCY: result.currency,
            ATTR_SKU: result.sku,
            ATTR_STOCK_COUNT: result.stock_count,
            ATTR_LAST_CHECK: state.get("last_check") or self._last_check_iso(),
            ATTR_PRICE_HISTORY: state.get("history") or [],
            "extraction_method": result.method,
            "lifetime_cost_usd": round(
                float(state.get("lifetime_cost_usd") or 0.0), 4
            ),
            "listing_id": self._listing_id,
            # Product-level edit context surfaced for the panel's
            # inline controls (edit target / pause). Harmless to repeat
            # on every listing's price sensor since both are
            # product-scoped; the panel reads them off the primary.
            "target_price": self.coordinator.target_price,
            "paused": self.coordinator.paused,
            # Whether anti-bot cookies are stored for this listing. Only the
            # boolean is exposed — the cookie value is a secret and never
            # surfaced to the frontend. Lets the panel show a "cookies set"
            # hint without round-tripping the value.
            "has_cookies": bool(
                (parser := self.coordinator.effective_custom_parser(self._listing_id))
                and _cookies_to_header_str(parser.get("request_cookies"))
            ),
        }

        # On-sale / discount signals, derived from result.original_price (the
        # struck-through "was" price). `price` is what you pay now; when the
        # original is higher, the item is on sale. The panel shows a "−N%"
        # badge from these.
        if result.original_price and result.original_price > result.price:
            attrs["on_sale"] = True
            attrs["original_price"] = result.original_price
            attrs["discount_percent"] = round(
                (1 - result.price / result.original_price) * 100
            )
        else:
            attrs["on_sale"] = False

        # Per-physical-store stock (Húsa-style). Surface the full list plus a
        # convenience list of stores that actually have it, so the panel can
        # show "in stock at: …" without re-deriving the statuses.
        if result.store_availability:
            attrs["store_availability"] = result.store_availability
            in_stock_rows = [
                s
                for s in result.store_availability
                if s.get("status") in ("in_stock", "limited")
            ]
            attrs["available_stores"] = [s["store"] for s in in_stock_rows]
            # JYSK marks stock that's at the Reykjavík warehouse (not the
            # store itself) with a red asterisk. When every in-stock store is
            # warehouse-sourced, the item can't be picked up locally without
            # ordering it in — surface that as a single convenience flag.
            if in_stock_rows and all(
                s.get("from_warehouse") for s in in_stock_rows
            ):
                attrs["stock_from_warehouse"] = True

        # Sibling size pages (JYSK "Stærðir"). The panel renders these as
        # chips and swaps the tracked URL when the user picks another size.
        if result.size_options:
            attrs["size_options"] = result.size_options

        # Retailer product number + fuller description name (Húsa / Byko),
        # shown under the title on the card.
        if result.product_number:
            attrs["product_number"] = result.product_number
        if result.description_name:
            attrs["description_name"] = result.description_name

        # Retailer's seasonal-offers page → "Tilboð hjá <store>" link.
        if offer_page_url:
            attrs["offer_page_url"] = offer_page_url

        # "Good price?" context for the card verdict. lowest is all-time
        # (cheap, meaningful after a couple of polls); typical is the median of
        # daily closes, only once there's enough history to be meaningful.
        lowest = state.get("lowest")
        if isinstance(lowest, (int, float)):
            attrs["price_lowest_ever"] = lowest
            attrs["is_at_low"] = result.price <= lowest
        closes = [
            d["last"]
            for d in (state.get("daily_history") or [])
            if isinstance(d, dict) and isinstance(d.get("last"), (int, float))
        ]
        if len(closes) >= 3:
            typical = statistics.median(closes)
            if typical:
                attrs["price_typical"] = round(typical)
                attrs["pct_vs_typical"] = round(
                    (result.price - typical) / typical * 100
                )

        # Price-per-unit (e.g. kr/m for Byko lumber), when known.
        if result.unit_price and result.unit_label:
            attrs["unit_price"] = result.unit_price
            attrs["unit_label"] = result.unit_label

        # Per-listing shipping signal, reusing the same heuristic that
        # decides this for AI alternatives. There's no AI guess for a
        # user-tracked listing, so we pass ai_guess=None and let the
        # heuristic speak only when it has ground truth (e.g. Newegg ->
        # IS = False, a matching country TLD = True). None means "no
        # opinion" and the panel keeps the listing visible. Lets the
        # panel's "Ships to me only" toggle filter tracked listings too.
        attrs["ships_to_user_region"] = evaluate_shipping(
            url=product_url or "",
            retailer=result.retailer or "",
            user_region=self.coordinator.user_region,
            ai_guess=None,
        )

        # Alternatives are product-level — only attach to the primary
        # listing's price sensor. Showing them on every listing's price
        # sensor would be redundant.
        if self._listing_id == self.coordinator.primary_listing_id:
            attrs[ATTR_ALTERNATIVES] = self.coordinator.alternatives
            attrs[ATTR_ALTERNATIVES_FETCHED_AT] = (
                self.coordinator.alternatives_fetched_at
            )
            attrs[ATTR_ALTERNATIVES_ERROR] = self.coordinator.alternatives_error

        # Discontinued context for THIS listing (per-listing — secondary
        # listings can be discontinued independently)
        if result.discontinued:
            attrs.update(
                {
                    "discontinued": True,
                    "discontinued_reason": result.discontinued_reason,
                    "discontinued_at": state.get("discontinued_at"),
                    "last_known_price": state.get("lkg_price"),
                    "last_known_currency": state.get("lkg_currency"),
                    "last_known_observed_at": state.get("lkg_observed_at"),
                }
            )
        return attrs

    def _last_check_iso(self) -> str | None:
        """Fallback last_check derived from coordinator-level success time.

        Used when a listing hasn't yet stored its own last_check (e.g.
        very first tick before _async_save runs). Mirrors the legacy
        behavior — last_update_success_time is when _async_update_data
        completed, which IS when this listing was last refreshed for
        single-listing products.
        """
        ts = getattr(self.coordinator, "last_update_success_time", None)
        if ts is None:
            return None
        try:
            return ts.isoformat()
        except Exception:  # noqa: BLE001
            return None


class PriceWatchStockCountSensor(_BasePriceWatchSensor):
    """Numeric stock-count sensor. Stays unknown when count isn't available."""

    @property
    def native_value(self) -> int | None:
        result = self._result
        if result is None:
            return None
        return result.stock_count
