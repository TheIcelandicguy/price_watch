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

from .extractor import fetch_html, find_meta_image, find_meta_price, try_jsonld

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
    SearxngSearchProvider,
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


# Domains that are clearly NOT shops — code hosts, video, social, forums,
# Q&A, encyclopedias, docs/tutorial blogs. Used by Free-mode "Search & add"
# to flag raw web hits that can't be a seller. Conservative on purpose: we
# only mark the obvious non-commerce sites, so a real store never gets a
# false "not a store" badge (the inverse — an unflagged non-shop — is the
# safe failure: the user just judges it themselves, same as before).
_NON_SHOP_DOMAINS: frozenset[str] = frozenset(
    {
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "githubusercontent.com",
        "youtube.com",
        "youtu.be",
        "vimeo.com",
        "reddit.com",
        "quora.com",
        "stackoverflow.com",
        "stackexchange.com",
        "superuser.com",
        "serverfault.com",
        "wikipedia.org",
        "wikimedia.org",
        "fandom.com",
        "medium.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "pinterest.com",
        "tiktok.com",
        "linkedin.com",
        "readthedocs.io",
        "readthedocs.org",
        "instructables.com",
        "hackster.io",
        "hackaday.com",
        "hackaday.io",
        "dronebotworkshop.com",
        "randomnerdtutorials.com",
        "home-assistant.io",
        "lastminuteengineers.com",
        "circuitdigest.com",
        "electronicshub.org",
        "allaboutcircuits.com",
        "makeuseof.com",
        "howtogeek.com",
        "wled.ge",
        # Review / editorial / spec sites — surface heavily for product
        # queries ("best X", "X review") but never sell anything. None of
        # these host a checkout, so dropping them only removes dead rows.
        "protoolreviews.com",
        "popularmechanics.com",
        "rtings.com",
        "tomsguide.com",
        "tomshardware.com",
        "techradar.com",
        "cnet.com",
        "theverge.com",
        "engadget.com",
        "pcmag.com",
        "gsmarena.com",
        "notebookcheck.net",
        "trustedreviews.com",
        "wirecutter.com",
        "nytimes.com",
        "consumerreports.org",
        "which.co.uk",
        "digitaltrends.com",
        "androidauthority.com",
        "thespruce.com",
        "familyhandyman.com",
        "bobvila.com",
    }
)

# Subdomain prefixes that signal documentation, community, or editorial
# content rather than a product listing — none of these ever host a
# checkout. Catches doc/wiki/forum hosts (kno.wled.ge, docs.espressif.com,
# community.home-assistant.io) that aren't worth denylisting individually.
# Conservative: a store never lives at docs./forum./help., so this can't
# false-flag a real seller's product page.
_NON_SHOP_SUBDOMAIN_PREFIXES: tuple[str, ...] = (
    "docs.",
    "doc.",
    "kno.",
    "wiki.",
    "blog.",
    "forum.",
    "forums.",
    "community.",
    "help.",
    "support.",
    "learn.",
    "kb.",
)


def _is_non_shop_domain(url: str) -> bool:
    """True if the URL's host is a known non-commerce site (heuristic).

    Two signals, both conservative:
      1. Suffix match against the curated denylist, so subdomains
         (gist.github.com, m.youtube.com, en.wikipedia.org) are caught.
      2. A documentation/community subdomain prefix (docs., kno., forum.,
         help., ...) — those hosts never sell a product.

    An unrecognized host returns False (treated as a possible shop),
    which is the safe default.
    """
    host = _normalize_domain(url)
    if not host:
        return False
    if any(host == nd or host.endswith("." + nd) for nd in _NON_SHOP_DOMAINS):
        return True
    return host.startswith(_NON_SHOP_SUBDOMAIN_PREFIXES)


