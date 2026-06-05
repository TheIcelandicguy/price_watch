"""AI-provider resolution for Price Watch coordinators.

Extracted from coordinator.py. These two functions decide which
AIProvider (if any) a product entry should use, resolving credentials
across the product entry and the shared settings entry.

Kept as free functions (not methods) because they're pure functions of
(hass, entry) with no coordinator state — moving them here keeps the
coordinator focused on its update/persistence loop.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ai import (
    AIProvider,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI_COMPATIBLE,
    get_provider,
)
from .const import (
    CONF_AI_FALLBACK_ONLY,
    CONF_AI_PROVIDER,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_EXTRA_HEADERS,
    CONF_FORCE_JSON_MODE,
    CONF_INPUT_COST_PER_MTOK,
    CONF_MAX_HTML_CHARS,
    CONF_MODEL,
    CONF_OUTPUT_COST_PER_MTOK,
    DEFAULT_MODEL,
    ENTRY_TYPE_SETTINGS,
)

_LOGGER = logging.getLogger(__name__)


def _find_settings_entry(
    hass: HomeAssistant, domain: str
) -> ConfigEntry | None:
    """The shared Price Watch settings entry, or None if not set up yet."""
    for other in hass.config_entries.async_entries(domain):
        if other.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
            return other
    return None


def read_ai_fallback_only(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Whether the AI should be used ONLY as a price-extraction fallback.

    When True, alternatives discovery stays on free DuckDuckGo (no AI search)
    and the configured AI provider is reserved for reading a price when
    free/JSON-LD extraction fails. Global flag on the settings entry; a
    product entry may override. Default False.
    """
    for candidate in (entry, _find_settings_entry(hass, entry.domain)):
        if candidate is None:
            continue
        for src in (candidate.options, candidate.data):
            if CONF_AI_FALLBACK_ONLY in src:
                return bool(src[CONF_AI_FALLBACK_ONLY])
    return False


def build_ai_provider(
    hass: HomeAssistant, entry: ConfigEntry
) -> AIProvider | None:
    """Build the AIProvider for this entry, or None if not configured.

    Reads CONF_AI_PROVIDER to select between Anthropic and the
    OpenAI-compatible class. Falls back to Anthropic when unset so
    existing config entries (which predate the provider abstraction)
    keep working.

    Credential resolution:
    1. The product entry's own data/options (snapshotted at creation
       time by the config flow).
    2. The shared settings entry. This is a fallback for product
       entries that don't carry their own snapshot. Reading the
       settings entry live also means subsequent key/provider
       changes propagate automatically.
    """
    # Settings come from the product entry first, then fall back to
    # the shared settings entry.
    provider_type, config = resolve_provider_config(hass, entry)
    if provider_type is None:
        return None

    try:
        return get_provider(provider_type, **config)
    except Exception as err:  # noqa: BLE001
        # A failed provider build should NOT brick the coordinator —
        # JSON-LD extraction still works without AI. Log and continue.
        _LOGGER.warning(
            "Failed to build AI provider %s for %s: %s",
            provider_type, entry.entry_id, err,
        )
        return None


