"""Alternatives-discovery mixin for PriceWatchCoordinator.

Extracted from coordinator.py. The alternatives feature finds other
retailer listings of the same product so the user can compare prices.
It's a self-contained concern layered on top of the coordinator's core
update/persistence loop, so it lives here as a mixin the coordinator
inherits.

Three search implementations live in the search/ subpackage:

- AnthropicNativeSearchProvider: uses Claude's web_search tool.
  One round-trip, high quality, costs a few cents per call.
- AISynthesizerSearchProvider: free DuckDuckGo HTML search +
  AI synthesis (Ollama / OpenAI-compat). Lower quality because
  the AI works from snippets, but no Anthropic credit required.
- DuckDuckGoSearchProvider: raw DDG hits with no AI cleanup, used
  in "Free" mode (no AI provider configured at all). Lowest quality
  — no same-SKU filtering, often no price — but the feature works
  instead of erroring out. Matches the panel live-search free path.

The coordinator picks between them based on which AI provider it
built in __init__. The choice is implicit (no separate config
option for "search provider"), with the contract: "use whatever
is configured for AI extraction, in the most capable mode that
provider supports; fall back to raw DDG when there is no AI."

The URL/domain filters (non-shop domains, search/category pages,
excluded hosts) live in search/filters.py and the JSON-LD price backfill
in search/enrich.py — both are shared with the panel's live search in
websocket.py, so they are not coordinator concerns.

The mixin reads/writes coordinator state it does not itself define
(self._state, self._ai_provider, self._search_provider, self.data,
self.entry, self.hass, self.user_region, self._async_save,
self.async_load, self.async_update_listeners). Those are all provided
by PriceWatchCoordinator; the TYPE_CHECKING block documents the
contract without creating an import cycle.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    ALTERNATIVES_REFRESH_HOURS,
    CONF_ALTERNATIVES_REGION,
    CONF_DAILY_ALTERNATIVES,
    CONF_EXCLUDED_DOMAINS,
    CONF_MAX_ALTERNATIVES,
    DEFAULT_MAX_ALTERNATIVES,
    DEFAULT_MODEL,
    DOMAIN,
)
from .search.enrich import enrich_alternatives_via_jsonld
from .search.filters import (
    _DDG_SNIPPET_CHARS,
    _host_excluded,
    _host_label,
    _is_non_shop_domain,
    _normalize_domain,
)
from .search import (
    AISynthesizerSearchProvider,
    Alternative,
    AnthropicNativeSearchProvider,
    DuckDuckGoSearchProvider,
    SearchProvider,
    SearchProviderError,
    SearxngSearchProvider,
    SearchQuery,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .ai import AIProvider
    from .extractor import ExtractionResult

_LOGGER = logging.getLogger(__name__)


class AlternativesMixin:
    """Alternatives-discovery behavior for PriceWatchCoordinator.

    All attributes referenced via ``self`` here are defined on the
    concrete coordinator. Declared in TYPE_CHECKING only so static
    analysis understands the contract; at runtime they resolve through
    the coordinator instance.
    """

    if TYPE_CHECKING:
        hass: HomeAssistant
        entry: ConfigEntry
        data: ExtractionResult | None
        user_region: str
        _state: dict[str, Any]
        _ai_provider: AIProvider | None
        _ai_fallback_only: bool
        _search_provider: SearchProvider | None

        async def async_load(self) -> None: ...
        async def _async_save(self) -> None: ...
        def async_update_listeners(self) -> None: ...

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
    def alternatives_region(self) -> str:
        """Regional preference for alternatives search.

        Currently a free-form string ('worldwide', 'nordic', 'eu',
        'us'). The Anthropic-native and AI-synthesis providers
        interpret it best-effort. We default to 'worldwide' so the
        user filters manually unless they've set an explicit option.
        """
        value = self.entry.options.get(CONF_ALTERNATIVES_REGION) or "worldwide"
        return str(value)

    @property
    def excluded_domains(self) -> set[str]:
        """Normalized hostnames to drop from alternatives results.

        Read from the global settings entry's options
        (CONF_EXCLUDED_DOMAINS), stored as a list of host strings. We
        normalize to bare lowercase hosts here so matching is robust to
        www./scheme/path noise the user may have pasted in. Returns an
        empty set when no settings entry or no list is configured.
        """
        raw: Any = None
        settings_id = self.hass.data.get(DOMAIN, {}).get("settings")
        if settings_id:
            settings_entry = self.hass.config_entries.async_get_entry(settings_id)
            if settings_entry is not None:
                raw = settings_entry.options.get(CONF_EXCLUDED_DOMAINS)
        if not raw:
            return set()
        if isinstance(raw, str):
            raw = [raw]
        out: set[str] = set()
        for item in raw:
            norm = _normalize_domain(str(item))
            if norm:
                out.add(norm)
        return out

    def _build_search_provider(self) -> SearchProvider | None:
        """Pick a SearchProvider strategy based on the AI provider.

        Never returns None: when no AI provider is configured ("Free"
        mode), falls back to raw DuckDuckGo search — the same path the
        panel's live search uses. Quality is lower (no AI same-SKU
        filtering, often no price), but the feature works rather than
        erroring out.

        Strategy:
        - If AI provider is Anthropic with a working key, use the
          native web_search tool (one round-trip, highest quality).
        - Else if any other AI provider is configured, use the AI
          synthesizer (DDG + that AI). Works for Ollama, OpenAI-compat.
        - Else (no AI at all) use raw DuckDuckGo hits, no AI cleanup.

        Re-uses self._ai_provider rather than building a separate one
        — saves credentials lookups and ensures the search uses the
        same model the user picked for extraction.
        """
        if self._search_provider is not None:
            return self._search_provider

        session = async_get_clientsession(self.hass)
        # A configured SearXNG instance replaces DuckDuckGo as the raw search
        # source (free path + AI synthesizer); Anthropic's native web_search
        # is unaffected.
        raw_source = (
            SearxngSearchProvider(self._searxng_url, session=session)
            if self._searxng_url
            else DuckDuckGoSearchProvider(session=session)
        )

        ai_provider = self._ai_provider
        if ai_provider is None or self._ai_fallback_only:
            # Raw search (same path the panel live-search uses). Either no AI
            # at all ("Free" mode), OR the user chose "fallback only" — keep
            # discovery free and reserve the AI for failed price extractions.
            # async_find_alternatives detects a raw provider and maps its hits
            # straight to Alternatives (find_alternatives intentionally raises).
            self._search_provider = raw_source
            _LOGGER.debug(
                "%s: %s — using %s (raw hits) for alternatives",
                self.entry.entry_id,
                "AI fallback-only" if ai_provider else "no AI provider",
                raw_source.name,
            )
            return self._search_provider

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

        # Default: AI synthesizer over the raw source (DuckDuckGo, or SearXNG
        # when configured). Works for any AIProvider that implements
        # call_with_tool (OpenAI-compat does).
        try:
            self._search_provider = AISynthesizerSearchProvider(
                ai_provider=ai_provider,
                session=session,
                raw_source=raw_source,
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

    async def _enrich_alternatives_via_jsonld(
        self, alternatives: list[Alternative]
    ) -> None:
        """Coordinator wrapper around the module-level enrichment helper."""
        await enrich_alternatives_via_jsonld(self.hass, alternatives)

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
            # Should be unreachable now that the no-AI path falls back to
            # DuckDuckGo, but a misconfigured AI provider (e.g. Anthropic
            # selected with no key) can still yield None — surface it.
            error = (
                "Could not build a search provider for this product. Check "
                "the AI settings in Settings → Devices & Services → "
                "Price Watch → Configure."
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
            if isinstance(provider, (DuckDuckGoSearchProvider, SearxngSearchProvider)):
                # No-AI path: raw hits, not Alternatives. Map them directly
                # using the product title as the query (best we can do
                # without AI same-SKU filtering).
                hits = await provider.search(
                    query.title, max_results=query.max_results
                )
                alternatives = [
                    Alternative(
                        title=hit.title,
                        url=hit.url,
                        retailer=_host_label(hit.url),
                        notes=(hit.snippet or "")[:_DDG_SNIPPET_CHARS],
                    )
                    for hit in hits
                    if hit.url
                ][: query.max_results]
                # DDG snippets rarely contain a price and there's no AI to
                # synthesize one. Fetch each listing and run the same
                # deterministic JSON-LD extractor used for tracked
                # products to fill in price/currency/image. Best-effort.
                await self._enrich_alternatives_via_jsonld(alternatives)
            else:
                alternatives = await provider.find_alternatives(query)
                # Even AI providers leave most prices blank: Anthropic's
                # native web_search and the DDG+AI synthesizer both work
                # from search snippets, not the rendered page, so Claude
                # returns price=null rather than guessing. Backfill those
                # gaps with the same deterministic JSON-LD pass used for
                # the free path — it only fetches listings missing a price
                # or image and never overrides a price the AI supplied.
                await self._enrich_alternatives_via_jsonld(alternatives)
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

        # Drop results whose host is on the global exclude list. Applied
        # after enrichment (so a JSON-LD redirect can't reintroduce a
        # filtered host) and regardless of provider — the user wants these
        # sites gone from every search, not just flagged.
        excluded = self.excluded_domains
        if excluded and alternatives:
            before = len(alternatives)
            alternatives = [
                alt for alt in alternatives if not _host_excluded(alt.url, excluded)
            ]
            dropped = before - len(alternatives)
            if dropped:
                _LOGGER.debug(
                    "%s: dropped %d alternative(s) via domain blocklist (%s)",
                    self.entry.entry_id, dropped, ", ".join(sorted(excluded)),
                )

        # Drop known non-commerce hosts (code repos, video, social, forums,
        # tutorial blogs). An "alternative" is meant to be another place to
        # buy this product, so a GitHub/YouTube/Reddit hit is pure noise —
        # unlike Free-mode "Search & add" where the user picks manually and
        # we only flag them. Conservative denylist: an unrecognized host is
        # treated as a possible shop and kept.
        if alternatives:
            before = len(alternatives)
            alternatives = [
                alt for alt in alternatives if not _is_non_shop_domain(alt.url)
            ]
            dropped = before - len(alternatives)
            if dropped:
                _LOGGER.debug(
                    "%s: dropped %d alternative(s) as non-shop hosts",
                    self.entry.entry_id, dropped,
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
