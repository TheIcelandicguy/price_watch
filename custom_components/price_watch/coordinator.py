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
    CONF_HOME_CURRENCY,
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
    EVENT_TARGET_HIT,
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
from .migration import migrate_storage_v1_to_v2

_LOGGER = logging.getLogger(__name__)


def _derive_listing_id(entry: ConfigEntry) -> str:
    """Deterministic listing-id derivation from entry_id.

    Must produce the same id as async_migrate_entry's derivation —
    that's the contract that ties migrated entry options to migrated
    storage data. ULID suffix gives plenty of entropy.
    """
    return f"l_{entry.entry_id[-12:].lower()}"


class _PriceWatchStore(Store[dict[str, Any]]):
    """Per-product Store with built-in v1 → v2 migration.

    HA calls _async_migrate_func when the on-disk version is older
    than the requested STORAGE_VERSION. We use the listing-id captured
    at construction time to nest v1's flat history under the right
    listings[id] key in v2.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        key: str,
        *,
        listing_id: str,
    ) -> None:
        super().__init__(hass, STORAGE_VERSION, key)
        self._listing_id = listing_id

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: Any,
    ) -> dict[str, Any]:
        """Migrate v1 storage to v2 shape.

        Called by HA's Store load path when the persisted version is
        below STORAGE_VERSION. Returns the new shape, which HA then
        persists (so future loads bypass migration).
        """
        if old_major_version < 2:
            _LOGGER.info(
                "Storage migration v%s → v2 for listing %s",
                old_major_version, self._listing_id,
            )
            return migrate_storage_v1_to_v2(
                old_data or {}, listing_id=self._listing_id,
            )
        # Future version we don't know about — return as-is. HA will
        # log a warning.
        return old_data


class PriceWatchCoordinator(TimestampDataUpdateCoordinator[ExtractionResult]):
    """Coordinator for a single tracked product."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.url: str = entry.data[CONF_URL]

        # Build the AI provider once. If no API key is configured
        # (neither on this entry nor on the shared settings entry),
        # we operate in no-AI mode: JSON-LD-only or custom-parser-only.
        # extract_product accepts None for ai_provider.
        self._ai_provider: AIProvider | None = self._build_ai_provider(hass, entry)

        # custom_parser is stored as a JSON string in entry.options (so the
        # value can survive HA's config_entry serialization). Parse it once
        # at coordinator init.
        self._custom_parser: dict[str, Any] | None = self._parse_custom_parser(
            entry.options.get(CONF_CUSTOM_PARSER)
        )
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
        self._listing_id: str = _derive_listing_id(entry)

        # Per-product persistent state with built-in v1 → v2 migration.
        self._store: _PriceWatchStore = _PriceWatchStore(
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
        self._state: dict[str, Any] = self._empty_listing_state()
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

        # Image bytes cache (in-memory only; not persisted to HA Store)
        # Keyed by URL so we only refetch when the URL changes.
        self._image_bytes: bytes | None = None
        self._image_content_type: str | None = None
        self._cached_image_url: str | None = None

    @staticmethod
    def _build_ai_provider(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> AIProvider | None:
        """Build the AIProvider for this entry, or None if not configured.

        Reads CONF_AI_PROVIDER to select between Anthropic and the
        OpenAI-compatible class. Falls back to Anthropic when unset so
        existing config entries (which predate the provider abstraction)
        keep working.

        Credential resolution:
        1. The product entry's own data/options (snapshotted at creation
           time by the config flow).
        2. The shared settings entry. This is a fallback for product
           entries that don't carry their own snapshot. Reading the
           settings entry live also means subsequent key/provider
           changes propagate automatically.
        """
        # Settings come from the product entry first, then fall back to
        # the shared settings entry.
        provider_type, config = PriceWatchCoordinator._resolve_provider_config(
            hass, entry
        )
        if provider_type is None:
            return None

        try:
            return get_provider(provider_type, **config)
        except Exception as err:  # noqa: BLE001
            # A failed provider build should NOT brick the coordinator —
            # JSON-LD extraction still works without AI. Log and continue.
            _LOGGER.warning(
                "Failed to build AI provider %s for %s: %s",
                provider_type, entry.entry_id, err,
            )
            return None

    @staticmethod
    def _resolve_provider_config(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> tuple[str | None, dict[str, Any]]:
        """Pick the provider type and assemble its constructor kwargs.

        Returns (provider_type, config_kwargs). provider_type is None
        when no credentials are available anywhere (i.e. the
        integration should operate in JSON-LD-only mode for this entry).

        The merge is "product entry overrides settings entry, options
        override data" — same precedence the rest of the integration
        uses. Empty-string and None are treated the same.
        """
        # Look up settings entry once, used as fallback throughout.
        settings_entry: ConfigEntry | None = None
        for other in hass.config_entries.async_entries(entry.domain):
            if other.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
                settings_entry = other
                break

        # AI-config keys are read differently than product-specific keys
        # (url, target_price, custom_parser, cookies, etc.). For AI config,
        # we have to handle the case where the user changed the global
        # provider (settings entry) AFTER products were added. Each
        # product carries a frozen `data` snapshot from when it was
        # created — that snapshot's keys (especially `model`) become
        # stale when the settings entry switches provider.
        #
        # Rule: if the product entry has NO explicit AI override
        # (options.ai_provider not set), AI config is read from the
        # settings entry ONLY. The product's data snapshot is ignored
        # for AI keys. This way "no override" really means "inherit
        # whatever settings has now," not "inherit my creation-time
        # snapshot."
        #
        # If the product DOES have an explicit override (it set
        # options.ai_provider), we use product-first precedence so
        # the override can be fully self-contained.
        AI_CONFIG_KEYS = frozenset({
            CONF_AI_PROVIDER, CONF_API_KEY, CONF_MODEL, CONF_BASE_URL,
            CONF_INPUT_COST_PER_MTOK, CONF_OUTPUT_COST_PER_MTOK,
            CONF_MAX_HTML_CHARS, CONF_FORCE_JSON_MODE, CONF_EXTRA_HEADERS,
        })
        # A product is treated as having an explicit AI override if it
        # has SET ai_provider in its options, OR if it set any
        # significant AI config field. "Significant" excludes data-only
        # fields like cost-per-mtok (which exist on every entry by
        # default) and includes the bits that actually change provider
        # behavior. Without this, a user who set model+base_url in the
        # options flow but didn't set ai_provider would have their
        # work silently ignored.
        product_has_override = (
            entry.options.get(CONF_AI_PROVIDER) not in ("", None)
            or entry.options.get(CONF_MODEL) not in ("", None)
            or entry.options.get(CONF_BASE_URL) not in ("", None)
            or entry.options.get(CONF_API_KEY) not in ("", None)
        )

        def read(key: str, default: Any = None) -> Any:
            """Read a config value with appropriate precedence.

            Non-AI keys (url, cookies, custom_parser, target_price,
            scan_interval, etc.) always use product-first precedence:
              product.options > product.data > settings.options >
              settings.data > default

            AI-config keys behave one of two ways depending on
            whether the product has its own AI override:
            - With override (options.ai_provider set on product):
              same product-first precedence as above. Lets the
              override be fully self-contained.
            - Without override: settings entry only, ignoring the
              product's data snapshot. Keeps inheritance fresh when
              the global provider gets switched mid-life.
            """
            if key in AI_CONFIG_KEYS and not product_has_override:
                # Inheritance-only path. Skip product entry entirely
                # so its stale data snapshot can't shadow a current
                # settings value.
                if settings_entry is not None:
                    if (
                        key in settings_entry.options
                        and settings_entry.options[key] not in ("", None)
                    ):
                        return settings_entry.options[key]
                    if (
                        key in settings_entry.data
                        and settings_entry.data[key] not in ("", None)
                    ):
                        return settings_entry.data[key]
                return default

            # Normal product-first precedence.
            if key in entry.options and entry.options[key] not in ("", None):
                return entry.options[key]
            if key in entry.data and entry.data[key] not in ("", None):
                return entry.data[key]
            if settings_entry is not None:
                if key in settings_entry.options and settings_entry.options[key] not in ("", None):
                    return settings_entry.options[key]
                if key in settings_entry.data and settings_entry.data[key] not in ("", None):
                    return settings_entry.data[key]
            return default

        provider_type = read(CONF_AI_PROVIDER, PROVIDER_ANTHROPIC)

        if provider_type == PROVIDER_ANTHROPIC:
            api_key = read(CONF_API_KEY)
            if not api_key:
                _LOGGER.debug(
                    "No Anthropic key for %s; AI extraction unavailable",
                    entry.entry_id,
                )
                return None, {}
            return PROVIDER_ANTHROPIC, {
                "api_key": api_key,
                "model": read(CONF_MODEL, DEFAULT_MODEL),
            }

        if provider_type == PROVIDER_OPENAI_COMPATIBLE:
            # OpenAI-compatible needs base_url + model at minimum. api_key
            # is optional (local Ollama / LM Studio).
            base_url = read(CONF_BASE_URL)
            model = read(CONF_MODEL)
            if not base_url or not model:
                _LOGGER.warning(
                    "OpenAI-compat provider needs base_url and model "
                    "(have base_url=%r, model=%r); AI extraction "
                    "unavailable for %s",
                    base_url, model, entry.entry_id,
                )
                return None, {}
            return PROVIDER_OPENAI_COMPATIBLE, {
                "api_key": read(CONF_API_KEY),
                "model": model,
                "base_url": base_url,
                "input_cost_per_mtok": float(read(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0),
                "output_cost_per_mtok": float(read(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0),
                "max_html_chars": int(read(CONF_MAX_HTML_CHARS, 100_000) or 100_000),
                "force_json_mode": bool(read(CONF_FORCE_JSON_MODE, False)),
                "extra_headers": read(CONF_EXTRA_HEADERS),
            }

        _LOGGER.warning(
            "Unknown AI provider type %r for %s; AI extraction unavailable",
            provider_type, entry.entry_id,
        )
        return None, {}

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

    @staticmethod
    def _empty_listing_state() -> dict[str, Any]:
        """Default runtime-state dict for a fresh listing.

        Used to initialize new listings and as the fallback when the
        primary listing is missing from storage (defensive — shouldn't
        happen). Keys here match what _async_update_one_listing
        reads/writes.
        """
        return {
            "history": [],
            "lowest": None,
            "highest": None,
            "last_hash": None,
            "last_result": None,
            "last_check": None,
            "lifetime_cost_usd": 0.0,
            "discontinued": False,
            "discontinued_at": None,
            "discontinued_reason": None,
            "discontinued_title": None,
            "lkg_price": None,
            "lkg_currency": None,
            "lkg_observed_at": None,
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
                self._listings[lid] = self._empty_listing_state()

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
            self._state = self._empty_listing_state()

        # Mirror product-level alternatives onto self._state
        self._state["alternatives"] = self._product_state.get("alternatives", [])
        self._state["alternatives_fetched_at"] = self._product_state.get("alternatives_fetched_at")
        self._state["alternatives_error"] = self._product_state.get("alternatives_error")

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

    # --- Alternatives discovery ----------------------------------------------
    #
    # The alternatives feature finds other retailer listings of the same
    # product so the user can compare prices. Two implementations live in
    # the search/ subpackage:
    #
    # - AnthropicNativeSearchProvider: uses Claude's web_search tool.
    #   One round-trip, high quality, costs a few cents per call.
    # - AISynthesizerSearchProvider: free DuckDuckGo HTML search +
    #   AI synthesis (Ollama / OpenAI-compat). Lower quality because
    #   the AI works from snippets, but no Anthropic credit required.
    #
    # The coordinator picks between them based on which AI provider it
    # built in __init__. The choice is implicit (no separate config
    # option for "search provider"), with the contract: "use whatever
    # is configured for AI extraction, in the most capable mode that
    # provider supports."

    @property
    def alternatives(self) -> list[dict[str, Any]]:
        """List of alternative product dicts. Empty if none fetched."""
        return list(self._state.get("alternatives") or [])

    @property
    def alternatives_fetched_at(self) -> str | None:
        """ISO timestamp of the last alternatives refresh. None if never."""
        return self._state.get("alternatives_fetched_at")

    @property
    def alternatives_error(self) -> str | None:
        """Short user-facing error from the last fetch, if any."""
        return self._state.get("alternatives_error")

    @property
    def daily_alternatives(self) -> bool:
        """Auto-refresh alternatives once per day (TTL gated)."""
        return bool(self.entry.options.get(CONF_DAILY_ALTERNATIVES, False))

    @property
    def max_alternatives(self) -> int:
        """Per-product max alternatives to fetch."""
        raw = self.entry.options.get(
            CONF_MAX_ALTERNATIVES, DEFAULT_MAX_ALTERNATIVES
        )
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_MAX_ALTERNATIVES
        return max(1, min(20, value))

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

    @property
    def alternatives_region(self) -> str:
        """Regional preference for alternatives search.

        Currently a free-form string ('worldwide', 'nordic', 'eu',
        'us'). The Anthropic-native and AI-synthesis providers
        interpret it best-effort. We default to 'worldwide' so the
        user filters manually unless they've set an explicit option.
        """
        value = self.entry.options.get(CONF_ALTERNATIVES_REGION) or "worldwide"
        return str(value)

    def _build_search_provider(self) -> SearchProvider | None:
        """Pick a SearchProvider strategy based on the AI provider.

        Returns None if no AI provider is configured at all (then the
        feature is unavailable — the caller surfaces a clear error).

        Strategy:
        - If AI provider is Anthropic with a working key, use the
          native web_search tool (one round-trip, highest quality).
        - Otherwise, use the AI synthesizer (DDG + whatever AI we
          have). Works for Ollama, OpenAI-compat, even Anthropic-
          without-web-search if we ever disable it.

        Re-uses self._ai_provider rather than building a separate one
        — saves credentials lookups and ensures the search uses the
        same model the user picked for extraction.
        """
        if self._search_provider is not None:
            return self._search_provider

        ai_provider = self._ai_provider
        if ai_provider is None:
            return None

        # Detect Anthropic by class name (avoids importing the class
        # here and creating a circular import). The class is always
        # named AnthropicProvider in ai/anthropic_provider.py.
        provider_class_name = type(ai_provider).__name__

        if provider_class_name == "AnthropicProvider":
            # Use Anthropic's native web_search. Build a parallel
            # AnthropicNativeSearchProvider — they share the same key
            # and model but have different message/tool shapes, so a
            # separate client is cleaner than method-bombing the
            # extraction provider.
            api_key = getattr(ai_provider, "_api_key", None)
            model = getattr(ai_provider, "model", DEFAULT_MODEL)
            if not api_key:
                _LOGGER.warning(
                    "%s: AnthropicProvider has no api_key; cannot "
                    "build native search provider",
                    self.entry.entry_id,
                )
                return None
            self._search_provider = AnthropicNativeSearchProvider(
                api_key=api_key, model=model
            )
            _LOGGER.debug(
                "%s: using AnthropicNativeSearchProvider for alternatives",
                self.entry.entry_id,
            )
            return self._search_provider

        # Default: AI synthesizer over DuckDuckGo. Works for any
        # AIProvider that implements call_with_tool (OpenAI-compat
        # does; we added it as part of this feature).
        session = async_get_clientsession(self.hass)
        try:
            self._search_provider = AISynthesizerSearchProvider(
                ai_provider=ai_provider,
                session=session,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "%s: could not build AISynthesizerSearchProvider: %s",
                self.entry.entry_id, err,
            )
            return None
        _LOGGER.debug(
            "%s: using AISynthesizerSearchProvider (AI=%s) for alternatives",
            self.entry.entry_id, provider_class_name,
        )
        return self._search_provider

    async def async_find_alternatives(
        self, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Run a fresh alternatives search and persist the result.

        Returns the list of Alternative dicts (the same list now stored
        on self._state). On failure, returns an empty list and stores
        the error message in alternatives_error.

        Always updates alternatives_fetched_at on completion, success
        or failure. That way the daily-refresh TTL is respected even
        when the call fails (we don't want to hammer the search
        provider every coordinator tick after a failure).
        """
        await self.async_load()

        provider = self._build_search_provider()
        if provider is None:
            error = (
                "No AI provider configured for this product. Set one in "
                "Settings → Devices & Services → Price Watch → Configure."
            )
            self._state["alternatives_error"] = error
            self._state["alternatives_fetched_at"] = dt_util.utcnow().isoformat()
            await self._async_save()
            self.async_update_listeners()
            return []

        result_data = self.data
        # Build the search query from current product state. If we have
        # no current data (e.g. paused, never refreshed), use the entry
        # title as a fallback so the user can still try a search.
        if result_data is not None:
            title = result_data.title
            current_price = result_data.price if result_data.price else None
            currency = result_data.currency
            retailer = result_data.retailer or ""
        else:
            title = self.entry.title or "Unknown product"
            current_price = None
            currency = ""
            retailer = ""

        query = SearchQuery(
            title=title,
            current_price=current_price,
            currency=currency,
            retailer=retailer,
            max_results=(
                max_results
                if max_results is not None
                else self.max_alternatives
            ),
            region=self.alternatives_region,
            user_region=self.user_region,
        )

        _LOGGER.info(
            "%s: fetching alternatives via %s (max=%d, region=%s)",
            self.entry.entry_id,
            type(provider).__name__,
            query.max_results,
            query.region,
        )

        alternatives: list[Alternative] = []
        error: str | None = None
        try:
            alternatives = await provider.find_alternatives(query)
        except SearchProviderError as err:
            error = str(err)
            _LOGGER.warning(
                "%s: alternatives search failed: %s",
                self.entry.entry_id, err,
            )
        except Exception as err:  # noqa: BLE001
            error = f"Unexpected error: {type(err).__name__}: {err}"
            _LOGGER.exception(
                "%s: unexpected error in alternatives search",
                self.entry.entry_id,
            )

        # Persist
        self._state["alternatives"] = [a.to_dict() for a in alternatives]
        self._state["alternatives_fetched_at"] = dt_util.utcnow().isoformat()
        self._state["alternatives_error"] = error
        await self._async_save()
        self.async_update_listeners()

        _LOGGER.info(
            "%s: alternatives search done — %d results, error=%r",
            self.entry.entry_id, len(alternatives), error,
        )
        return self._state["alternatives"]

    async def async_maybe_refresh_alternatives(self) -> None:
        """If daily_alternatives is enabled and TTL has expired, run a refresh.

        Called from _async_update_data after a successful price tick.
        We deliberately fire-and-forget (no await on the result) so a
        slow search doesn't block the coordinator's update cycle —
        the next tick is more important than waiting for alternatives.

        TTL: ALTERNATIVES_REFRESH_HOURS (24h by default). On failure
        the fetched_at timestamp is updated anyway, so we don't retry
        until the next TTL period. User can force a manual refresh
        via the service.
        """
        if not self.daily_alternatives:
            return

        last = self._state.get("alternatives_fetched_at")
        if last:
            try:
                last_dt = dt_util.parse_datetime(last)
            except (ValueError, TypeError):
                last_dt = None
            if last_dt is not None:
                age = dt_util.utcnow() - last_dt
                if age.total_seconds() < ALTERNATIVES_REFRESH_HOURS * 3600:
                    return  # TTL not yet expired

        _LOGGER.debug(
            "%s: daily alternatives TTL expired, scheduling refresh",
            self.entry.entry_id,
        )
        # Fire-and-forget — don't block the update tick.
        self.hass.async_create_task(self.async_find_alternatives())

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
        custom_parser = config.get("custom_parser")
        if custom_parser is None and listing_id == self._primary_listing_id:
            custom_parser = self._custom_parser

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
                await self._update_image_bytes(result)

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

        # Per-listing FX + image — Phase 2: only primary listing.
        # Phase 3+ may extend per-listing if multi-currency cards are
        # added to the panel; for now the panel only shows the primary.
        if is_primary:
            await self._update_price_local(result)
            await self._update_image_bytes(result)

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

    async def _update_image_bytes(self, result: ExtractionResult) -> None:
        """Fetch and cache product image bytes.

        Only refetches when the source URL changes, so most updates are
        no-ops. Stored in memory only - never persisted to HA Store
        (image bytes are too large and don't survive restarts well via
        that path).
        """
        url = result.image_url if result else None
        if not url:
            self._image_bytes = None
            self._image_content_type = None
            self._cached_image_url = None
            return
        if url == self._cached_image_url and self._image_bytes is not None:
            # Same URL, cache hit - skip the fetch
            return
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            fetched = await fetch_image_bytes(
                url, async_get_clientsession(self.hass)
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Image fetch raised: %s", err)
            fetched = None

        if fetched is None:
            _LOGGER.warning("Could not fetch product image: %s", url)
            return  # Keep stale bytes if we have any - better than nothing

        self._image_bytes, self._image_content_type = fetched
        self._cached_image_url = url
        _LOGGER.debug(
            "Image fetched: %d bytes, %s", len(self._image_bytes), self._image_content_type
        )

    async def _update_price_local(self, result: ExtractionResult) -> None:
        """Compute price_local from the current result, if home_currency is set.

        Failure is non-fatal: price_local stays None, sensor reports unavailable.
        Called both on a fresh fetch AND on the UNCHANGED short-circuit so that
        adding/changing home_currency in settings options takes effect on the
        next coordinator tick without needing the source page to change.
        """
        home = self.home_currency
        if not home:
            _LOGGER.info(
                "price_local: no home_currency configured (set one in "
                "Settings -> Devices & Services -> Price Watch -> Configure)"
            )
            self._price_local = None
            return
        if not result or not result.currency:
            _LOGGER.warning(
                "price_local: no source currency available on result, skipping"
            )
            self._price_local = None
            return
        src = result.currency.upper()
        dst = home.upper()
        if src == dst:
            _LOGGER.debug("price_local: %s == %s, no conversion needed", src, dst)
            self._price_local = result.price
            return
        try:
            converted = await self._fx.convert(result.price, src, dst)
            if converted is None:
                _LOGGER.warning(
                    "price_local: FX conversion %s->%s returned None "
                    "(see earlier FX log lines for the cause)",
                    src, dst,
                )
            else:
                _LOGGER.debug(
                    "price_local: %s %s -> %s %s", result.price, src, converted, dst
                )
            self._price_local = converted
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("price_local: FX conversion threw: %s", err)
            self._price_local = None

    @property
    def home_currency(self) -> str | None:
        """User's home currency from settings entry, if configured.

        Looked up fresh on every access so changing it in settings options
        takes effect on next update without reload.
        """
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == "settings":
                value = entry.options.get(
                    CONF_HOME_CURRENCY, entry.data.get(CONF_HOME_CURRENCY)
                )
                return (value or "").upper() or None
        return None

    @property
    def price_local(self) -> float | None:
        """Price in user's home currency, if conversion succeeded."""
        return self._price_local

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
        """Raw bytes of the product photo (None if fetch failed or no URL)."""
        return self._image_bytes

    @property
    def image_content_type(self) -> str | None:
        """MIME type of the cached image bytes."""
        return self._image_content_type

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
        title = result.title if result else "Price Watch product"
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

    def _fire_event(
        self, event_type: str, result: ExtractionResult, previous: ExtractionResult | None
    ) -> None:
        """Fire an HA event with consistent payload shape."""
        self.hass.bus.async_fire(
            event_type,
            {
                "entry_id": self.entry.entry_id,
                "title": result.title,
                "url": self.url,
                "retailer": result.retailer,
                "price": result.price,
                "currency": result.currency,
                "previous_price": previous.price if previous else None,
                "target": self._target_price,
                "image_url": result.image_url,
                "in_stock": result.in_stock,
            },
        )

    def _fire_event_with_extra(
        self,
        event_type: str,
        result: ExtractionResult,
        previous: ExtractionResult | None,
        extra: dict[str, Any],
    ) -> None:
        """Same as _fire_event but merges in event-type-specific fields.

        Used by EVENT_DISCONTINUED to attach last_known_price /
        discontinued_at / discontinued_reason that aren't present on
        regular price events.
        """
        payload = {
            "entry_id": self.entry.entry_id,
            "title": result.title,
            "url": self.url,
            "retailer": result.retailer,
            "price": result.price,
            "currency": result.currency,
            "previous_price": previous.price if previous else None,
            "target": self._target_price,
            "image_url": result.image_url,
            "in_stock": result.in_stock,
        }
        payload.update(extra)
        self.hass.bus.async_fire(event_type, payload)

    def _fire_target_hit(
        self, result: ExtractionResult, previous: ExtractionResult | None
    ) -> None:
        self._fire_event(EVENT_TARGET_HIT, result, previous)