def resolve_provider_config(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[str | None, dict[str, Any]]:
    """Pick the provider type and assemble its constructor kwargs.

    Returns (provider_type, config_kwargs). provider_type is None
    when no credentials are available anywhere (i.e. the
    integration should operate in JSON-LD-only mode for this entry).

    The merge is "product entry overrides settings entry, options
    override data" — same precedence the rest of the integration
    uses. Empty-string and None are treated the same.
    """
    # Look up settings entry once, used as fallback throughout.
    settings_entry = _find_settings_entry(hass, entry.domain)

    # AI-config keys are read differently than product-specific keys
    # (url, target_price, custom_parser, cookies, etc.). For AI config,
    # we have to handle the case where the user changed the global
    # provider (settings entry) AFTER products were added. Each
    # product carries a frozen `data` snapshot from when it was
    # created — that snapshot's keys (especially `model`) become
    # stale when the settings entry switches provider.
    #
    # Rule: if the product entry has NO explicit AI override
    # (options.ai_provider not set), AI config is read from the
    # settings entry ONLY. The product's data snapshot is ignored
    # for AI keys. This way "no override" really means "inherit
    # whatever settings has now," not "inherit my creation-time
    # snapshot."
    #
    # If the product DOES have an explicit override (it set
    # options.ai_provider), we use product-first precedence so
    # the override can be fully self-contained.
    AI_CONFIG_KEYS = frozenset({
        CONF_AI_PROVIDER, CONF_API_KEY, CONF_MODEL, CONF_BASE_URL,
        CONF_INPUT_COST_PER_MTOK, CONF_OUTPUT_COST_PER_MTOK,
        CONF_MAX_HTML_CHARS, CONF_FORCE_JSON_MODE, CONF_EXTRA_HEADERS,
    })
    # A product is treated as having an explicit AI override if it
    # has SET ai_provider in its options, OR if it set any
    # significant AI config field. "Significant" excludes data-only
    # fields like cost-per-mtok (which exist on every entry by
    # default) and includes the bits that actually change provider
    # behavior. Without this, a user who set model+base_url in the
    # options flow but didn't set ai_provider would have their
    # work silently ignored.
    product_has_override = (
        entry.options.get(CONF_AI_PROVIDER) not in ("", None)
        or entry.options.get(CONF_MODEL) not in ("", None)
        or entry.options.get(CONF_BASE_URL) not in ("", None)
        or entry.options.get(CONF_API_KEY) not in ("", None)
    )

    def read(key: str, default: Any = None) -> Any:
        """Read a config value with appropriate precedence.

        Non-AI keys (url, cookies, custom_parser, target_price,
        scan_interval, etc.) always use product-first precedence:
          product.options > product.data > settings.options >
          settings.data > default

        AI-config keys behave one of two ways depending on
        whether the product has its own AI override:
        - With override (options.ai_provider set on product):
          same product-first precedence as above. Lets the
          override be fully self-contained.
        - Without override: settings entry only, ignoring the
          product's data snapshot. Keeps inheritance fresh when
          the global provider gets switched mid-life.
        """
        if key in AI_CONFIG_KEYS and not product_has_override:
            # Inheritance-only path. Skip product entry entirely
            # so its stale data snapshot can't shadow a current
            # settings value.
            if settings_entry is not None:
                if (
                    key in settings_entry.options
                    and settings_entry.options[key] not in ("", None)
                ):
                    return settings_entry.options[key]
                if (
                    key in settings_entry.data
                    and settings_entry.data[key] not in ("", None)
                ):
                    return settings_entry.data[key]
            return default

        # Normal product-first precedence.
        if key in entry.options and entry.options[key] not in ("", None):
            return entry.options[key]
        if key in entry.data and entry.data[key] not in ("", None):
            return entry.data[key]
        if settings_entry is not None:
            if key in settings_entry.options and settings_entry.options[key] not in ("", None):
                return settings_entry.options[key]
            if key in settings_entry.data and settings_entry.data[key] not in ("", None):
                return settings_entry.data[key]
        return default

    provider_type = read(CONF_AI_PROVIDER, PROVIDER_ANTHROPIC)

    if provider_type == PROVIDER_ANTHROPIC:
        api_key = read(CONF_API_KEY)
        if not api_key:
            _LOGGER.debug(
                "No Anthropic key for %s; AI extraction unavailable",
                entry.entry_id,
            )
            return None, {}
        return PROVIDER_ANTHROPIC, {
            "api_key": api_key,
            "model": read(CONF_MODEL, DEFAULT_MODEL),
        }

    if provider_type == PROVIDER_OPENAI_COMPATIBLE:
        # OpenAI-compatible needs base_url + model at minimum. api_key
        # is optional (local Ollama / LM Studio).
        base_url = read(CONF_BASE_URL)
        model = read(CONF_MODEL)
        if not base_url or not model:
            _LOGGER.warning(
                "OpenAI-compat provider needs base_url and model "
                "(have base_url=%r, model=%r); AI extraction "
                "unavailable for %s",
                base_url, model, entry.entry_id,
            )
            return None, {}
        return PROVIDER_OPENAI_COMPATIBLE, {
            "api_key": read(CONF_API_KEY),
            "model": model,
            "base_url": base_url,
            "input_cost_per_mtok": float(read(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0),
            "output_cost_per_mtok": float(read(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0),
            "max_html_chars": int(read(CONF_MAX_HTML_CHARS, 100_000) or 100_000),
            "force_json_mode": bool(read(CONF_FORCE_JSON_MODE, False)),
            "extra_headers": read(CONF_EXTRA_HEADERS),
        }

    _LOGGER.warning(
        "Unknown AI provider type %r for %s; AI extraction unavailable",
        provider_type, entry.entry_id,
    )
    return None, {}
