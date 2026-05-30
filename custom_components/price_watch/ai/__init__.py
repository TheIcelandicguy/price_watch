"""AI provider registry and factory.

The integration constructs providers via `get_provider(provider_type, ...)`
rather than importing them directly, so adding a new provider (OpenAI-
compatible, Gemini, Ollama, etc.) only requires:

1. Implementing AIProvider in a new module
2. Registering it in PROVIDERS below
3. Exposing its config knobs in the config flow

Nothing else in the codebase needs to know about specific providers.
"""

from __future__ import annotations

from typing import Any

from .anthropic_provider import AnthropicProvider
from .anthropic_provider import PRICING_PER_MTOK as ANTHROPIC_PRICING
from .base import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_TOOL_SCHEMA,
    AIAuthenticationError,
    AIExtractionResult,
    AIProvider,
    AIProviderError,
)
from .openai_compat_provider import (
    DEFAULT_MAX_HTML_CHARS as OPENAI_COMPAT_DEFAULT_MAX_HTML_CHARS,
    OpenAICompatProvider,
)

# Provider type identifiers — what gets stored in the config entry.
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"

# All known providers. Adding a new one means adding an entry here and
# the corresponding import above. get_provider() forwards **kwargs
# straight to the class __init__, so each provider documents its own
# required/optional kwargs.
PROVIDERS: dict[str, type] = {
    PROVIDER_ANTHROPIC: AnthropicProvider,
    PROVIDER_OPENAI_COMPATIBLE: OpenAICompatProvider,
}


def list_provider_types() -> list[str]:
    """Return the registered provider type identifiers."""
    return list(PROVIDERS.keys())


def get_provider(provider_type: str, **config: Any) -> AIProvider:
    """Build an AIProvider instance from a type identifier and config.

    `config` is provider-specific. For Anthropic: api_key, model.
    Future providers will add their own kwargs (base_url, api_key,
    model for OpenAI-compat; api_key, model for Gemini; etc.).

    Raises KeyError if the provider type is unknown, and propagates
    whatever the provider's __init__ raises on bad config (typically
    ValueError for missing required fields).
    """
    if provider_type not in PROVIDERS:
        raise KeyError(
            f"Unknown AI provider type: {provider_type!r}. "
            f"Known: {sorted(PROVIDERS)}"
        )
    cls = PROVIDERS[provider_type]
    return cls(**config)


__all__ = [
    "AIAuthenticationError",
    "AIExtractionResult",
    "AIProvider",
    "AIProviderError",
    "ANTHROPIC_PRICING",
    "EXTRACTION_SYSTEM_PROMPT",
    "EXTRACTION_TOOL_SCHEMA",
    "OPENAI_COMPAT_DEFAULT_MAX_HTML_CHARS",
    "PROVIDER_ANTHROPIC",
    "PROVIDER_OPENAI_COMPATIBLE",
    "PROVIDERS",
    "get_provider",
    "list_provider_types",
]
