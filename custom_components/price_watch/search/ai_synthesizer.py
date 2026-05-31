"""AI synthesizer search provider — combines raw search with any AIProvider.

Pairs a DuckDuckGoSearchProvider with an existing AIProvider
(Anthropic, OpenAI-compatible, Ollama-via-OpenAI-compat). The flow:

1. DDG fetches top-N raw results for the product's title.
2. We hand the AI provider a JSON list of raw hits and ask it to
   select which are the same product (using ALTERNATIVES_SYSTEM_PROMPT)
   and return them via report_alternatives.
3. We parse the AI's tool call into Alternative objects.

This is the path used when the entry's AI provider is NOT Anthropic-
with-web-search. The most common case: Ollama (no web search) or
OpenAI-compat (web search support varies). The AI sees only the
title/url/snippet from DDG — it does NOT re-fetch retailer pages.
That means prices are extracted from snippets when present, otherwise
null. The panel surfaces "Click to verify" for null prices.

Trade-offs vs the Anthropic-native path:
- Pros: Free (DDG is free, Ollama is free); independent of Anthropic
  credit balance.
- Cons: Lower quality. AI is working from snippets, not live pages.
  Snippet content varies — sometimes contains a price, often doesn't.
  Local models (Ollama 4B) hallucinate more than Claude.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from ..ai.base import AIProvider, AIProviderError
from .base import (
    ALTERNATIVES_SYSTEM_PROMPT,
    ALTERNATIVES_TOOL_SCHEMA,
    DISCOVERY_SYSTEM_PROMPT,
    Alternative,
    SearchProviderError,
    SearchQuery,
)
from .duckduckgo import DuckDuckGoSearchProvider, RawSearchHit

_LOGGER = logging.getLogger(__name__)


# Cap on hits fed to the AI. More than ~15 results adds tokens without
# much marginal benefit — DDG's first page is usually the relevant
# matches anyway. Set higher than max_results so the AI has some
# rejected candidates to choose from.
_MAX_HITS_FOR_AI = 12

# Truncate per-hit snippet length. Snippets are usually <300 chars
# but some include long product descriptions. Trimming keeps the
# prompt token count predictable.
_MAX_SNIPPET_CHARS = 400

# Price-enrichment limits. After the AI synthesis step, we fetch each
# alternative URL (in parallel, capped) and try to extract a price
# from JSON-LD. This adds significant quality (DDG snippets often
# don't contain prices, especially for European retailers), at the
# cost of one HTTP request per alternative.
#
# Concurrency cap: 3 simultaneous fetches. Higher than that risks
# anti-bot challenges from retailers that share infra; lower hurts
# user-facing latency.
_ENRICH_MAX_CONCURRENT = 3
# Per-page fetch timeout. JSON-LD-bearing pages are usually <1s; 8s
# is generous enough for slow retailers without blocking the whole
# alternatives flow on one stuck request.
_ENRICH_FETCH_TIMEOUT_SEC = 8.0


def _coerce_ships(value: Any) -> bool | None:
    """Normalize the AI's ships_to_user_region field.

    Accepts a real bool, None, or stringy variants ("true"/"false"/
    "null"/"unknown"/""), returning bool | None. Anything weird
    becomes None — better to under-claim than over-claim shipping.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0"):
            return False
    return None


def _build_hits_payload(hits: list[RawSearchHit]) -> str:
    """Serialize raw hits into a compact JSON list for the AI prompt.

    We keep this as JSON rather than a freeform table because the AI
    is then more likely to preserve the URLs verbatim in its response
    (rather than retyping them, which is where hallucinations creep
    in). Snippets are truncated to control token count.
    """
    payload = []
    for hit in hits[:_MAX_HITS_FOR_AI]:
        snippet = hit.snippet
        if len(snippet) > _MAX_SNIPPET_CHARS:
            snippet = snippet[:_MAX_SNIPPET_CHARS] + "…"
        payload.append({"title": hit.title, "url": hit.url, "snippet": snippet})
    return json.dumps(payload, ensure_ascii=False)


def _build_user_prompt(query: SearchQuery, hits_json: str) -> str:
    """Compose the user prompt for the AI synthesis step.

    Includes the original product context, the regional preference,
    and the JSON list of search hits. Closes with an explicit
    instruction to call report_alternatives.
    """
    if query.discovery:
        bits = [f"Search query: {query.title}"]
    else:
        bits = [f"Original product: {query.title}"]
        if query.current_price is not None and query.currency:
            bits.append(
                f"Currently tracked at: {query.current_price} {query.currency} "
                f"({query.retailer or 'unknown retailer'})"
            )
        elif query.current_price is not None:
            bits.append(f"Currently tracked at: {query.current_price}")

    if query.region and query.region != "worldwide":
        bits.append(f"Regional preference: {query.region}")

    if query.user_region:
        bits.append(
            f"User's country code (ISO 3166-1 alpha-2): {query.user_region}. "
            "For each result, set ships_to_user_region based on whether "
            "the retailer ships physical goods to this country. Use null when "
            "genuinely uncertain - do not guess."
        )

    bits.append("")
    bits.append("Web search returned these candidates (JSON):")
    bits.append(hits_json)
    bits.append("")
    if query.discovery:
        bits.append(
            f"From the candidates above, pick up to {query.max_results} real, "
            "currently-purchasable product listings that best match the search "
            "query. Prefer direct product pages over search/category pages. "
            "Use ONLY the URLs from the candidates list — do not invent URLs. "
            "Extract price from the snippet when possible; leave price null when "
            "you can't determine it. Call report_alternatives with your selections."
        )
    else:
        bits.append(
            f"From the candidates above, pick up to {query.max_results} that "
            "are clearly the SAME product (same SKU / model number / "
            "configuration). Reject random similar-but-different items. "
            "Use ONLY the URLs from the candidates list — do not invent "
            "URLs. Extract price from the snippet when possible; leave "
            "price null when you can't determine it. Call "
            "report_alternatives with your selections."
        )
    return "\n".join(bits)


