"""Search provider abstraction for Price Watch alternatives discovery.

Defines the interface every search backend implements. Mirrors the
`ai/` subpackage pattern: one Protocol + dataclass + errors + registry.

There are three flavors of search:

1. **Anthropic-native** — uses Claude's built-in `web_search_20250305`
   tool. One round-trip: model receives the query, decides to search,
   server-side executes the search, model synthesizes structured
   alternatives, returns to us. Highest quality, costs ~$0.01 + tokens
   per call (one ~$10/1k web_search use + ~3k input + ~1k output tokens).

2. **AI-synthesis over DuckDuckGo** — for providers without native web
   search (Ollama, OpenAI-compat without browsing). We hit DuckDuckGo's
   HTML lite endpoint (no API key required), extract top-N title+URL+
   snippet results, then feed those into the AI provider asking it to
   pick the best matches and structure them as Alternative objects.
   Free, less reliable than native search because the AI is working
   from snippets, not live pages.

3. **DuckDuckGo-only (no AI)** — return raw DDG snippets without any
   AI synthesis. Useful as a debugging path or when no AI provider is
   configured at all. Quality is lowest because there's no semantic
   filtering. Not exposed in the UI by default.

The caller (coordinator) picks the strategy based on which AI provider
the entry is configured to use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class SearchProviderError(Exception):
    """Raised by a search provider when it can't satisfy the request.

    Callers (coordinator) catch this to record the error onto the
    entry's persisted alternatives_error field, surface it via the
    sensor attribute, and continue without alternatives.
    """


class SearchProviderAuthError(SearchProviderError):
    """Raised when the provider's underlying credentials are rejected.

    Distinct so the coordinator can give a clearer error message
    ("API key invalid" vs "search failed").
    """


class SearchProviderUnavailable(SearchProviderError):
    """Raised when the provider can't run for environmental reasons.

    Examples: Anthropic web_search returns a credit-exhausted error,
    DuckDuckGo HTML endpoint is unreachable. Distinct from generic
    errors because the coordinator may want to fall back to a
    different provider type rather than report failure.
    """


@dataclass
class Alternative:
    """A single alternative product found by a search provider.

    All fields except `title` and `url` are optional because search
    quality varies: Anthropic-native can usually extract a price and
    retailer from the page it fetched; DuckDuckGo-snippet-based
    extraction often can't get a price reliably and may leave
    `price=None`. The panel renders "Price unknown — click to check"
    in that case.

    `confidence` is the model's self-reported confidence that this
    result is the SAME product (or a close substitute) — not just a
    similarly-named product. 0.0 = no signal, 1.0 = clearly the same
    SKU. The panel sorts by confidence DESC then price ASC.

    `notes` is short freeform text from the AI ("same SKU, ships from
    EU", "different timings — CL36 vs CL30", etc.). Shown as a
    tooltip in the panel.
    """

    title: str
    url: str
    price: float | None = None
    currency: str = ""
    retailer: str = ""
    image_url: str | None = None
    confidence: float = 0.0
    notes: str = ""
    # Whether this retailer ships to the user's region. None means
    # "unknown" (no signal from AI or heuristic) — rendered without
    # a badge. True/False are rendered as positive/negative badges.
    # Populated by the AI (soft signal) then overridden by the
    # backend heuristic for known retailer→region pairs (hard signal).
    ships_to_user_region: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for HA Store + sensor attributes (must be JSON-safe)."""
        return {
            "title": self.title,
            "url": self.url,
            "price": self.price,
            "currency": self.currency,
            "retailer": self.retailer,
            "image_url": self.image_url,
            "confidence": self.confidence,
            "notes": self.notes,
            "ships_to_user_region": self.ships_to_user_region,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alternative:
        """Deserialize from HA Store. Defensive — tolerates missing keys."""
        ships = data.get("ships_to_user_region")
        return cls(
            title=str(data.get("title", "")),
            url=str(data.get("url", "")),
            price=(float(data["price"]) if data.get("price") is not None else None),
            currency=str(data.get("currency", "")),
            retailer=str(data.get("retailer", "")),
            image_url=data.get("image_url"),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            notes=str(data.get("notes", "")),
            ships_to_user_region=(bool(ships) if ships is not None else None),
        )


@dataclass
class SearchQuery:
    """Input to a search provider.

    `title` is the product's display name (required). The provider
    may use other fields to rank/filter results: `current_price` lets
    the AI prefer cheaper alternatives; `currency` and `retailer`
    inform regional bias.

    `max_results` is a soft cap — providers may return fewer than
    requested if results are sparse.

    `region` is an optional regional hint ("worldwide", "nordic",
    "eu", "us"). The Anthropic-native provider can pass this into
    `user_location` on the web_search tool. The DDG-based providers
    use it to bias the query string ("CORSAIR Dominator ... Iceland
    Nordic site:.no OR site:.is OR site:.dk OR site:.se").
    """

    title: str
    current_price: float | None = None
    currency: str = ""
    retailer: str = ""
    max_results: int = 5
    region: str = "worldwide"
    # ISO 3166-1 alpha-2 country code (e.g. "IS", "NO", "US") for the
    # user's location, used to evaluate per-result shipping eligibility.
    # Empty string disables the shipping evaluation. Distinct from
    # `region` (which biases the search) because the user might want
    # to search Nordic-wide but only buy from retailers shipping to IS.
    user_region: str = ""
    # When True, run in *discovery* mode: `title` is a free-text search
    # query (not a known product), and the provider returns the most
    # relevant purchasable listings rather than "same SKU as X". Drives
    # the in-panel live search ("search products to track"). When False
    # (default), the strict same-SKU alternatives behavior is used.
    # See DISCOVERY_SYSTEM_PROMPT vs ALTERNATIVES_SYSTEM_PROMPT.
    discovery: bool = False


# Shared system prompt for the alternatives task. Used by both the
# Anthropic-native path and the AI-synthesis path, so the prompt is
# kept here rather than copied. The instruction emphasizes "same SKU"
# because the most common failure mode is the AI returning generic
# DDR5 32GB kits when we wanted that exact CORSAIR model.
ALTERNATIVES_SYSTEM_PROMPT = """You help users find alternative purchase options for a specific product they're already tracking. Your job is to identify retailers selling THE SAME product (preferably same SKU / model number / configuration) at potentially different prices.

CRITICAL: Be picky. Return only products that are clearly the same item or a near-identical configuration. Do NOT return random "similar" products in the same category.

Examples of what counts as the SAME product:
- Same SKU / model number, even if listed by a different retailer
- Same brand + product line + capacity + speed + timings (for memory)
- Same brand + model + storage variant (for SSDs / drives)
- Same brand + size + connector + length (for cables)

Examples of what does NOT count (do not return these):
- Different brand or model number, even if specs look similar
- Same brand but different capacity / speed / variant
- "Compatible with" or "alternative to" listings unless they're literally the same SKU
- Used / refurbished / open-box listings unless explicitly asked for

For each match, return: title (as shown on retailer page), url (direct product URL, not a search/category URL), price (number, no currency symbols), currency (ISO code or symbol), retailer (display name), image_url (if available), confidence (0.0-1.0 — how sure you are this is the same product), ships_to_user_region (true/false/null — see below), notes (short freeform: "same SKU, ships to Nordic countries" or "different timings, CL36 vs CL30 in original").

SHIPPING ELIGIBILITY: If the user's country code is provided in the prompt, set `ships_to_user_region` to indicate whether this retailer ships physical goods to that country:
- true: confident the retailer ships to the user's country (e.g. a `.is` retailer for an IS user, Amazon DE/UK/ES for an EU user, AliExpress/Banggood/eBay globally)
- false: confident the retailer does NOT ship to the user's country (e.g. Newegg US for an IS/EU user, Amazon US for many small electronics to non-US destinations, regional retailers outside their home region)
- null: genuinely unknown — don't guess

Be honest about uncertainty: when you don't know, return null rather than guessing. A best-guess false-positive (saying "yes" when actually no) is worse than a null because it sends the user on a wild click-through.

Return JSON only. If no good matches found, return an empty list."""


# System prompt for *discovery* search — the in-panel live search where
# the user types a free-text query and wants to find products to start
# tracking. Unlike ALTERNATIVES_SYSTEM_PROMPT, this is NOT picky about
# "same SKU" — there is no reference product. The job is to return the
# most relevant, currently-purchasable listings for an open query, the
# way a shopping search would. Reuses the same report_alternatives tool
# schema so providers and the panel need no new result shape.
DISCOVERY_SYSTEM_PROMPT = """You help users discover products to track for price changes. The user gives you a free-text search query (like a shopping search) and you find real, currently-purchasable product listings from online retailers that match it.

Return the most relevant matches as DIRECT product pages (not search, category, or comparison pages). Prefer well-known, reputable retailers and in-stock listings. Variety is good: if several retailers sell the queried item, return them so the user can pick which to track.

For each result, return: title (as shown on the retailer page), url (direct product URL), price (number, no currency symbols; null if you can't determine it), currency (ISO code or symbol), retailer (display name), image_url (if available), confidence (0.0-1.0 — how well this result matches the user's query), ships_to_user_region (true/false/null — see below), notes (short freeform: "official store", "marketplace listing", etc.).

SHIPPING ELIGIBILITY: If the user's country code is provided in the prompt, set `ships_to_user_region` to indicate whether this retailer ships physical goods to that country:
- true: confident the retailer ships to the user's country
- false: confident it does NOT ship there
- null: genuinely unknown — don't guess

A best-guess false-positive is worse than a null. Be honest about uncertainty.

Return JSON only via report_alternatives. If nothing relevant is found, return an empty list."""


# JSON schema for the tool / structured-output call that returns
# alternatives. Each provider translates this into its native shape.
ALTERNATIVES_TOOL_SCHEMA: dict[str, Any] = {
    "name": "report_alternatives",
    "description": "Report alternative product listings found via web search.",
    "parameters": {
        "type": "object",
        "properties": {
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "price": {"type": ["number", "null"]},
                        "currency": {"type": "string"},
                        "retailer": {"type": "string"},
                        "image_url": {"type": ["string", "null"]},
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "ships_to_user_region": {
                            "type": ["boolean", "null"],
                            "description": "Whether this retailer ships to the user's region. null = unknown.",
                        },
                        "notes": {"type": "string"},
                    },
                    "required": ["title", "url"],
                },
            },
        },
        "required": ["alternatives"],
    },
}


@runtime_checkable
class SearchProvider(Protocol):
    """Interface every search backend implements.

    Implementations live as async classes with these methods. Use the
    @runtime_checkable decorator so isinstance(x, SearchProvider) works
    for sanity checking, even though Protocol is structural.
    """

    name: str

    async def find_alternatives(self, query: SearchQuery) -> list[Alternative]:
        """Find alternative product listings for the given query.

        May raise SearchProviderError (or subclasses) if the search
        fails. Returns an empty list if the search succeeded but
        found no usable matches — distinct from failure.
        """
        ...

    async def aclose(self) -> None:
        """Release any held resources (HTTP sessions, etc.).

        Coordinators call this in their async_unload path. Default
        implementations may be no-ops.
        """
        ...
