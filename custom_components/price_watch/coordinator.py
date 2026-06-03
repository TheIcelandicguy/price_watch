"""Coordinator for Price Watch.

One coordinator instance per tracked product. Handles:
- Scheduled fetches via DataUpdateCoordinator
- Price history persistence to HA Store
- Event firing on drops / target hits / new lows
- Per-product cost tracking and budget circuit breaker
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .ai import (
    AIProvider,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI_COMPATIBLE,
    get_provider,
)
from .const import (
    ALTERNATIVES_REFRESH_HOURS,
    CONF_AI_PROVIDER,
    CONF_ALTERNATIVES_REGION,
    CONF_USER_REGION,
    CURRENCY_TO_COUNTRY,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CUSTOM_PARSER,
    CONF_DAILY_ALTERNATIVES,
    CONF_EXTRA_HEADERS,
    CONF_FORCE_DISCONTINUED,
    CONF_FORCE_JSON_MODE,
    CONF_INPUT_COST_PER_MTOK,
    CONF_MAX_ALTERNATIVES,
    CONF_MAX_HTML_CHARS,
    CONF_MODEL,
    CONF_OUTPUT_COST_PER_MTOK,
    CONF_PAUSED,
    CONF_SCAN_INTERVAL,
    CONF_TARGET_PRICE,
    CONF_URL,
    DEFAULT_MAX_ALTERNATIVES,
    DEFAULT_MODEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_SETTINGS,
    EVENT_BACK_IN_STOCK,
    EVENT_DISCONTINUED,
    EVENT_NEW_LOW,
    EVENT_PRICE_DROP,
    MAX_HISTORY_ENTRIES,
    STORAGE_VERSION,
)
from .extractor import ExtractionError, ExtractionResult, extract_product, fetch_image_bytes
from .fx import FxRates
from .search import (
    AISynthesizerSearchProvider,
    Alternative,
    AnthropicNativeSearchProvider,
    SearchProvider,
    SearchProviderError,
    SearchQuery,
)
from .coordinator_alternatives import AlternativesMixin
from .coordinator_events import EventsMixin
from .coordinator_fx import FxMixin
from .coordinator_storage import StorageMixin
from .provider_config import build_ai_provider
from .store import PriceWatchStore, derive_listing_id, empty_listing_state

_LOGGER = logging.getLogger(__name__)


class PriceWatchCoordinator(
    AlternativesMixin,
    EventsMixin,
    FxMixin,
    StorageMixin,
    TimestampDataUpdateCoordinator[ExtractionResult],
):
    """Coordinator for a single tracked product.

    Cohesive concerns are split into mixins the coordinator inherits:
    - AlternativesMixin (coordinator_alternatives.py): alternatives discovery
      (find/maybe-refresh, search-provider selection, alternatives* props).
    - EventsMixin (coordinator_events.py): HA bus event emission (price drop /
      new low / back-in-stock / target hit / discontinued).
    - FxMixin (coordinator_fx.py): price_local / home-currency conversion.
    - StorageMixin (coordinator_storage.py): v2 Store load/save, listing-config
      resolution (effective_custom_parser), discontinued restore.
    AI-provider resolution lives in provider_config.py; the Store subclass +
    listing-id/empty-state helpers live in store.py.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.url: str = entry.data[CONF_URL]

        # Build the AI provider once. If no API key is configured
        # (neither on this entry nor on the shared settings entry),
        # we operate in no-AI mode: JSON-LD-only or custom-parser-only.
        # extract_product accepts None for ai_provider.
        self._ai_provider: AIProvider | None = build_ai_provider(hass, entry)

        # custom_parser is stored as a JSON string in entry.options (so the
        # value can survive HA's config_entry serialization). Parse it once
        # at coordinator init.
        self._custom_parser: dict[str, Any] | None = self._parse_custom_parser(
            entry.options.get(CONF_CUSTOM_PARSER)
        )
        # Product-level Wix variant pin for the PRIMARY listing — used when a
        # single-product entry has no materialized listings[] array (the
        # from-scratch / panel-track case). Per-listing variant_options on a
        # listing config still take precedence; this is the primary fallback,
        # mirroring how _custom_parser works above.
        self._variant_options: list[str] = [
            str(v) for v in (entry.options.get("variant_options") or [])
        ]
        self._target_price: float | None = entry.options.get(
            CONF_TARGET_PRICE, entry.data.get(CONF_TARGET_PRICE)
        )

        scan_minutes = entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60)
        )
        interval = timedelta(minutes=scan_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id[:8]}",
            update_interval=interval,
        )

        # v2: the deterministic listing-id ties this coordinator to its
        # one listing in the v2 entry-options and storage shapes. Same
        # derivation that async_migrate_entry used.
        self._listing_id: str = derive_listing_id(entry)

        # Per-product persistent state with built-in v1 → v2 migration.
        self._store: PriceWatchStore = PriceWatchStore(
            hass,
            f"{DOMAIN}.{entry.entry_id}",
            listing_id=self._listing_id,
        )
        # Phase 2: per-listing state. self._listings maps listing_id ->
        # state dict (history, lowest, highest, last_hash, lifetime_cost_usd,
        # discontinued/LKG fields). Each listing has its own price
        # observation history and runtime state.
        #
        # self._product_state holds fields shared across all listings
        # of a product (alternatives + their fetched_at/error).
        #
        # self._primary_listing_id is the "default" listing — its data
        # backs the existing single-listing coordinator API (.lowest,
        # .history, .data, etc.) for back-compat with sensors and panel.
        # For migrated v1 entries, this is the only listing.
        self._primary_listing_id: str = self._listing_id
        self._listings: dict[str, dict[str, Any]] = {}
        self._product_state: dict[str, Any] = {
            "alternatives": [],
            "alternatives_fetched_at": None,
            "alternatives_error": None,
        }
        # self._state aliases the primary listing's state dict — existing
        # code that does self._state[X] = Y propagates to
        # self._listings[primary_id][X] = Y (same dict reference). Set
        # by _ensure_primary_listing() after load.
        self._state: dict[str, Any] = empty_listing_state()
        # Per-listing ExtractionResult cache. Populated by
        # _async_update_one_listing on each successful extraction.
        # Read as the "previous" result for event firing and UNCHANGED
        # short-circuits. Empty on cold start (first tick has no
        # previous; events that need a previous are correctly skipped).
        # In-memory only — restart resets to empty, sensors recover
        # from the next refresh.
        self._listing_results: dict[str, "ExtractionResult"] = {}
        self._loaded = False

        # Lazy-built search provider. Constructed on first
        # async_find_alternatives call so we don't pay the cost when
        # the feature isn't in use. Lives on self because some
        # implementations hold resources (e.g. the
        # AnthropicNativeSearchProvider's AsyncAnthropic client) we
        # want to reuse across calls.
        self._search_provider: SearchProvider | None = None

        # FX conversion - shared session, cached rates
        self._fx = FxRates(hass, async_get_clientsession(hass))
        self._price_local: float | None = None

        # Image bytes cache (in-memory only; not persisted to HA Store).
        # Phase 3c: one entry per listing_id so every listing has its own
        # thumbnail. Keyed first by listing_id, then internally by URL so
        # we only refetch a listing's image when its source URL changes.
        # The primary listing's bytes are also surfaced via the legacy
        # image_bytes / image_content_type properties (used by the
        # ProductImage entity and the panel's product-level image).
        self._listing_image_bytes: dict[str, bytes] = {}
        self._listing_image_content_type: dict[str, str] = {}
        self._listing_cached_image_url: dict[str, str | None] = {}

    @property
    def target_price(self) -> float | None:
        """Current target price."""
        return self._target_price

    async def async_set_target(self, target: float | None) -> None:
        """Update target price (from service or options flow)."""
        self._target_price = target
        # Reflect in entry options so it persists across restarts
        new_options = {**self.entry.options, CONF_TARGET_PRICE: target}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        # Re-evaluate target hit immediately if we have a current price
        if self.data and target is not None and self.data.price <= target:
            self._fire_target_hit(self.data, previous=None)

    async def async_reset_history(self) -> None:
        """Wipe price history but keep current value."""
        self._state["history"] = []
        self._state["lowest"] = None
        self._state["highest"] = None
        await self._async_save()
        self.async_update_listeners()

    # --- Pause / force-discontinued overrides ---------------------------------
    #
    # These two flags live in entry.options and are read fresh on every
    # _async_update_data tick (rather than cached on self) so that the
    # options-flow listener can update them without bouncing the entry.
    # Pattern: options-flow writes options, HA fires an update listener,
    # listener calls async_request_refresh on the coordinator (existing
    # plumbing in __init__.py via _async_update_listener). Next refresh
    # picks up the new flags via these properties.

    @property
    def paused(self) -> bool:
        """User has paused this product. Skip refreshes."""
        return bool(self.entry.options.get(CONF_PAUSED, False))

    @property
    def force_discontinued(self) -> bool:
        """User has manually marked this product as discontinued."""
        return bool(self.entry.options.get(CONF_FORCE_DISCONTINUED, False))

    async def async_set_paused(self, paused: bool) -> None:
        """Set or clear the paused flag.

        When pausing: stops the polling loop immediately (no
        DataUpdateCoordinator tick will fire). When unpausing: restores
        the configured interval AND triggers an immediate refresh so the
        user sees fresh data without waiting up to scan_interval.

        Persisted on entry.options; survives restart.
        """
        new_options = {**self.entry.options, CONF_PAUSED: bool(paused)}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        if paused:
            self.update_interval = None
            _LOGGER.info("%s: polling paused by user", self.url)
        else:
            scan_minutes = self.entry.options.get(
                CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60)
            )
            self.update_interval = timedelta(minutes=scan_minutes)
            _LOGGER.info("%s: polling resumed (every %sm)", self.url, scan_minutes)
            # Refresh immediately so user sees current state
            await self.async_request_refresh()

    async def async_force_discontinued(
        self, value: bool, reason: str | None = None
    ) -> None:
        """Manually mark or unmark this product as discontinued.

        Marking: sets force_discontinued=True in options, then mirrors
        all the state a real discontinuation would write (discontinued
        flag, discontinued_at, discontinued_reason, LKG from current
        data). Stops polling. Fires the EVENT_DISCONTINUED event so
        downstream automations see it as a real discontinuation.

        Unmarking: clears force_discontinued AND the discontinued
        markers in state, restores the polling interval, requests an
        immediate refresh. The next refresh may re-mark it as
        discontinued if the page actually shows that.
        """
        new_options = {
            **self.entry.options,
            CONF_FORCE_DISCONTINUED: bool(value),
        }
        self.hass.config_entries.async_update_entry(
            self.entry, options=new_options
        )
        await self.async_load()

        if value:
            now = dt_util.utcnow()
            previous = self.data
            # Capture current price as LKG if we have a non-discontinued
            # observation. Otherwise, keep whatever LKG already exists
            # (could be from a previous real discontinuation, or None).
            if previous is not None and not previous.discontinued:
                self._state["lkg_price"] = previous.price
                self._state["lkg_currency"] = previous.currency
                self._state["lkg_observed_at"] = now.isoformat()
                self._state["discontinued_title"] = previous.title
            self._state["discontinued"] = True
            self._state["discontinued_at"] = (
                self._state.get("discontinued_at") or now.isoformat()
            )
            self._state["discontinued_reason"] = (
                reason or "Manually marked discontinued"
            )
            self.update_interval = None
            await self._async_save()

            # Synthesize a discontinued ExtractionResult so sensors
            # reflect the new state without waiting for a refresh.
            synthetic = ExtractionResult(
                title=(self._state.get("discontinued_title")
                       or (previous.title if previous else "(discontinued)")),
                price=0.0,
                currency=self._state.get("lkg_currency") or "",
                in_stock=False,
                stock_count=0,
                image_url=previous.image_url if previous else None,
                sku=previous.sku if previous else None,
                retailer=previous.retailer if previous else None,
                content_hash=self._state.get("last_hash") or "",
                cost_usd=0.0,
                method="manual+discontinued",
                raw={},
                discontinued=True,
                discontinued_reason=self._state["discontinued_reason"],
            )
            self.async_set_updated_data(synthetic)
            # Fire the standard event so automations don't have to care
            # whether a discontinuation was detected or manual.
            self._fire_event_with_extra(
                EVENT_DISCONTINUED,
                synthetic,
                previous,
                extra={
                    "discontinued_at": self._state["discontinued_at"],
                    "discontinued_reason": self._state["discontinued_reason"],
                    "last_known_price": self._state.get("lkg_price"),
                    "last_known_currency": self._state.get("lkg_currency"),
                    "manual": True,
                },
            )
            _LOGGER.info(
                "%s: manually marked discontinued (%s)",
                self.url, self._state["discontinued_reason"],
            )
            return

        # Unmark: clear discontinued state and resume polling.
        # We deliberately keep LKG fields — they're just history at this
        # point and might be useful if the product is rediscontinued.
        self._state["discontinued"] = False
        self._state["discontinued_at"] = None
        self._state["discontinued_reason"] = None
        await self._async_save()
        scan_minutes = self.entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60)
        )
        self.update_interval = timedelta(minutes=scan_minutes)
        _LOGGER.info(
            "%s: discontinued flag cleared by user; resuming polling", self.url,
        )
        await self.async_request_refresh()

    # Alternatives discovery (alternatives* properties, max_alternatives,
    # alternatives_region, _build_search_provider, async_find_alternatives,
    # async_maybe_refresh_alternatives) lives in AlternativesMixin —
    # see coordinator_alternatives.py.

    @property
    def user_region(self) -> str:
        """Return ISO 3166-1 alpha-2 country code for shipping checks.

        Lookup order: product entry option -> settings entry option
        -> CURRENCY_TO_COUNTRY fallback from home_currency -> "".
        Empty string disables the shipping heuristic + AI prompt.

        Always returned uppercase. Whitespace and obvious junk
        (longer than 2 chars) is rejected as if unset.
        """
        # Product entry override
        raw = self.entry.options.get(CONF_USER_REGION)
        if not raw:
            # Settings entry inheritance. hass.data[DOMAIN]["settings"]
            # stores the entry_id (a string), not the ConfigEntry object —
            # resolve via the config_entries registry. Defensive against
            # the settings entry being missing or unloaded.
            settings_id = self.hass.data.get(DOMAIN, {}).get("settings")
            if settings_id:
                settings_entry = self.hass.config_entries.async_get_entry(
                    settings_id
                )
                if settings_entry is not None:
                    raw = settings_entry.options.get(CONF_USER_REGION)
        if raw:
            s = str(raw).strip().upper()
            if len(s) == 2 and s.isalpha():
                return s
        # Currency-based fallback
        home = self.home_currency
        if home:
            mapped = CURRENCY_TO_COUNTRY.get(home.upper())
            if mapped:
                return mapped
        return ""

    async def _async_update_one_listing(
        self,
        listing_id: str,
        listing: dict[str, Any],
    ) -> "ExtractionResult":
        """Fetch and process one listing's URL.

        Extracted from the single-URL body of the legacy
        _async_update_data so the outer loop can iterate over
        self._listings.items() and apply per-URL extraction to each.

        Args:
            listing_id: The listing's stable ID (e.g., "l_xxx").
            listing: The listing's runtime-state dict from
                self._listings[listing_id]. Mutated in place — history
                appended, lowest/highest tracked, discontinued/LKG set,
                last_hash/last_check/lifetime_cost_usd updated.

        Returns:
            ExtractionResult on success; also stored in
            self._listing_results[listing_id] for next tick's "previous".

        Raises:
            UpdateFailed on extraction error.

        Side effects (PRIMARY listing only — kept product-level for
        Phase 2 to preserve existing sensor semantics):
            - _update_price_local: FX conversion to home_currency
            - _update_image_bytes: cached image fetch
            - update_interval = None: stops the polling loop when
              the primary listing goes terminal-discontinued

        Events fired (with listing_id + listing URL in payload):
            - EVENT_DISCONTINUED
            - EVENT_NEW_LOW
            - EVENT_PRICE_DROP
            - EVENT_BACK_IN_STOCK
            - EVENT_TARGET_HIT (primary listing only)
        """
        # Resolve per-listing config. URL falls back to self.url for the
        # primary listing — listings created pre-Phase-2 may not have
        # a config in entry.options yet if the migration was partial.
        config = self._get_listing_config(listing_id) or {}
        url = config.get("url") or (
            self.url if listing_id == self._primary_listing_id else None
        )
        custom_parser = self.effective_custom_parser(listing_id)

        # Pinned Wix variant (option labels) for this listing, if any. Falls
        # back to the product-level pin for the primary listing (entries with
        # no materialized listings[] array).
        variant_options = config.get("variant_options") or None
        if variant_options is None and listing_id == self._primary_listing_id:
            variant_options = self._variant_options or None

        if not url:
            raise UpdateFailed(f"Listing {listing_id} has no URL")

        is_primary = listing_id == self._primary_listing_id

        # Previous result for THIS listing — used for previous_hash,
        # price-delta events, and UNCHANGED short-circuit.
        previous: "ExtractionResult | None" = self._listing_results.get(listing_id)
        previous_hash = listing.get("last_hash")

        try:
            result = await extract_product(
                session=async_get_clientsession(self.hass),
                url=url,
                ai_provider=self._ai_provider,
                custom_parser=custom_parser,
                previous_hash=previous_hash,
                variant_options=variant_options,
            )
        except ExtractionError as err:
            if str(err) == "UNCHANGED":
                # Page hasn't changed — reuse last result, but still
                # recompute FX for the primary listing (rates change
                # daily, home_currency may have been edited since).
                if previous is not None:
                    _LOGGER.debug(
                        "%s [%s]: content unchanged, reusing cached result",
                        url, listing_id,
                    )
                    if is_primary:
                        await self._update_price_local(previous)
                    return previous
                # No previous — actually extract
                result = await extract_product(
                    session=async_get_clientsession(self.hass),
                    url=url,
                    ai_provider=self._ai_provider,
                    custom_parser=custom_parser,
                    previous_hash=None,
                    variant_options=variant_options,
                )
            else:
                raise UpdateFailed(f"Extraction failed: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err

        # Update per-listing state
        now = dt_util.utcnow()
        listing["last_hash"] = result.content_hash
        listing["last_check"] = now.isoformat()
        listing["lifetime_cost_usd"] = (
            listing.get("lifetime_cost_usd", 0.0) + result.cost_usd
        )

        # Build event payload extras — every event from this method
        # carries listing context so consumers can disambiguate when
        # a product has multiple listings.
        event_extra_base = {"listing_id": listing_id, "url": url}

        # Discontinued products are TERMINAL per-listing. We:
        #   - copy forward last known good (LKG) so the sensor still
        #     has a meaningful price attribute
        #   - persist the discontinued flag so first_refresh after
        #     restart skips re-extraction
        #   - stop the WHOLE coordinator's polling loop only if the
        #     PRIMARY listing goes discontinued (secondary listings
        #     going discontinued doesn't stop primary polling)
        #   - fire EVENT_DISCONTINUED once (not on every subsequent tick)
        if result.discontinued:
            previously_discontinued = bool(listing.get("discontinued"))
            if previous is not None and not previous.discontinued:
                listing["lkg_price"] = previous.price
                listing["lkg_currency"] = previous.currency
                listing["lkg_observed_at"] = (
                    previous.raw.get("ts")
                    if isinstance(previous.raw, dict)
                    else None
                )
            listing["discontinued"] = True
            listing["discontinued_at"] = (
                listing.get("discontinued_at") or now.isoformat()
            )
            listing["discontinued_reason"] = result.discontinued_reason
            listing["discontinued_title"] = result.title

            if not previously_discontinued:
                _LOGGER.info(
                    "%s [%s]: marked discontinued (%s); %sstopping polling",
                    url, listing_id,
                    result.discontinued_reason or "no reason given",
                    "" if is_primary else "NOT ",
                )
                self._fire_event_with_extra(
                    EVENT_DISCONTINUED,
                    result,
                    previous,
                    extra={
                        **event_extra_base,
                        "discontinued_at": listing["discontinued_at"],
                        "discontinued_reason": result.discontinued_reason,
                        "last_known_price": listing.get("lkg_price"),
                        "last_known_currency": listing.get("lkg_currency"),
                    },
                )

            # Stop polling only if PRIMARY went discontinued. Secondary
            # listings can be discontinued without halting the whole
            # coordinator — primary may still be active.
            if is_primary:
                self.update_interval = None
                await self._update_price_local(result)
            # Keep each listing's thumbnail current even when discontinued
            # (the panel still shows the row with its last-known image).
            await self._update_image_bytes(listing_id, result)

            self._listing_results[listing_id] = result
            return result

        # Live (non-discontinued) path
        # Append to history
        history: list[dict[str, Any]] = listing.setdefault("history", [])
        history.append(
            {
                "ts": now.isoformat(),
                "price": result.price,
                "currency": result.currency,
                "in_stock": result.in_stock,
            }
        )
        if len(history) > MAX_HISTORY_ENTRIES:
            listing["history"] = history[-MAX_HISTORY_ENTRIES:]

        # Per-listing extremes (lowest/highest of THIS listing's history)
        if listing.get("lowest") is None or result.price < listing["lowest"]:
            old_low = listing.get("lowest")
            listing["lowest"] = result.price
            if old_low is not None:  # don't fire on very first observation
                self._fire_event_with_extra(
                    EVENT_NEW_LOW, result, previous, extra=event_extra_base
                )
        if listing.get("highest") is None or result.price > listing["highest"]:
            listing["highest"] = result.price

        # Transition events
        if previous is not None:
            if result.price < previous.price:
                self._fire_event_with_extra(
                    EVENT_PRICE_DROP, result, previous, extra=event_extra_base
                )
            if not previous.in_stock and result.in_stock:
                self._fire_event_with_extra(
                    EVENT_BACK_IN_STOCK, result, previous, extra=event_extra_base
                )

        # Target hit — target_price is product-level, so only check
        # against the primary listing. Secondary listings don't fire
        # target events (they'd be confusing for the user — "target
        # hit on Amazon" when the actual product is on a different
        # retailer).
        if (
            is_primary
            and self._target_price is not None
            and result.price <= self._target_price
            and (previous is None or previous.price > self._target_price)
        ):
            self._fire_target_hit(result, previous)

        # Per-listing image — Phase 3c: fetch every listing's own photo
        # so the panel can show a thumbnail per listing row. FX stays
        # primary-only (conversion is product-level in Phase 2; the panel
        # only shows price_local for the headline/primary listing).
        if is_primary:
            await self._update_price_local(result)
        await self._update_image_bytes(listing_id, result)

        self._listing_results[listing_id] = result
        return result

    async def _async_update_data(self) -> "ExtractionResult":
        """Fetch latest prices for all listings of this product.

        Phase 2: outer iterator. Each listing is updated independently
        via _async_update_one_listing. Returns the PRIMARY listing's
        result for back-compat with sensors reading coordinator.data.
        Secondary listings persist their results in self._listing_results
        and their state in self._listings[id] — accessible to per-listing
        sensors (Phase 2.3+) but not to coordinator.data itself.

        Product-level shortcuts (paused, force_discontinued) apply to
        the whole product — when paused, no listing is fetched.

        Failure handling: a primary-listing failure raises UpdateFailed
        (the whole coordinator tick fails, sensors go unavailable, HA
        will retry). A secondary-listing failure is logged but the tick
        succeeds — primary continues to work, secondary stays at its
        last known state until next tick.
        """
        await self.async_load()

        # Product-level shortcuts: paused or force_discontinued apply
        # to every listing. We don't fetch anything when paused.
        if self.paused:
            _LOGGER.debug("%s: paused, skipping refresh", self.url)
            # Return prior data so sensors stay at last-known. If we
            # have no prior data (first refresh after install while
            # paused — unusual but possible), raise so the entry goes
            # to setup_retry, which is the right thing.
            if self.data is None:
                raise UpdateFailed("Paused with no prior data")
            return self.data

        if self.force_discontinued and not (self.data and self.data.discontinued):
            # Force flag set but our last data wasn't already discontinued
            # — apply it now. Handles options-flow toggle race plus
            # restart-while-flag-set.
            await self.async_force_discontinued(True)
            return self.data

        # Shell entry guard: no listings configured means nothing to
        # extract. Stay loaded (self.data may be None if this entry has
        # never had a listing) and let the next add_listing trigger
        # a reload that re-runs this tick with real listings.
        if not self._listings:
            _LOGGER.debug(
                "%s: no listings configured (shell entry), skipping refresh",
                self.entry.entry_id,
            )
            return self.data  # may be None — DataUpdateCoordinator accepts that

        primary_result: "ExtractionResult | None" = None
        primary_error: Exception | None = None

        # Iterate over listings. Each listing's success/failure is
        # independent. We snapshot .items() with list() so a listing
        # added/removed mid-iteration (shouldn't happen but defensive)
        # doesn't break the loop.
        for listing_id, listing in list(self._listings.items()):
            try:
                result = await self._async_update_one_listing(listing_id, listing)
            except UpdateFailed as err:
                if listing_id == self._primary_listing_id:
                    # Primary listing failure propagates to the whole tick
                    primary_error = err
                else:
                    # Secondary listing failure: log and continue
                    _LOGGER.warning(
                        "%s: secondary listing %s update failed: %s",
                        self.entry.entry_id, listing_id, err,
                    )
                continue
            if listing_id == self._primary_listing_id:
                primary_result = result

        if primary_result is None:
            # Primary listing failed. Propagate the specific error if
            # we have one; otherwise generic message.
            if primary_error is not None:
                raise primary_error
            raise UpdateFailed("Primary listing produced no result")

        # Persist all listing state in one save (one write for N listings)
        await self._async_save()

        # Daily alternatives refresh — product-level, fire-and-forget.
        # The maybe-refresh check is gated by daily_alternatives flag +
        # TTL internally; this is a cheap no-op when feature is off.
        await self.async_maybe_refresh_alternatives()

        return primary_result

    async def _update_image_bytes(
        self, listing_id: str, result: ExtractionResult
    ) -> None:
        """Fetch and cache one listing's image bytes.

        Only refetches when that listing's source URL changes, so most
        updates are no-ops. Stored in memory only - never persisted to HA
        Store (image bytes are too large and don't survive restarts well
        via that path). Keyed by listing_id so each listing keeps its own
        thumbnail independently (Phase 3c).
        """
        url = result.image_url if result else None
        if not url:
            self._listing_image_bytes.pop(listing_id, None)
            self._listing_image_content_type.pop(listing_id, None)
            self._listing_cached_image_url[listing_id] = None
            return
        if (
            url == self._listing_cached_image_url.get(listing_id)
            and self._listing_image_bytes.get(listing_id) is not None
        ):
            # Same URL, cache hit - skip the fetch
            return
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            fetched = await fetch_image_bytes(
                url, async_get_clientsession(self.hass)
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Image fetch raised (%s): %s", listing_id, err)
            fetched = None

        if fetched is None:
            _LOGGER.warning(
                "Could not fetch listing image (%s): %s", listing_id, url
            )
            return  # Keep stale bytes if we have any - better than nothing

        self._listing_image_bytes[listing_id] = fetched[0]
        self._listing_image_content_type[listing_id] = fetched[1]
        self._listing_cached_image_url[listing_id] = url
        _LOGGER.debug(
            "Image fetched for %s: %d bytes, %s",
            listing_id,
            len(fetched[0]),
            fetched[1],
        )

    @property
    def lowest(self) -> float | None:
        """Lifetime lowest price."""
        return self._state.get("lowest")

    @property
    def highest(self) -> float | None:
        """Lifetime highest price."""
        return self._state.get("highest")

    @property
    def history(self) -> list[dict[str, Any]]:
        """Price history."""
        return list(self._state.get("history", []))

    @property
    def lifetime_cost(self) -> float:
        """Total API cost since first run."""
        return float(self._state.get("lifetime_cost_usd", 0.0))

    # ---- Per-listing accessors (Phase 2.3) ----
    # These give sensor.py and other entity platforms a way to read state
    # for a specific listing, distinct from the product-level / primary-
    # listing-fronted properties above. For all currently-deployed
    # single-listing entries, `listing_ids` returns one ID and
    # `get_listing_state(primary_id)` returns the same dict object that
    # `self._state` aliases.

    @property
    def listing_ids(self) -> list[str]:
        """Stable IDs of all listings configured for this product.

        Primary listing comes first; other listings are appended in
        whatever order they appear in self._listings (currently dict
        insertion order). Sensor platforms iterate over this to build
        per-listing entities.
        """
        ids: list[str] = []
        if self._primary_listing_id in self._listings:
            ids.append(self._primary_listing_id)
        for lid in self._listings:
            if lid != self._primary_listing_id:
                ids.append(lid)
        return ids

    @property
    def primary_listing_id(self) -> str:
        """ID of the primary listing.

        Sensor platforms use this to decide whether a listing's sensors
        should use legacy unique_ids ({entry}_{key}) for back-compat, or
        extended unique_ids ({entry}_{listing}_{key}) for new listings,
        preserving HA's entity registry history for existing entities.
        """
        return self._primary_listing_id

    def get_listing_state(self, listing_id: str) -> dict[str, Any] | None:
        """Return the listing's runtime state dict.

        Contains: history, lowest, highest, lkg_*, discontinued_*,
        lifetime_cost_usd, last_check, last_hash, last_result.

        Returns None if the listing_id is unknown. For the primary
        listing, this is the SAME dict object as self._state (alias);
        mutations propagate.
        """
        return self._listings.get(listing_id)

    def get_listing_result(self, listing_id: str) -> "ExtractionResult | None":
        """Return the listing's latest ExtractionResult, or None.

        Populated by _async_update_one_listing on each successful tick.
        None if the listing hasn't refreshed since coordinator startup
        (cold start — sensors show unavailable until first tick).
        """
        return self._listing_results.get(listing_id)

    def get_listing_config(self, listing_id: str) -> dict[str, Any] | None:
        """Public alias for _get_listing_config.

        Sensor.py uses this to read the listing's URL, retailer,
        currency, etc. from entry.options.listings. Returns None when
        no listing with this id is configured.
        """
        return self._get_listing_config(listing_id)


    @property
    def discontinued_at(self) -> str | None:
        """ISO timestamp when this product was first observed as discontinued.

        None if the product is currently available. Persists across
        restarts via the entry's HA Store.
        """
        return self._state.get("discontinued_at")

    @property
    def last_known_price(self) -> float | None:
        """The product's price as of the last refresh BEFORE it was
        marked discontinued. None when no good observation was ever
        captured."""
        return self._state.get("lkg_price")

    @property
    def last_known_currency(self) -> str | None:
        """Currency that pairs with last_known_price."""
        return self._state.get("lkg_currency")

    @property
    def last_known_observed_at(self) -> str | None:
        """ISO timestamp of the last successful pre-discontinued refresh."""
        return self._state.get("lkg_observed_at")

    @property
    def image_bytes(self) -> bytes | None:
        """Primary listing's photo bytes (None if fetch failed or no URL).

        Back-compat accessor for the product-level image (ProductImage
        entity + panel product image). Per-listing bytes are available
        via image_bytes_for().
        """
        return self._listing_image_bytes.get(self.primary_listing_id)

    @property
    def image_content_type(self) -> str | None:
        """MIME type of the primary listing's cached image bytes."""
        return self._listing_image_content_type.get(self.primary_listing_id)

    def image_bytes_for(self, listing_id: str) -> bytes | None:
        """Raw bytes of a specific listing's photo (None if none cached)."""
        return self._listing_image_bytes.get(listing_id)

    def image_content_type_for(self, listing_id: str) -> str | None:
        """MIME type of a specific listing's cached image bytes."""
        return self._listing_image_content_type.get(listing_id)

    @property
    def device_info(self) -> dict[str, Any]:
        """Common device_info for entities to share.

        configuration_url resolution (Phase 3b shell-safe):
          1. entry.data[CONF_URL] if set (legacy URL-based entries)
          2. Primary listing's config URL (shell-then-populate entries
             that have had a listing added)
          3. None (shell entries with no listings yet — HA's device
             registry rejects empty string as invalid URL, so we MUST
             return None rather than "" in that case)
        """
        result = self.data
        # Prefer the extracted title; fall back to the config entry title
        # (the name the user gave when adding the product) so a product
        # whose first fetch failed still shows its real name in the panel
        # and device list — not a generic placeholder.
        title = (
            result.title
            if result
            else (self.entry.title or "Price Watch product")
        )
        retailer = result.retailer if result else None

        config_url: str | None = self.url or None
        if not config_url and self._listings:
            primary_config = self._get_listing_config(self._primary_listing_id)
            if primary_config:
                config_url = primary_config.get("url") or None

        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": title,
            "manufacturer": retailer or "Price Watch",
            "model": "Tracked product",
            "configuration_url": config_url,
            "entry_type": "service",
        }

