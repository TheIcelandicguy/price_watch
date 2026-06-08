"""SearXNG search provider.

Queries a self-hosted (or any) SearXNG instance's JSON API and returns
raw search hits — the same ``RawSearchHit`` shape DuckDuckGoSearchProvider
returns, so SearXNG is a drop-in raw source for both the free path (hits
mapped straight to Alternatives) and the AI-synthesizer path (hits handed
to an AIProvider for same-SKU filtering + structuring).

Why SearXNG: it's a metasearch engine the user runs themselves (e.g. next
to their Ollama box). Unlike scraping ``html.duckduckgo.com`` it's an
actual JSON API — no HTML regexes to break, no rate-limiting/CAPTCHA from a
third party, and it aggregates Google/Bing/Brave/etc. The instance must have
the JSON format enabled (``search.formats: [html, json]`` in settings.yml).
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ..const import USER_AGENT
from .base import SearchProviderError, SearchProviderUnavailable, SearchQuery
from .duckduckgo import RawSearchHit

_LOGGER = logging.getLogger(__name__)

_SEARXNG_TIMEOUT_SEC = 12.0
_SEARXNG_MAX_RESPONSE_BYTES = 4_000_000


class SearxngSearchProvider:
    """Raw search via a SearXNG instance's JSON API.

    Mirrors DuckDuckGoSearchProvider: ``search()`` returns RawSearchHit
    objects; ``find_alternatives`` raises (it's a raw source, wrapped by the
    AI synthesizer or mapped directly in the free path).
    """

    name = "searxng"

    def __init__(
        self, base_url: str, session: aiohttp.ClientSession | None = None
    ) -> None:
        # Normalize: drop a trailing slash and any trailing /search the user
        # may have pasted, so we can always append "/search".
        url = (base_url or "").strip().rstrip("/")
        if url.endswith("/search"):
            url = url[: -len("/search")]
        self._base_url = url
        self._session = session

    async def search(self, query: str, max_results: int = 10) -> list[RawSearchHit]:
        """Run a SearXNG search; return up to ``max_results`` raw hits."""
        if self._session is None:
            raise SearchProviderError(
                "SearxngSearchProvider built without aiohttp session"
            )
        if not self._base_url:
            raise SearchProviderError("SearXNG base URL is not configured")

        data = await self._fetch_json(query)
        results = data.get("results")
        if not isinstance(results, list):
            return []

        hits: list[RawSearchHit] = []
        for r in results:
            if not isinstance(r, dict):
                continue
            url = str(r.get("url") or "").strip()
            title = str(r.get("title") or "").strip()
            if not url or not title:
                continue
            # Skip anything still pointing back at the SearXNG host itself.
            try:
                if urlparse(self._base_url).netloc and (
                    urlparse(url).netloc == urlparse(self._base_url).netloc
                ):
                    continue
            except (ValueError, TypeError):
                pass
            snippet = str(r.get("content") or "").strip()
            hits.append(RawSearchHit(title=title, url=url, snippet=snippet))
            if len(hits) >= max_results:
                break

        if not hits:
            _LOGGER.info("SearXNG returned 0 usable hits for %r", query)
        return hits

    async def _fetch_json(self, query: str) -> dict[str, Any]:
        assert self._session is not None
        params = {
            "q": query,
            "format": "json",
            "safesearch": "0",
            "categories": "general",
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            async with self._session.get(
                f"{self._base_url}/search",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=_SEARXNG_TIMEOUT_SEC),
            ) as resp:
                if resp.status == 429:
                    raise SearchProviderUnavailable(
                        "SearXNG returned 429 (rate-limited). Retry later."
                    )
                if resp.status == 403:
                    raise SearchProviderError(
                        "SearXNG returned 403 — the JSON format is likely "
                        "disabled. Add `json` to search.formats in settings.yml."
                    )
                if resp.status >= 400:
                    raise SearchProviderError(f"SearXNG HTTP {resp.status}")
                raw = await resp.text(errors="ignore")
                if len(raw) > _SEARXNG_MAX_RESPONSE_BYTES:
                    raw = raw[:_SEARXNG_MAX_RESPONSE_BYTES]
        except aiohttp.ClientError as err:
            raise SearchProviderError(f"SearXNG network error: {err}") from err

        import json as _json

        try:
            data = _json.loads(raw)
        except (ValueError, _json.JSONDecodeError) as err:
            # Most common cause: the instance served HTML because JSON isn't
            # enabled, or the URL points somewhere that isn't SearXNG.
            raise SearchProviderError(
                "SearXNG did not return JSON — check the URL and that the "
                "`json` format is enabled in the instance's settings.yml."
            ) from err
        if not isinstance(data, dict):
            raise SearchProviderError("SearXNG returned an unexpected payload")
        return data

    async def find_alternatives(self, query: SearchQuery) -> list[Any]:
        raise SearchProviderError(
            "SearxngSearchProvider returns raw hits, not Alternatives. Use it "
            "as the free-path source or via AISynthesizerSearchProvider."
        )

    async def aclose(self) -> None:
        # We don't own the session — the coordinator handles its lifecycle.
        pass
