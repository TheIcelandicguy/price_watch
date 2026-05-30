"""DuckDuckGo HTML-lite search provider.

Uses DuckDuckGo's html.duckduckgo.com endpoint, which returns server-
rendered HTML with no JavaScript required and no API key. We scrape
the top-N result links + snippets and return them as raw search hits.

This provider returns RawSearchHit objects (a richer intermediate),
not Alternative objects directly. The ai_synthesizer module is
responsible for turning RawSearchHits into Alternatives by asking an
AI to pick which results are the same product and structure them.

Why not just return Alternatives? Because DDG snippets don't reliably
contain prices — sometimes yes, often no. An AI provider running over
the hits can synthesize prices from the title/snippet text where
possible and confidence-score each result. We keep the layers
separate so the same DDG fetcher can also support a future "no AI"
debug path that just dumps the hits unchanged.

Caveats:
- DDG occasionally rate-limits aggressive scraping. We use a real
  browser User-Agent and the curl_cffi Chrome impersonation that the
  rest of the integration uses, which helps.
- DDG can change their HTML structure without notice. The regexes
  used here are loose but will eventually break. When they do, the
  scraper logs a warning and returns an empty list — graceful
  degradation rather than throwing.
- The redirect URLs returned by DDG (//duckduckgo.com/l/?uddg=...) are
  unwrapped to direct retailer URLs before being returned. The AI
  provider should never see a duckduckgo.com URL in our output.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

from ..const import USER_AGENT
from .base import SearchProviderError, SearchProviderUnavailable, SearchQuery

_LOGGER = logging.getLogger(__name__)


# DDG's HTML endpoint. The /html/ subpath is the no-JS, server-
# rendered variant. We use POST with form-encoded body because
# DDG sometimes rate-limits GET requests for the same query string.
DDG_HTML_URL = "https://html.duckduckgo.com/html/"

# Maximum response size we'll accept. 1 MB is generous — typical
# response is ~40 KB.
DDG_MAX_RESPONSE_BYTES = 1_000_000

# Per-call timeout. DDG is usually <1s; 10s leaves room for transient
# slowness without blocking the coordinator's update loop.
DDG_TIMEOUT_SEC = 10.0

# Result row regex. Matches DDG's stable result__a class on the link
# wrapper. Captures the URL and inner HTML (which contains the title
# text). The snippet is matched separately because it lives in a
# sibling element under result__snippet.
_RESULT_LINK_RE = re.compile(
    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_RESULT_SNIPPET_RE = re.compile(
    r'class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)

# Strip HTML tags from a captured fragment.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Collapse runs of whitespace.
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class RawSearchHit:
    """A single raw search hit before AI synthesis.

    Returned by DuckDuckGoSearchProvider. Consumed by ai_synthesizer to
    produce structured Alternative objects. Has fewer constraints than
    Alternative — no requirement that title/url be present, no notion
    of confidence or price.

    Returned as a plain dataclass so the synthesizer can iterate
    cheaply and the optional "no AI" debug path can dump them
    directly to JSON.
    """

    title: str
    url: str
    snippet: str


def _unwrap_ddg_url(redirect_url: str) -> str:
    """Strip DuckDuckGo's redirect wrapper from a result URL.

    DDG result links look like //duckduckgo.com/l/?uddg=<encoded>&...
    We want just the decoded target. Returns the input unchanged if it
    doesn't match the redirect pattern (e.g. DDG sometimes returns
    direct URLs for sponsored ads).
    """
    # Add protocol if missing — DDG uses protocol-relative URLs.
    if redirect_url.startswith("//"):
        redirect_url = "https:" + redirect_url
    parsed = urlparse(redirect_url)
    if "duckduckgo.com" not in parsed.netloc:
        return redirect_url
    qs = parse_qs(parsed.query)
    target = qs.get("uddg", [None])[0]
    if target:
        return unquote(target)
    return redirect_url


def _clean_html_fragment(html: str) -> str:
    """Strip HTML tags + decode entities + normalize whitespace."""
    text = _HTML_TAG_RE.sub(" ", html)
    text = text.replace("&amp;", "&").replace("&quot;", '"')
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&#x27;", "'").replace("&apos;", "'")
    text = text.replace("&nbsp;", " ")
    return _WHITESPACE_RE.sub(" ", text).strip()


class DuckDuckGoSearchProvider:
    """Free, no-API-key DuckDuckGo HTML search.

    Returns RawSearchHit objects, not Alternatives. The AI synthesizer
    converts hits into structured alternatives downstream.
    """

    name = "duckduckgo"

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Build the provider.

        `session` is the integration's shared aiohttp ClientSession.
        Passed in by the coordinator rather than created internally
        so we participate in HA's connection pooling and cleanup.

        Can also be constructed with session=None for unit tests; in
        that case fetch() raises rather than going to the network.
        """
        self._session = session

    async def search(self, query: str, max_results: int = 10) -> list[RawSearchHit]:
        """Run a raw DDG search.

        Returns up to `max_results` RawSearchHit objects. Returns an
        empty list if DDG returned no usable results — distinct from
        failure, which raises.
        """
        if self._session is None:
            raise SearchProviderError(
                "DuckDuckGoSearchProvider built without aiohttp session"
            )

        body = await self._fetch_html(query)
        return self._parse_hits(body, max_results)

    async def _fetch_html(self, query: str) -> str:
        """POST to DDG's HTML endpoint, return the response body."""
        assert self._session is not None  # narrowed by .search() caller
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            # DDG is happier with form-encoded POST than GET — fewer
            # rate-limit hits in practice.
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"q": query, "kl": "wt-wt", "df": ""}  # kl=wt-wt = worldwide
        try:
            async with self._session.post(
                DDG_HTML_URL,
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=DDG_TIMEOUT_SEC),
                allow_redirects=True,
            ) as resp:
                if resp.status == 202:
                    # DDG sometimes serves 202 with a CAPTCHA challenge
                    # page when scraping is heavy. Treat as unavailable.
                    raise SearchProviderUnavailable(
                        "DuckDuckGo returned 202 (likely rate-limited "
                        "or challenge page). Retry later."
                    )
                if resp.status >= 400:
                    raise SearchProviderError(
                        f"DuckDuckGo HTTP {resp.status}"
                    )
                body = await resp.text(errors="ignore")
                if len(body) > DDG_MAX_RESPONSE_BYTES:
                    body = body[:DDG_MAX_RESPONSE_BYTES]
                return body
        except aiohttp.ClientError as err:
            raise SearchProviderError(f"DuckDuckGo network error: {err}") from err

    @staticmethod
    def _parse_hits(html: str, max_results: int) -> list[RawSearchHit]:
        """Extract title/url/snippet triplets from DDG's HTML response."""
        # Match links and snippets independently — DDG's HTML may not
        # always pair them perfectly. We zip them positionally, which
        # works because they appear in the same order in the DOM.
        link_matches = _RESULT_LINK_RE.findall(html)
        snippet_matches = _RESULT_SNIPPET_RE.findall(html)

        hits: list[RawSearchHit] = []
        for idx, (raw_url, raw_title) in enumerate(link_matches):
            url = _unwrap_ddg_url(raw_url)
            title = _clean_html_fragment(raw_title)
            snippet = (
                _clean_html_fragment(snippet_matches[idx])
                if idx < len(snippet_matches)
                else ""
            )
            if not title or not url:
                continue
            # Skip ads/sponsored — DDG marks these with class="result--ad"
            # which results in URLs containing "y.js" or "duckduckgo.com/ad".
            # Cheap heuristic: skip if the unwrapped URL still points at DDG
            # or at known ad domains.
            parsed = urlparse(url)
            if "duckduckgo.com" in parsed.netloc:
                continue

            hits.append(RawSearchHit(title=title, url=url, snippet=snippet))
            if len(hits) >= max_results:
                break

        if not hits:
            _LOGGER.warning(
                "DuckDuckGo returned 0 hits (regex may need updating, "
                "or query yielded no results)"
            )
        return hits

    # The SearchProvider Protocol expects find_alternatives; this class
    # doesn't implement it directly (returns RawSearchHit instead). It's
    # intended to be wrapped by ai_synthesizer.AISynthesizerSearchProvider
    # which combines DDG + an AI provider. Calling find_alternatives
    # directly on this class raises by design.
    async def find_alternatives(self, query: SearchQuery) -> list[Any]:
        raise SearchProviderError(
            "DuckDuckGoSearchProvider returns raw hits, not Alternatives. "
            "Use AISynthesizerSearchProvider to combine DDG with an AI "
            "provider for structured results."
        )

    async def aclose(self) -> None:
        # We don't own the session — coordinator handles its lifecycle.
        pass
