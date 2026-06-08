"""Per-listing update loop mixin for PriceWatchCoordinator.

Extracted from coordinator.py — the core fetch/extract/persist loop:

- _async_update_data: the DataUpdateCoordinator override. Outer iterator
  over self._listings; applies product-level shortcuts (paused /
  force_discontinued / shell-entry), updates each listing independently,
  saves once, and returns the PRIMARY result for coordinator.data.
- _async_update_one_listing: fetch + extract one listing's URL, handle the
  UNCHANGED short-circuit, append history, track extremes, fire transition
  events, and (primary only) recompute FX + image bytes.
- _update_image_bytes: per-listing image fetch + in-memory cache.

This mixin reads/writes a lot of coordinator-owned state and calls into the
other mixins (StorageMixin: async_load/_async_save/_get_listing_config/
effective_custom_parser; FxMixin: _update_price_local; EventsMixin:
_fire_*; AlternativesMixin: async_maybe_refresh_alternatives) plus the
coordinator's own paused/force_discontinued/async_force_discontinued. All of
those resolve through the concrete PriceWatchCoordinator; the TYPE_CHECKING
block documents the contract without creating an import cycle.

IMPORTANT: like the other coordinator mixins, this MUST appear before
TimestampDataUpdateCoordinator in the class bases so its _async_update_data
overrides the base coordinator's abstract one.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    EVENT_BACK_IN_STOCK,
    EVENT_DISCONTINUED,
    EVENT_DISCOUNT,
    EVENT_NEW_LOW,
    EVENT_PRICE_DROP,
    MAX_DAILY_HISTORY_DAYS,
    MAX_HISTORY_ENTRIES,
)
from .extractor import (
    ExtractionError,
    ExtractionResult,
    extract_product,
    fetch_image_bytes,
    is_on_sale,
)

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .ai import AIProvider

_LOGGER = logging.getLogger(__name__)


class UpdateMixin:
    """The per-listing fetch/extract/persist loop for PriceWatchCoordinator."""

    if TYPE_CHECKING:
        hass: HomeAssistant
        entry: ConfigEntry
        data: ExtractionResult | None
        url: str
        update_interval: timedelta | None
        paused: bool
        force_discontinued: bool
        _listings: dict[str, dict[str, Any]]
        _listing_results: dict[str, ExtractionResult]
        _primary_listing_id: str
        _ai_provider: AIProvider | None
        _variant_options: list[str]
        _target_price: float | None
        _listing_image_bytes: dict[str, bytes]
        _listing_image_content_type: dict[str, str]
        _listing_cached_image_url: dict[str, str | None]

        # Provided by the other mixins / the coordinator.
        def _get_listing_config(self, listing_id: str) -> dict[str, Any] | None: ...
        def effective_custom_parser(self, listing_id: str) -> dict[str, Any] | None: ...
        async def _update_price_local(self, result: ExtractionResult) -> None: ...
        def _fire_event_with_extra(
            self, event_type: str, result: ExtractionResult,
            previous: ExtractionResult | None, extra: dict[str, Any],
        ) -> None: ...
        def _fire_target_hit(
            self, result: ExtractionResult, previous: ExtractionResult | None
        ) -> None: ...
        async def _async_save(self) -> None: ...
        async def async_load(self) -> None: ...
        async def async_force_discontinued(
            self, value: bool, reason: str | None = None
        ) -> None: ...
        async def async_maybe_refresh_alternatives(self) -> None: ...

    async def _async_update_one_listing(
        self,
        listing_id: str,
        listing: dict[str, Any],
    ) -> ExtractionResult:
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
        previous: ExtractionResult | None = self._listing_results.get(listing_id)
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

        # Honor listing-level currency/retailer overrides (set via edit_listing)
        # when extraction didn't supply them. A custom CSS price selector reads
        # only the number, so without this the user's configured currency would
        # be lost — breaking price formatting AND FX conversion (price_local
        # skips when currency is blank) AND the stored history rows.
        if not result.currency and config.get("currency"):
            result.currency = str(config["currency"]).strip().upper()
        if not result.retailer and config.get("retailer"):
            result.retailer = str(config["retailer"]).strip()

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

        # Daily-downsampled long history for "good price?" context. One bucket
        # per UTC date {date, min, max, last}; today's bucket keeps the day's
        # min/max and latest. Capped at MAX_DAILY_HISTORY_DAYS.
        daily: list[dict[str, Any]] = listing.setdefault("daily_history", [])
        today = now.date().isoformat()
        if daily and daily[-1].get("date") == today:
            bucket = daily[-1]
            bucket["min"] = min(bucket.get("min", result.price), result.price)
            bucket["max"] = max(bucket.get("max", result.price), result.price)
            bucket["last"] = result.price
        else:
            daily.append(
                {
                    "date": today,
                    "min": result.price,
                    "max": result.price,
                    "last": result.price,
                }
            )
        if len(daily) > MAX_DAILY_HISTORY_DAYS:
            listing["daily_history"] = daily[-MAX_DAILY_HISTORY_DAYS:]

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

        # Transition events. Guarded on a known `previous` so none of these
        # fire on the first poll (incl. the first poll after an HA restart,
        # when the in-memory previous is empty) — avoids spurious pings.
        if previous is not None:
            if result.price < previous.price:
                self._fire_event_with_extra(
                    EVENT_PRICE_DROP, result, previous, extra=event_extra_base
                )
            if not previous.in_stock and result.in_stock:
                self._fire_event_with_extra(
                    EVENT_BACK_IN_STOCK, result, previous, extra=event_extra_base
                )
            # Discount appeared: the retailer's own sale flag (original_price
            # > price) went from absent to present. Distinct from a price
            # drop — fires once, when the sale starts.
            if is_on_sale(result) and not is_on_sale(previous):
                discount_percent = round(
                    (1 - result.price / result.original_price) * 100
                )
                self._fire_event_with_extra(
                    EVENT_DISCOUNT,
                    result,
                    previous,
                    extra={
                        **event_extra_base,
                        "original_price": result.original_price,
                        "discount_percent": discount_percent,
                    },
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

    async def _async_update_data(self) -> ExtractionResult:
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

        primary_result: ExtractionResult | None = None
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
