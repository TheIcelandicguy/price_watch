"""Alternatives-discovery mixin for PriceWatchCoordinator.

Extracted from coordinator.py. The alternatives feature finds other
retailer listings of the same product so the user can compare prices.
It's a self-contained concern layered on top of the coordinator's core
update/persistence loop, so it lives here as a mixin the coordinator
inherits.

Two search implementations live in the search/ subpackage:

- AnthropicNativeSearchProvider: uses Claude's web_search tool.
  One round-trip, high quality, costs a few cents per call.
- AISynthesizerSearchProvider: free DuckDuckGo HTML search +
  AI synthesis (Ollama / OpenAI-compat). Lower quality because
  the AI works from snippets, but no Anthropic credit required.

The coordinator picks between them based on which AI provider it
built in __init__. The choice is implicit (no separate config
option for "search provider"), with the contract: "use whatever
is configured for AI extraction, in the most capable mode that
provider supports."

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
    CONF_MAX_ALTERNATIVES,
    DEFAULT_MAX_ALTERNATIVES,
    DEFAULT_MODEL,
)
from .search import (
    AISynthesizerSearchProvider,
    Alternative,
    AnthropicNativeSearchProvider,
    SearchProvider,
    SearchProviderError,
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
