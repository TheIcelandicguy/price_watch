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

The mixin reads/writes coordinator state it does not itself define
(self._state, self._ai_provider, self._search_provider, self.data,
self.entry, self.hass, self.user_region, self._async_save,
self.async_load, self.async_update_listeners). Those are all provided
by PriceWatchCoordinator; the TYPE_CHECKING block documents the
contract without creating an import cycle.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .extractor import fetch_html, find_meta_image, try_jsonld

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
from .search import (
    AISynthesizerSearchProvider,
    Alternative,
    AnthropicNativeSearchProvider,
    DuckDuckGoSearchProvider,
    SearchProvider,
    SearchProviderError,
    SearchQuery,
)

# Per-hit snippet length forwarded in the DDG-only (no-AI) path. Without
# an AI to summarize, the raw snippet is handed to the panel as `notes`.
# Mirrors websocket._DDG_SNIPPET_CHARS so both search paths look alike.
_DDG_SNIPPET_CHARS = 220

# Max concurrent listing fetches when enriching DDG hits with prices via
# JSON-LD. Bounded so a search doesn't open a dozen sockets at once.
_ENRICH_CONCURRENCY = 4


def _host_label(url: str) -> str:
    """Human-ish retailer label derived from a URL host.

    DDG raw hits carry no retailer field, so we default to the bare
    hostname ("www." stripped) — e.g. "newegg.com", "amazon.de". Good
    enough for the card until JSON-LD (if any) gives something better.
    """
    try:
        host = urlparse(url).netloc.lower()
    except (ValueError, TypeError):
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_domain(value: str) -> str:
    """Normalize a user-entered domain to a bare lowercase host.

    Accepts full URLs ("https://www.amazon.de/foo"), host-with-www, or
    bare hosts. Strips scheme, path, port, leading "www.", surrounding
    whitespace, and a trailing dot. Returns "" for junk so callers can
    drop empties.
    """
    if not value:
        return ""
    s = str(value).strip().lower()
    if not s:
        return ""
    if "://" in s:
        try:
            s = urlparse(s).netloc or s
        except (ValueError, TypeError):
            pass
    # Drop any path/port/userinfo that survived a bare "amazon.de/foo".
    s = s.split("/")[0].split("@")[-1].split(":")[0]
    s = s.strip().strip(".")
    if s.startswith("www."):
        s = s[4:]
    return s


def _host_excluded(url: str, excluded: set[str]) -> bool:
    """True if the URL's host equals or is a subdomain of an excluded host."""
    if not excluded:
        return False
    host = _normalize_domain(url)
    if not host:
        return False
    return any(host == ex or host.endswith("." + ex) for ex in excluded)


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

        ai_provider = self._ai_provider
        if ai_provider is None:
            # "Free" mode — no AI. Fall back to raw DuckDuckGo search,
            # matching the panel live-search free path. async_find_-
            # alternatives detects this provider type and maps raw hits
            # straight to Alternatives (DuckDuckGoSearchProvider.find_-
            # alternatives intentionally raises).
            session = async_get_clientsession(self.hass)
            self._search_provider = DuckDuckGoSearchProvider(session=session)
            _LOGGER.debug(
                "%s: no AI provider — using DuckDuckGoSearchProvider "
                "(raw hits) for alternatives",
                self.entry.entry_id,
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

    async def _enrich_alternatives_via_jsonld(
        self, alternatives: list[Alternative]
    ) -> None:
        """Backfill price/currency/image on alternatives using JSON-LD.

        Used by every search path, not just the free one: for each
        listing missing a price or image we fetch the page (curl_cffi
        Chrome impersonation, same as the tracker) and run try_jsonld —
        the deterministic Schema.org extractor that prices every tracked
        product. Listings that already have both a price and an image are
        skipped (no fetch). A page that fails to fetch, or has no usable
        JSON-LD, simply keeps price=None (the panel renders "Price
        unknown"), so one bad page never sinks the whole search. We never
        override a price the AI already supplied. Fetches run
        concurrently under a small semaphore to keep latency reasonable.
        """
        if not alternatives:
            return

        session = async_get_clientsession(self.hass)
        sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)

        async def _enrich_one(alt: Alternative) -> None:
            # Nothing to gain if the provider already gave us both a price
            # and an image — skip the fetch entirely. This keeps the
            # Anthropic/AI path cheap: we only hit the network for the
            # listings the AI couldn't price (Claude's web_search returns
            # price=null for most results since it works from snippets).
            if alt.price is not None and alt.image_url:
                return
            async with sem:
                try:
                    html = await fetch_html(alt.url, session=session)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "alt enrich: fetch failed for %s: %s", alt.url, err
                    )
                    return
                try:
                    jsonld = try_jsonld(html, url=alt.url)
                except Exception:  # noqa: BLE001
                    _LOGGER.debug(
                        "alt enrich: JSON-LD parse failed for %s",
                        alt.url,
                        exc_info=True,
                    )
                    jsonld = None

                # Only fill the price when the provider left it blank —
                # never override a price the AI already supplied (it may
                # have come from a more reliable source than this page's
                # JSON-LD, e.g. a structured snippet).
                if alt.price is None and jsonld and jsonld.get("price"):
                    alt.price = jsonld["price"]
                    if jsonld.get("currency"):
                        alt.currency = jsonld["currency"]
                    # JSON-LD title is usually cleaner than a raw DDG
                    # snippet title (no "| Buy now - Retailer" cruft).
                    if jsonld.get("title"):
                        alt.title = jsonld["title"]
                # Grab a thumbnail regardless of whether we got a price —
                # JSON-LD image first, then og:image meta as fallback.
                image = (jsonld or {}).get("image_url") or find_meta_image(html)
                if image and not alt.image_url:
                    alt.image_url = image

        # Best-effort: gather never raises because each task swallows its
        # own errors above. return_exceptions is belt-and-suspenders.
        await asyncio.gather(
            *(_enrich_one(alt) for alt in alternatives),
            return_exceptions=True,
        )

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
            if isinstance(provider, DuckDuckGoSearchProvider):
                # No-AI path: DDG returns raw hits, not Alternatives.
                # Map them directly using the product title as the query
                # (best we can do without AI same-SKU filtering).
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