class AISynthesizerSearchProvider:
    """SearchProvider that combines DDG + any AIProvider.

    Drop-in replacement for AnthropicNativeSearchProvider when the
    underlying AI provider doesn't have native web search.
    """

    name = "ai_synthesizer"

    def __init__(
        self,
        ai_provider: AIProvider,
        session: aiohttp.ClientSession,
    ) -> None:
        if ai_provider is None:
            raise ValueError(
                "AISynthesizerSearchProvider requires an AI provider"
            )
        self._ai = ai_provider
        self._session = session
        self._ddg = DuckDuckGoSearchProvider(session=session)

    async def find_alternatives(self, query: SearchQuery) -> list[Alternative]:
        """Two-step: DDG search, then AI synthesis."""
        # Step 1 — get raw search hits. Build a query string that
        # encourages matches — include "buy" so we bias toward
        # retailer pages over review/spec pages. (Not appended for
        # the "same SKU" filtering, just for the DDG search input.)
        ddg_query = f"{query.title} buy"
        if query.region and query.region != "worldwide":
            ddg_query += f" {query.region}"

        try:
            hits = await self._ddg.search(ddg_query, max_results=_MAX_HITS_FOR_AI)
        except SearchProviderError:
            # Bubble up — caller wraps for user-facing reporting.
            raise
        if not hits:
            _LOGGER.info(
                "AISynthesizer: DDG returned 0 hits for %r", query.title
            )
            return []

        # Step 2 — feed hits to the AI for synthesis. We piggyback on
        # the AIProvider's call_with_tool method (every provider in
        # the ai/ subpackage exposes one for the extraction path).
        hits_json = _build_hits_payload(hits)
        user_prompt = _build_user_prompt(query, hits_json)

        system_prompt = (
            DISCOVERY_SYSTEM_PROMPT if query.discovery else ALTERNATIVES_SYSTEM_PROMPT
        )
        try:
            result_data = await self._call_ai(user_prompt, system_prompt)
        except AIProviderError as err:
            raise SearchProviderError(f"AI synthesis failed: {err}") from err

        alternatives = self._parse_alternatives(
            result_data, query.max_results, hits
        )

        # Price enrichment: fill in missing prices by fetching each
        # retailer page and parsing JSON-LD. Snippet-only extraction
        # often leaves prices null (especially for European retailers
        # whose product pages don't surface price in meta tags). This
        # round-trip per URL recovers most of them.
        await self._enrich_prices(alternatives)

        # Region heuristic: override the AI's ships_to_user_region
        # guess where we have ground-truth knowledge (Newegg won't
        # ship to IS, .is TLD definitely ships to IS, etc.). Applied
        # after enrichment so it's the last word on the field. The
        # heuristic is a no-op when query.user_region is empty.
        if query.user_region:
            from .region_heuristic import apply_to_alternative
            for alt in alternatives:
                apply_to_alternative(alt, query.user_region)

        return alternatives

    async def _enrich_prices(self, alternatives: list[Alternative]) -> None:
        """Fill in missing prices by fetching retailer pages for JSON-LD.

        Mutates `alternatives` in place: alternatives that already have
        a price are left untouched; those with price=None get one
        attempt at JSON-LD extraction from a live fetch. Failures
        leave the price as None (better than a hallucinated value).

        Concurrent up to _ENRICH_MAX_CONCURRENT, per-fetch timeout
        _ENRICH_FETCH_TIMEOUT_SEC. Total worst-case time is bounded
        by ceil(N/_ENRICH_MAX_CONCURRENT) * timeout — for 5 alts and
        cap=3, max ~16s.

        Currency: when JSON-LD provides a currency we adopt it over
        the AI's guess (JSON-LD is authoritative; the AI was working
        from a snippet that often doesn't mention currency).
        """
        targets = [a for a in alternatives if a.price is None and a.url]
        if not targets:
            return

        # Import lazily to avoid a circular import: extractor imports
        # from .ai indirectly, and ai/search depend on this module.
        # At call time the import graph is settled.
        from ..extractor import fetch_html, try_jsonld

        sem = asyncio.Semaphore(_ENRICH_MAX_CONCURRENT)

        async def _enrich_one(alt: Alternative) -> None:
            async with sem:
                try:
                    html = await asyncio.wait_for(
                        fetch_html(alt.url, self._session),
                        timeout=_ENRICH_FETCH_TIMEOUT_SEC,
                    )
                except asyncio.TimeoutError:
                    _LOGGER.debug(
                        "Price enrichment timeout for %s", alt.url
                    )
                    return
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Price enrichment fetch failed for %s: %s",
                        alt.url, err,
                    )
                    return

                if not html:
                    return

                try:
                    ld = try_jsonld(html)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "JSON-LD parse failed for %s: %s", alt.url, err
                    )
                    return

                if not ld or ld.get("price") is None:
                    return

                # Got a price from JSON-LD — adopt it. Also adopt
                # the JSON-LD currency since it's authoritative.
                try:
                    price_val = float(ld["price"])
                except (TypeError, ValueError):
                    return
                # Sanity bound: reject zero or absurdly low prices
                # (sometimes retailer pages publish "0.0" as a default
                # when the actual price is loaded dynamically).
                if price_val <= 0:
                    return
                alt.price = price_val
                ld_currency = ld.get("currency")
                if ld_currency:
                    alt.currency = str(ld_currency)
                _LOGGER.info(
                    "Enriched %s with price=%s %s",
                    alt.url, alt.price, alt.currency,
                )

        await asyncio.gather(
            *(_enrich_one(a) for a in targets),
            return_exceptions=True,
        )

        # Re-sort after enrichment so price-bearing rows aren't stuck
        # at the bottom of a confidence tie group.
        alternatives.sort(
            key=lambda a: (
                -a.confidence,
                a.price if a.price is not None else float("inf"),
            )
        )

    async def _call_ai(
        self, user_prompt: str, system_prompt: str = ALTERNATIVES_SYSTEM_PROMPT
    ) -> dict[str, Any]:
        """Invoke the AI provider with the alternatives tool schema.

        Each AIProvider implementation exposes a generic interface
        for one-shot tool calls. We call the same low-level method
        used by the extraction path but with our alternatives schema
        and system prompt. `system_prompt` differs between the strict
        same-SKU alternatives task and the open discovery search.

        Returns the raw input dict that the AI passed to
        report_alternatives.
        """
        # Both AnthropicProvider and OpenAICompatProvider expose
        # `call_with_tool` — a common helper we add for this purpose
        # (not previously needed because extraction had a dedicated
        # method per provider). For now we route through whichever
        # method exists. If neither does, raise a clear error so
        # we can wire it up.
        if hasattr(self._ai, "call_with_tool"):
            return await self._ai.call_with_tool(  # type: ignore[attr-defined]
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tool_schema=ALTERNATIVES_TOOL_SCHEMA,
            )

        raise SearchProviderError(
            f"AI provider {type(self._ai).__name__} does not implement "
            "call_with_tool() — required for alternatives synthesis. "
            "See ai/ subpackage for adding the generic tool-call hook."
        )

    @staticmethod
    def _parse_alternatives(
        payload: dict[str, Any],
        max_results: int,
        original_hits: list[RawSearchHit],
    ) -> list[Alternative]:
        """Convert the AI's tool input into Alternative objects.

        Guards against the AI inventing URLs by validating each
        returned URL appears in the original hits list. Hallucinated
        URLs are silently dropped — preferring fewer trustworthy
        results over more results with broken links.
        """
        items_raw = payload.get("alternatives", [])
        if not isinstance(items_raw, list):
            _LOGGER.warning(
                "AISynthesizer: AI returned non-list alternatives: %r",
                type(items_raw),
            )
            return []

        # Build a set of valid URLs from the DDG hits for verification.
        valid_urls = {hit.url for hit in original_hits}

        out: list[Alternative] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue

            # Reject URLs the AI invented (not in the hit list).
            if url not in valid_urls:
                _LOGGER.debug(
                    "AISynthesizer: dropping hallucinated URL: %s", url
                )
                continue

            price_raw = item.get("price")
            price: float | None
            if price_raw is None:
                price = None
            else:
                try:
                    price = float(price_raw)
                except (TypeError, ValueError):
                    price = None

            conf_raw = item.get("confidence", 0.0)
            try:
                confidence = max(0.0, min(1.0, float(conf_raw)))
            except (TypeError, ValueError):
                confidence = 0.0

            out.append(
                Alternative(
                    title=title,
                    url=url,
                    price=price,
                    currency=str(item.get("currency", "") or ""),
                    retailer=str(item.get("retailer", "") or ""),
                    image_url=item.get("image_url"),
                    confidence=confidence,
                    notes=str(item.get("notes", "") or ""),
                    ships_to_user_region=_coerce_ships(
                        item.get("ships_to_user_region")
                    ),
                )
            )
            if len(out) >= max_results:
                break

        out.sort(
            key=lambda a: (
                -a.confidence,
                a.price if a.price is not None else float("inf"),
            )
        )
        return out

    async def aclose(self) -> None:
        await self._ddg.aclose()
        # We don't close the AIProvider — coordinator owns it.