# Path fragments that mark a search-results or category/browse page rather than
# a single product — these never carry one trackable price (Amazon /s?k=,
# Home Depot /b/, Lowe's /pl/, eBay /sch/, Shopify /collections/, etc.).
_LISTING_PATH_MARKERS: tuple[str, ...] = (
    "/b/",
    "/pl/",
    "/sch/",
    "/search",
    "/browse/",
    "/category/",
    "/categories/",
    "/collections/",
    "/c/",
    "/shop/",
)
# Query keys that mark a search (?k=, ?q=, ?query=, ...).
_LISTING_QUERY_KEYS: tuple[str, ...] = (
    "k=",
    "q=",
    "query=",
    "searchterm=",
    "keyword=",
    "searchkeyword=",
)


def _looks_like_listing_url(url: str) -> bool:
    """True if the URL is a search/category/browse page, not a single product.

    Conservative: matches well-known listing path fragments and search query
    keys. A real product URL (Amazon /dp/, /gp/product/, retailer /product/…)
    has none of these, so this won't drop a trackable page.
    """
    if not url:
        return False
    try:
        parts = urlparse(url.lower())
    except ValueError:
        return False
    path, query = parts.path, parts.query
    if any(marker in path for marker in _LISTING_PATH_MARKERS):
        return True
    # Amazon search: path ends with "/s" and carries a search query.
    if (path == "/s" or path.endswith("/s")) and "k=" in query:
        return True
    if any(query == k or query.startswith(k) or ("&" + k) in query for k in _LISTING_QUERY_KEYS):
        return True
    return False


def is_unusable_search_result(url: str) -> bool:
    """Drop signal for live search / alternatives: a non-shop domain (review,
    spec, wiki, video) OR a search/category page — neither is a trackable,
    priceable product listing."""
    return _is_non_shop_domain(url) or _looks_like_listing_url(url)


if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .ai import AIProvider
    from .extractor import ExtractionResult

_LOGGER = logging.getLogger(__name__)


async def enrich_alternatives_via_jsonld(
    hass: HomeAssistant, alternatives: list[Alternative]
) -> None:
    """Backfill price/currency/image on alternatives via JSON-LD + meta tags.

    For each listing missing a price or image, fetch the page (curl_cffi Chrome
    impersonation, same as the tracker) and read a price from JSON-LD first,
    then Open Graph / microdata meta tags. Listings that already have both a
    price and an image are skipped (no fetch). A page that fails to fetch or has
    no usable price simply keeps price=None. Never overrides a price the AI
    already supplied. Fetches run concurrently under a small semaphore.

    Module-level (not just a coordinator method) so the live "Search & add"
    websocket path can price its candidates too, not only tracked products.
    """
    if not alternatives:
        return

    session = async_get_clientsession(hass)
    sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def _enrich_one(alt: Alternative) -> None:
        if alt.price is not None and alt.image_url:
            return
        async with sem:
            try:
                html = await fetch_html(alt.url, session=session)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("alt enrich: fetch failed for %s: %s", alt.url, err)
                return
            try:
                jsonld = try_jsonld(html, url=alt.url)
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "alt enrich: JSON-LD parse failed for %s", alt.url, exc_info=True
                )
                jsonld = None

            if alt.price is None and jsonld and jsonld.get("price"):
                alt.price = jsonld["price"]
                if jsonld.get("currency"):
                    alt.currency = jsonld["currency"]
                if jsonld.get("title"):
                    alt.title = jsonld["title"]
            # Meta/microdata fallback when JSON-LD has no price.
            if alt.price is None:
                meta_price, meta_currency = find_meta_price(html)
                if meta_price is not None:
                    alt.price = meta_price
                    if meta_currency and not alt.currency:
                        alt.currency = meta_currency
            image = (jsonld or {}).get("image_url") or find_meta_image(html)
            if image and not alt.image_url:
                alt.image_url = image

    await asyncio.gather(
        *(_enrich_one(alt) for alt in alternatives),
        return_exceptions=True,
    )


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
