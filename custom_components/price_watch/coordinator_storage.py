"""Persistence + listing-config resolution mixin for PriceWatchCoordinator.

Extracted from coordinator.py. This is the storage layer: load/save the
v2 nested Store shape, sync runtime state (self._listings) with the
declared listings in entry.options, resolve a listing's effective parser,
and restore a discontinued product without a live fetch.

The in-memory ↔ storage translation lives entirely here:
- async_load / _load_v2_storage: Store → self._listings + self._product_state
- _build_v2_storage / _async_save: self._listings + self._product_state → Store
- _ensure_primary_listing: reconcile self._listings with entry.options.listings
- effective_custom_parser / _get_listing_config / _parse_custom_parser:
  resolve the parser a poll will actually use for a listing

All attributes referenced via ``self`` are defined on the concrete
PriceWatchCoordinator (set in its __init__); the TYPE_CHECKING block
documents the contract without creating an import cycle.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import CONF_URL
from .extractor import ExtractionResult
from .store import empty_listing_state

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .store import PriceWatchStore

_LOGGER = logging.getLogger(__name__)


class StorageMixin:
    """v2 storage load/save + listing-config resolution for the coordinator."""

    if TYPE_CHECKING:
        hass: HomeAssistant
        entry: ConfigEntry
        update_interval: timedelta | None
        _loaded: bool
        _store: PriceWatchStore
        _listings: dict[str, dict[str, Any]]
        _product_state: dict[str, Any]
        _state: dict[str, Any]
        _primary_listing_id: str
        _listing_results: dict[str, Any]
        _custom_parser: dict[str, Any] | None

        def async_set_updated_data(self, data: ExtractionResult) -> None: ...

    @staticmethod
    def _parse_custom_parser(raw: Any) -> dict[str, Any] | None:
        """Parse the custom_parser option, accepting either a dict or JSON string.

        The config flow stores parsers as JSON strings (so HA's serialization
        is happy). The options flow text field also returns a string. Either
        way, we want a dict at runtime.
        """
        if raw is None or raw == "":
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                import json as _json
                parsed = _json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, TypeError):
                _LOGGER.warning("Could not parse custom_parser JSON: %r", raw[:120])
                return None
        return None

    async def async_load(self) -> None:
        """Load persisted state from v2 storage.

        Phase 2: populates self._listings (per-URL state) and
        self._product_state (shared across listings) via
        _load_v2_storage(). Then _ensure_primary_listing() initializes
        the primary listing if missing and aliases self._state to it
        for back-compat.
        """
        if self._loaded:
            return
        stored = await self._store.async_load()
        if stored:
            self._load_v2_storage(stored)
        self._ensure_primary_listing()
        self._loaded = True

    def _load_v2_storage(self, stored: dict[str, Any]) -> None:
        """Populate self._listings + self._product_state from v2 storage.

        Phase 2 replacement for `_flatten_v2_storage`. Loads ALL
        listings into self._listings (not just the primary) and
        product-level state into self._product_state. Defensive
        against partial/missing/malformed storage.

        Translates the v2 storage key 'price_history' → in-memory
        'history' for back-compat with existing coordinator code.
        """
        listings = stored.get("listings")
        product = stored.get("product")
        if not isinstance(listings, dict):
            listings = {}
        if not isinstance(product, dict):
            product = {}
        loaded: dict[str, dict[str, Any]] = {}
        for listing_id, ls in listings.items():
            if not isinstance(ls, dict):
                _LOGGER.debug(
                    "%s: listing %s storage entry not a dict, skipping",
                    self.entry.entry_id, listing_id,
                )
                continue
            loaded[listing_id] = {
                "history": list(ls.get("price_history") or []),
                "lowest": ls.get("lowest"),
                "highest": ls.get("highest"),
                "last_hash": ls.get("last_hash"),
                "last_result": ls.get("last_result"),
                "last_check": ls.get("last_check"),
                "lifetime_cost_usd": float(ls.get("lifetime_cost_usd") or 0.0),
                "discontinued": bool(ls.get("discontinued", False)),
                "discontinued_at": ls.get("discontinued_at"),
                "discontinued_reason": ls.get("discontinued_reason"),
                "discontinued_title": ls.get("discontinued_title"),
                "lkg_price": ls.get("lkg_price"),
                "lkg_currency": ls.get("lkg_currency"),
                "lkg_observed_at": ls.get("lkg_observed_at"),
            }
        self._listings = loaded
        self._product_state = {
            "alternatives": list(product.get("alternatives") or []),
            "alternatives_fetched_at": product.get("alternatives_fetched_at"),
            "alternatives_error": product.get("alternatives_error"),
        }

    def _ensure_primary_listing(self) -> None:
        """Sync self._listings with entry.options.listings and alias self._state.

        Idempotent. Two sources of truth in play:
            - entry.options.listings: declares which listings EXIST
              (added by add_listing, removed by remove_listing)
            - self._listings: holds RUNTIME STATE for known listings

        Sync rules:
            - For each listing declared in entry.options: ensure
              self._listings has an entry (create empty state if missing)
            - Listings in self._listings but NOT declared in options are
              pruned as orphans (from partial remove_listing, external
              storage edits, etc.)
            - Back-compat: if options has no declared listings but
              storage has the deterministic primary listing's ID,
              treat primary as declared (covers v1-migrated entries
              where options.listings might be empty/absent)

        Primary listing determination for self._state alias:
            1. Prefer the deterministic primary_listing_id when it's
               in self._listings (v1-migrated entries + entries that
               had this ID added via add_listing)
            2. Otherwise use the first listing in self._listings
               (shell entries whose first listing was added later
               via add_listing got a random listing_id)
            3. If self._listings is empty (shell entry with NO
               listings yet), self._state points at a throwaway
               sentinel dict NOT in self._listings — legacy code
               that reads self._state[X] gets defaults, writes are
               harmless (no listing to persist them to)

        Mirrors product-level alternatives onto self._state for
        back-compat with code that reads self._state["alternatives"];
        reverse-mirror happens in _build_v2_storage.
        """
        options_listings = self.entry.options.get("listings") or []
        if not isinstance(options_listings, list):
            options_listings = []

        # Collect declared listing IDs from entry.options
        declared_ids: set[str] = set()
        for listing_cfg in options_listings:
            if isinstance(listing_cfg, dict):
                lid = listing_cfg.get("id")
                if isinstance(lid, str) and lid:
                    declared_ids.add(lid)

        # Back-compat: no declared listings, but the entry already has
        # a primary listing identity. Auto-declare it in two cases:
        #   (a) v1-migrated entry whose storage has the deterministic
        #       primary state — load preserves it, we declare it now.
        #   (b) URL-based entry created via the "Add by URL" config
        #       flow — entry.data.url is set but options.listings was
        #       never populated (only add_listing populates it). The
        #       deterministic primary IS the implicit listing for this
        #       entry and must be declared so sensors materialize on
        #       first setup.
        # Shell entries (entry.data.url == "" AND no listings declared)
        # bypass both branches and fall through to the sentinel path.
        if not declared_ids:
            entry_url = self.entry.data.get(CONF_URL) or ""
            if self._primary_listing_id in self._listings or entry_url:
                declared_ids.add(self._primary_listing_id)

        # Ensure runtime state for every declared listing
        for lid in declared_ids:
            if lid not in self._listings:
                _LOGGER.debug(
                    "%s: listing %s declared in entry.options but missing "
                    "from storage; initializing empty runtime state",
                    self.entry.entry_id, lid,
                )
                self._listings[lid] = empty_listing_state()

        # Prune orphans — listings in storage but not declared in options
        orphan_ids = set(self._listings.keys()) - declared_ids
        for orphan in orphan_ids:
            _LOGGER.info(
                "%s: pruning orphaned listing %s (not declared in entry.options)",
                self.entry.entry_id, orphan,
            )
            self._listings.pop(orphan, None)
            self._listing_results.pop(orphan, None)

        # Pick primary listing for self._state alias
        if self._primary_listing_id in self._listings:
            # Deterministic primary exists — use it (back-compat path)
            self._state = self._listings[self._primary_listing_id]
        elif self._listings:
            # No deterministic primary, but listings exist — use the
            # first declared listing as runtime primary. Update
            # self._primary_listing_id so listing_ids and sensor
            # unique_id logic treat it consistently.
            first_id = next(iter(self._listings))
            _LOGGER.info(
                "%s: deterministic primary %s not declared; using first "
                "listing %s as runtime primary",
                self.entry.entry_id, self._primary_listing_id, first_id,
            )
            self._primary_listing_id = first_id
            self._state = self._listings[first_id]
        else:
            # Shell entry — no listings at all. self._state is a sentinel
            # dict NOT connected to self._listings. Legacy code that
            # reads self._state[X] gets defaults; writes don't persist
            # (there's no real listing to persist to). _async_update_data
            # short-circuits before any per-listing work in this state.
            self._state = empty_listing_state()

        # Mirror product-level alternatives onto self._state
        self._state["alternatives"] = self._product_state.get("alternatives", [])
        self._state["alternatives_fetched_at"] = self._product_state.get("alternatives_fetched_at")
        self._state["alternatives_error"] = self._product_state.get("alternatives_error")

    def effective_custom_parser(self, listing_id: str) -> dict[str, Any] | None:
        """The parser dict the poll will actually use for this listing.

        Resolves the listing's own custom_parser, falling back to the
        product-level parser for the primary listing, and normalizes through
        the single tolerant boundary so a parser persisted as a JSON string
        (config flow) is handled the same as one persisted as a dict
        (services). Returns a dict or None. Shared by the poll path and the
        sensor's has_cookies attribute so the resolution lives in one place.
        """
        config = self._get_listing_config(listing_id) or {}
        parser = self._parse_custom_parser(config.get("custom_parser"))
        if parser is None and listing_id == self._primary_listing_id:
            parser = self._custom_parser
        return parser

    def _get_listing_config(self, listing_id: str) -> dict[str, Any] | None:
        """Return the listing's CONFIG dict from entry.options.listings.

        Separate from self._listings[id] which holds RUNTIME STATE.
        The config has URL, retailer, custom_parser, request_cookies,
        min_price, max_price, paused, etc. — populated by the
        migration and (in Phase 3+) by add_listing operations.

        Returns None if no listing with this id exists in entry.options
        — which can happen if the listings array was edited externally
        or if a Phase-3 remove_listing left the runtime state in
        self._listings (defensive; shouldn't happen in normal flow).
        """
        listings = self.entry.options.get("listings") or []
        if not isinstance(listings, list):
            return None
        for listing in listings:
            if isinstance(listing, dict) and listing.get("id") == listing_id:
                return listing
        return None

    def _build_v2_storage(self) -> dict[str, Any]:
        """Serialize self._listings + self._product_state to v2 storage shape.

        Phase 2: emits ALL listings, not just the primary. Before
        building, syncs alternatives* fields from self._state (where
        existing code writes them) back into self._product_state
        (where they live in v2 storage).
        """
        # Pull alternatives* back out of self._state into self._product_state
        self._product_state["alternatives"] = list(self._state.get("alternatives") or [])
        self._product_state["alternatives_fetched_at"] = self._state.get("alternatives_fetched_at")
        self._product_state["alternatives_error"] = self._state.get("alternatives_error")

        listings_out: dict[str, Any] = {}
        for listing_id, listing in self._listings.items():
            history = list(listing.get("history") or listing.get("price_history") or [])
            listings_out[listing_id] = {
                "price_history": history,
                "lowest": listing.get("lowest"),
                "highest": listing.get("highest"),
                "last_hash": listing.get("last_hash"),
                "last_result": listing.get("last_result"),
                "last_check": listing.get("last_check"),
                "lifetime_cost_usd": float(listing.get("lifetime_cost_usd") or 0.0),
                "discontinued": bool(listing.get("discontinued", False)),
                "discontinued_at": listing.get("discontinued_at"),
                "discontinued_reason": listing.get("discontinued_reason"),
                "discontinued_title": listing.get("discontinued_title"),
                "lkg_price": listing.get("lkg_price"),
                "lkg_currency": listing.get("lkg_currency"),
                "lkg_observed_at": listing.get("lkg_observed_at"),
            }
        return {
            "listings": listings_out,
            "product": dict(self._product_state),
        }

    async def async_restore_if_discontinued(self) -> bool:
        """If the persisted state says the product is discontinued,
        synthesize an ExtractionResult and short-circuit the first
        refresh.

        Returns True if restoration happened (caller should skip the
        usual first_refresh). Returns False if there's no discontinued
        marker, leaving the coordinator in its normal first-refresh
        path.
        """
        await self.async_load()
        if not self._state.get("discontinued"):
            return False

        # Synthesize a discontinued ExtractionResult from persisted data.
        # The sensor reads .discontinued and the LKG attributes off this
        # result to render the "Discontinued" state.
        restored = ExtractionResult(
            title=self._state.get("discontinued_title") or "(discontinued product)",
            price=0.0,
            currency=self._state.get("lkg_currency") or "",
            in_stock=False,
            stock_count=0,
            image_url=None,
            sku=None,
            retailer=None,
            content_hash=self._state.get("last_hash") or "",
            cost_usd=0.0,
            method="restored+discontinued",
            raw={},
            discontinued=True,
            discontinued_reason=self._state.get("discontinued_reason"),
        )
        # Bypass the DataUpdateCoordinator's normal "first refresh" path.
        # async_set_updated_data() pushes the result to listeners exactly
        # the same way a successful refresh would, without scheduling
        # the periodic loop.
        self.async_set_updated_data(restored)
        # Stop the polling loop so we don't refetch this discontinued
        # product on every interval.
        self.update_interval = None
        return True

    async def _async_save(self) -> None:
        """Persist state in v2 nested shape."""
        await self._store.async_save(self._build_v2_storage())
