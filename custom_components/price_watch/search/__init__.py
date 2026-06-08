"""Search provider registry and factory.

Mirrors `ai/__init__.py`: a small registry that lets the rest of the
integration construct search providers without importing them
directly. The coordinator picks a provider based on the entry's AI
provider configuration:

- AI provider = Anthropic AND key is present → AnthropicNativeSearchProvider
  (uses Anthropic's built-in web_search tool)
- AI provider = anything else (Ollama, OpenAI-compat) → AISynthesizerSearchProvider
  (DuckDuckGo HTML search + AI-driven filtering)
- No AI provider at all → DuckDuckGoSearchProvider (raw DDG hits, no AI
  cleanup — lowest quality but the feature still works)

This routing lives in the coordinator (build_search_provider helper),
not here, because the routing decision needs runtime state (which
AIProvider was built) that the search subpackage doesn't have.
"""

from __future__ import annotations

from .ai_synthesizer import AISynthesizerSearchProvider
from .anthropic_native import AnthropicNativeSearchProvider
from .base import (
    ALTERNATIVES_SYSTEM_PROMPT,
    ALTERNATIVES_TOOL_SCHEMA,
    Alternative,
    SearchProvider,
    SearchProviderAuthError,
    SearchProviderError,
    SearchProviderUnavailable,
    SearchQuery,
)
from .duckduckgo import DuckDuckGoSearchProvider, RawSearchHit
from .searxng import SearxngSearchProvider

# Search provider type identifiers — what gets stored if/when we ever
# expose a per-product "search provider override" option. For now,
# routing is implicit (based on AI provider) so these are just for
# logging/diagnostics.
SEARCH_PROVIDER_ANTHROPIC_NATIVE = "anthropic_native"
SEARCH_PROVIDER_AI_SYNTHESIZER = "ai_synthesizer"
SEARCH_PROVIDER_DUCKDUCKGO_RAW = "duckduckgo_raw"


__all__ = [
    "AISynthesizerSearchProvider",
    "ALTERNATIVES_SYSTEM_PROMPT",
    "ALTERNATIVES_TOOL_SCHEMA",
    "Alternative",
    "AnthropicNativeSearchProvider",
    "DuckDuckGoSearchProvider",
    "RawSearchHit",
    "SEARCH_PROVIDER_AI_SYNTHESIZER",
    "SEARCH_PROVIDER_ANTHROPIC_NATIVE",
    "SEARCH_PROVIDER_DUCKDUCKGO_RAW",
    "SearchProvider",
    "SearchProviderAuthError",
    "SearchProviderError",
    "SearchProviderUnavailable",
    "SearchQuery",
    "SearxngSearchProvider",
]
