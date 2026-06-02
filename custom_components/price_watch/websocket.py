"""WebSocket API for the Price Watch panel — live product search.

The panel's "Search & add" feature sends a `price_watch/search` command
with a free-text query; we run a *discovery* search synchronously and
return ranked results in the WS reply. This is deliberately different
from the `find_alternatives` service (which is fire-and-forget and
writes results onto entity attributes): the panel needs the results
back at the caller, and a WS command returns them in its reply without
having to teach the frontend to read service-response data.

Backend selection is automatic, mirroring the coordinator's strategy:
  - Settings provider = Anthropic with an API key  → Claude's native
    `web_search` tool (highest quality).
  - Settings provider = OpenAI-compatible          → DuckDuckGo + AI
    synthesis over the raw hits.
  - No usable AI provider (the "Free" choice)       → raw DuckDuckGo
    hits, no AI cleanup (title/url/snippet only, no price/confidence).

The reply shape is:
    {"engine": "anthropic_native" | "ai_synthesizer" | "duckduckgo",
     "results": [<Alternative.to_dict()>, ...]}
so the panel can reuse its existing Alternative rendering and badge the
result quality by engine if it wants.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .ai import (
    AIAuthenticationError,
    AIProviderError,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI_COMPATIBLE,
    get_provider,
)
from .const import (
    ANTHROPIC_MODELS,
    CONF_AI_PROVIDER,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_EXCLUDED_DOMAINS,
    CONF_EXTRA_HEADERS,
    CONF_FORCE_JSON_MODE,
    CONF_INPUT_COST_PER_MTOK,
    CONF_MAX_HTML_CHARS,
    CONF_MODEL,
    CONF_OUTPUT_COST_PER_MTOK,
    CONF_USER_REGION,
    DEFAULT_MODEL,
    DOMAIN,
    ENTRY_TYPE_SETTINGS,
)
from .coordinator_alternatives import (
    _host_excluded,
    _is_non_shop_domain,
    _normalize_domain,
)
from .search.ai_synthesizer import AISynthesizerSearchProvider
from .search.anthropic_native import AnthropicNativeSearchProvider
from .search.base import (
    Alternative,
    SearchProviderAuthError,
    SearchProviderError,
    SearchProviderUnavailable,
    SearchQuery,
)
from .search.duckduckgo import DuckDuckGoSearchProvider

_LOGGER = logging.getLogger(__name__)

# Hard cap so a panel bug or hostile client can't request a huge search.
_MAX_RESULTS_CAP = 20
_DEFAULT_MAX_RESULTS = 8

# Per-hit snippet length we forward in the DDG-only fallback (no AI to
# summarize, so we hand the raw snippet to the panel as `notes`).
_DDG_SNIPPET_CHARS = 220


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the panel's WebSocket commands. Idempotent.

    Safe to call from every product entry's async_setup_entry — HA's
    command registry replaces a same-typed handler rather than erroring,
    so repeated registration is a no-op in practice.
    """
    websocket_api.async_register_command(hass, ws_search)
    websocket_api.async_register_command(hass, ws_get_provider_settings)
    websocket_api.async_register_command(hass, ws_set_provider_settings)
    websocket_api.async_register_command(hass, ws_test_selector)
    websocket_api.async_register_command(hass, ws_list_variants)
    websocket_api.async_register_command(hass, ws_exclude_domain)


def _settings_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the Price Watch settings config entry, if one exists."""
    entry_id = hass.data.get(DOMAIN, {}).get("settings")
    if not entry_id:
        return None
    return hass.config_entries.async_get_entry(entry_id)


def _read_setting(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Read a setting, options taking precedence over data.

    Mirrors config_flow._read_setting — the settings entry stores
    initial values in data and option-flow overrides in options.
    """
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


def _read_excluded_domains(entry: ConfigEntry | None) -> list[str]:
    """Return the settings entry's excluded-domain list, normalized.

    Stored as a list of host strings on the settings entry options.
    Normalized to bare lowercase hosts (www./scheme/path stripped) and
    de-duplicated while preserving order so the panel shows a clean,
    stable list.
    """
    if entry is None:
        return []
    raw = _read_setting(entry, CONF_EXCLUDED_DOMAINS)
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        norm = _normalize_domain(str(item))
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _build_ai_provider(entry: ConfigEntry):
    """Build an AIProvider from the settings entry, or None for Free.

    Returns None when the configured provider can't be built (e.g. the
    "Free" choice = Anthropic with no key, or an OpenAI-compat entry
    missing base_url/model). The caller falls back to DuckDuckGo-only.
    """
    provider_type = _read_setting(entry, CONF_AI_PROVIDER, PROVIDER_ANTHROPIC)
    try:
        if provider_type == PROVIDER_ANTHROPIC:
            api_key = _read_setting(entry, CONF_API_KEY)
            if api_key:
                return get_provider(
                    PROVIDER_ANTHROPIC,
                    api_key=api_key,
                    model=_read_setting(entry, CONF_MODEL, DEFAULT_MODEL),
                )
        elif provider_type == PROVIDER_OPENAI_COMPATIBLE:
            base_url = _read_setting(entry, CONF_BASE_URL)
            model = _read_setting(entry, CONF_MODEL)
            if base_url and model:
                return get_provider(
                    PROVIDER_OPENAI_COMPATIBLE,
                    api_key=_read_setting(entry, CONF_API_KEY),
                    model=model,
                    base_url=base_url,
                    input_cost_per_mtok=float(
                        _read_setting(entry, CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0
                    ),
                    output_cost_per_mtok=float(
                        _read_setting(entry, CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0
                    ),
                    max_html_chars=int(
                        _read_setting(entry, CONF_MAX_HTML_CHARS, 100_000) or 100_000
                    ),
                    force_json_mode=bool(
                        _read_setting(entry, CONF_FORCE_JSON_MODE, False)
                    ),
                    extra_headers=_read_setting(entry, CONF_EXTRA_HEADERS),
                )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to build AI provider for panel search")
    return None


@websocket_api.websocket_command(
    {
        vol.Required("type"): "price_watch/search",
        vol.Required("query"): str,
        vol.Optional("max_results", default=_DEFAULT_MAX_RESULTS): vol.All(
            int, vol.Range(min=1, max=_MAX_RESULTS_CAP)
        ),
    }
)
@websocket_api.async_response
async def ws_search(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run a discovery product search and return ranked results.

    Reply: {"engine": <str>, "results": [Alternative.to_dict(), ...]}.
    On failure, sends a typed WS error so the panel can show a message.
    """
    query_text = (msg.get("query") or "").strip()
    if not query_text:
        connection.send_result(msg["id"], {"engine": "none", "results": []})
        return

    max_results: int = msg["max_results"]
    session = async_get_clientsession(hass)

    settings = _settings_entry(hass)
    user_region = ""
    ai_provider = None
    if settings is not None:
        user_region = str(_read_setting(settings, CONF_USER_REGION, "") or "")
        ai_provider = _build_ai_provider(settings)

    query = SearchQuery(
        title=query_text,
        max_results=max_results,
        user_region=user_region,
        discovery=True,
    )

    # Pick the engine. Sniff the AI provider's concrete class the same
    # way the coordinator does: AnthropicProvider supports native web
    # search; anything else goes through DDG + AI synthesis; no provider
    # at all falls back to raw DDG hits.
    provider: Any
    engine: str
    if ai_provider is None:
        provider = DuckDuckGoSearchProvider(session=session)
        engine = "duckduckgo"
    elif type(ai_provider).__name__ == "AnthropicProvider":
        provider = AnthropicNativeSearchProvider(
            api_key=_read_setting(settings, CONF_API_KEY),
            model=_read_setting(settings, CONF_MODEL, DEFAULT_MODEL),
        )
        engine = "anthropic_native"
    else:
        provider = AISynthesizerSearchProvider(
            ai_provider=ai_provider, session=session
        )
        engine = "ai_synthesizer"

    try:
        if engine == "duckduckgo":
            hits = await provider.search(query_text, max_results=max_results)
            results = []
            for hit in hits:
                if not hit.url:
                    continue
                row = Alternative(
                    title=hit.title,
                    url=hit.url,
                    notes=(hit.snippet or "")[:_DDG_SNIPPET_CHARS],
                ).to_dict()
                # Free mode has no AI to name the retailer or read a price,
                # so surface the bare domain as the retailer and flag the
                # obvious non-shops (GitHub/YouTube/wiki/docs) — that's the
                # only "is this a seller?" signal we can give without AI.
                row["retailer"] = _normalize_domain(hit.url)
                row["likely_non_shop"] = _is_non_shop_domain(hit.url)
                results.append(row)
            results = results[:max_results]
        else:
            alternatives = await provider.find_alternatives(query)
            results = [alt.to_dict() for alt in alternatives]
    except SearchProviderAuthError as err:
        connection.send_error(msg["id"], "search_auth_failed", str(err))
        return
    except SearchProviderUnavailable as err:
        connection.send_error(msg["id"], "search_unavailable", str(err))
        return
    except SearchProviderError as err:
        connection.send_error(msg["id"], "search_failed", str(err))
        return
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Panel search failed for %r", query_text)
        connection.send_error(msg["id"], "search_failed", str(err))
        return
    finally:
        # Release the search provider's own resources (DDG session,
        # AnthropicNative SDK client). The synthesizer's aclose only
        # closes its DDG child, not the shared AIProvider — that's
        # intentional; the AIProvider holds no long-lived resource we
        # own here (matches config_flow's per-call provider usage).
        try:
            await provider.aclose()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error closing search provider", exc_info=True)

    # Honor the global domain blocklist for live search too, so excluded
    # retailers never show up as "Search & add" candidates either.
    excluded = set(_read_excluded_domains(settings))
    if excluded:
        results = [
            r for r in results if not _host_excluded(str(r.get("url") or ""), excluded)
        ]

    connection.send_result(msg["id"], {"engine": engine, "results": results})


# ---------------------------------------------------------------------------
# Provider settings editor (panel "AI provider" dialog).
#
# The panel lets the user switch the global AI provider — Free (no AI),
# Anthropic, or any OpenAI-compatible endpoint (Ollama, LM Studio, etc.) —
# without leaving for HA's Settings → Devices & Services options flow. The
# get/set pair below reads and writes the *settings* config entry's options,
# which provider_config.resolve_provider_config reads when each product
# coordinator builds its AIProvider. Because coordinators cache that
# provider at construction, set_provider_settings reloads the product
# entries so the change takes effect immediately.
# ---------------------------------------------------------------------------

# Panel-side label for "Free / no AI". Stored as anthropic + null key,
# mirroring config_flow._free_config(). The panel never sees the raw
# provider sentinel mismatch because get/set translate both ways.
_PANEL_PROVIDER_NONE = "none"

# Defaults applied to the OpenAI-compat/advanced fields when switching to
# a provider that doesn't use them (Free / Anthropic), so stale endpoint
# config can't shadow a later switch. Matches config_flow._OPENAI_CLEARED.
_DEFAULT_MAX_HTML_CHARS = 100_000


def _current_provider_state(entry: ConfigEntry | None) -> dict[str, Any]:
    """Summarize the settings entry's AI provider for the panel editor.

    SECURITY: never returns the raw API key — only ``has_api_key``. The
    base_url, model, and cost/advanced fields are non-secret and returned
    verbatim so the editor can prefill them.
    """
    models = list(ANTHROPIC_MODELS)
    if entry is None:
        return {
            "provider": _PANEL_PROVIDER_NONE,
            "model": DEFAULT_MODEL,
            "base_url": "",
            "has_api_key": False,
            "input_cost_per_mtok": 0.0,
            "output_cost_per_mtok": 0.0,
            "max_html_chars": _DEFAULT_MAX_HTML_CHARS,
            "force_json_mode": False,
            "extra_headers": "",
            "anthropic_models": models,
            "excluded_domains": [],
        }

    provider_type = _read_setting(entry, CONF_AI_PROVIDER, PROVIDER_ANTHROPIC)
    api_key = _read_setting(entry, CONF_API_KEY)
    has_key = bool(api_key)
    # Free is modeled as anthropic + null key — present it as "none".
    ui_provider = (
        _PANEL_PROVIDER_NONE
        if provider_type == PROVIDER_ANTHROPIC and not has_key
        else provider_type
    )
    extra_headers = _read_setting(entry, CONF_EXTRA_HEADERS)
    extra_headers_str = (
        json.dumps(extra_headers) if isinstance(extra_headers, dict) else ""
    )
    return {
        "provider": ui_provider,
        "model": _read_setting(entry, CONF_MODEL, DEFAULT_MODEL) or DEFAULT_MODEL,
        "base_url": _read_setting(entry, CONF_BASE_URL, "") or "",
        "has_api_key": has_key,
        "input_cost_per_mtok": float(
            _read_setting(entry, CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0
        ),
        "output_cost_per_mtok": float(
            _read_setting(entry, CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0
        ),
        "max_html_chars": int(
            _read_setting(entry, CONF_MAX_HTML_CHARS, _DEFAULT_MAX_HTML_CHARS)
            or _DEFAULT_MAX_HTML_CHARS
        ),
        "force_json_mode": bool(_read_setting(entry, CONF_FORCE_JSON_MODE, False)),
        "extra_headers": extra_headers_str,
        "anthropic_models": models,
        "excluded_domains": _read_excluded_domains(entry),
    }


@websocket_api.websocket_command(
    {vol.Required("type"): "price_watch/get_provider_settings"}
)
@websocket_api.async_response
async def ws_get_provider_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current global AI provider settings for the panel editor."""
    connection.send_result(msg["id"], _current_provider_state(_settings_entry(hass)))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "price_watch/set_provider_settings",
        vol.Required("provider"): vol.In(
            [_PANEL_PROVIDER_NONE, PROVIDER_ANTHROPIC, PROVIDER_OPENAI_COMPATIBLE]
        ),
        # Blank api_key means "keep the existing stored key" for providers
        # that use one. To clear a key, switch to Free.
        vol.Optional("api_key"): vol.Any(None, str),
        vol.Optional("model"): vol.Any(None, str),
        vol.Optional("base_url"): vol.Any(None, str),
        vol.Optional("input_cost_per_mtok"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("output_cost_per_mtok"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("max_html_chars"): vol.Any(None, vol.Coerce(int)),
        vol.Optional("force_json_mode"): bool,
        vol.Optional("extra_headers"): vol.Any(None, str),
        # Global blocklist: list of hostnames (or a newline/comma string)
        # to drop from every alternatives search. Independent of the
        # provider choice, so it's preserved across provider switches.
        vol.Optional("excluded_domains"): vol.Any(None, str, [str]),
    }
)
@websocket_api.async_response
async def ws_set_provider_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Validate + persist a new global AI provider, then reload products.

    Mirrors the config/options flow's validation (get_provider +
    validate_credentials) so the panel and HA settings can't diverge. On
    success, persists to the settings entry options and schedules a reload
    of every product entry (their coordinators rebuild the AIProvider on
    setup). Sends a typed WS error the panel can map to a message on any
    validation failure — nothing is persisted in that case.
    """
    settings = _settings_entry(hass)
    if settings is None:
        connection.send_error(
            msg["id"], "no_settings", "No Price Watch settings entry exists yet."
        )
        return

    provider = msg["provider"]
    existing_key = _read_setting(settings, CONF_API_KEY)
    submitted_key = (msg.get("api_key") or "").strip()
    # Preserve unrelated settings (region, currency, budgets, daily
    # alternatives, etc.) — only the AI-config keys are overwritten.
    new_options = dict(settings.options)

    if provider == _PANEL_PROVIDER_NONE:
        new_options.update(
            {
                CONF_AI_PROVIDER: PROVIDER_ANTHROPIC,
                CONF_API_KEY: None,
                CONF_MODEL: DEFAULT_MODEL,
                CONF_BASE_URL: None,
                CONF_INPUT_COST_PER_MTOK: 0.0,
                CONF_OUTPUT_COST_PER_MTOK: 0.0,
                CONF_MAX_HTML_CHARS: _DEFAULT_MAX_HTML_CHARS,
                CONF_FORCE_JSON_MODE: False,
                CONF_EXTRA_HEADERS: None,
            }
        )

    elif provider == PROVIDER_ANTHROPIC:
        api_key = submitted_key or (existing_key or None)
        if not api_key:
            connection.send_error(
                msg["id"],
                "key_required",
                "An Anthropic API key is required (or choose Free).",
            )
            return
        if not str(api_key).startswith("sk-ant-"):
            connection.send_error(
                msg["id"],
                "invalid_key_format",
                "Anthropic keys start with 'sk-ant-'.",
            )
            return
        model = (msg.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        try:
            provider_obj = get_provider(
                PROVIDER_ANTHROPIC, api_key=api_key, model=model
            )
            await provider_obj.validate_credentials()
        except AIAuthenticationError:
            connection.send_error(
                msg["id"], "invalid_key", "Anthropic rejected that API key."
            )
            return
        except AIProviderError as err:
            connection.send_error(
                msg["id"], "validation_error", f"Could not validate key: {err}"
            )
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Anthropic validation error")
            connection.send_error(msg["id"], "validation_error", str(err))
            return
        new_options.update(
            {
                CONF_AI_PROVIDER: PROVIDER_ANTHROPIC,
                CONF_API_KEY: api_key,
                CONF_MODEL: model,
                CONF_BASE_URL: None,
                CONF_INPUT_COST_PER_MTOK: 0.0,
                CONF_OUTPUT_COST_PER_MTOK: 0.0,
                CONF_MAX_HTML_CHARS: _DEFAULT_MAX_HTML_CHARS,
                CONF_FORCE_JSON_MODE: False,
                CONF_EXTRA_HEADERS: None,
            }
        )

    else:  # PROVIDER_OPENAI_COMPATIBLE
        base_url = (msg.get("base_url") or "").strip()
        model = (msg.get("model") or "").strip()
        if not base_url:
            connection.send_error(
                msg["id"],
                "base_url_required",
                "A base URL is required for an OpenAI-compatible provider.",
            )
            return
        if not model:
            connection.send_error(
                msg["id"],
                "model_required",
                "A model name is required for an OpenAI-compatible provider.",
            )
            return
        # api_key is optional for local endpoints (Ollama / LM Studio).
        api_key = submitted_key or (existing_key or None)
        extra_headers_raw = (msg.get("extra_headers") or "").strip()
        extra_headers: dict[str, str] | None = None
        if extra_headers_raw:
            try:
                parsed = json.loads(extra_headers_raw)
            except json.JSONDecodeError:
                connection.send_error(
                    msg["id"],
                    "extra_headers_invalid_json",
                    "Extra headers must be valid JSON.",
                )
                return
            if not isinstance(parsed, dict):
                connection.send_error(
                    msg["id"],
                    "extra_headers_not_object",
                    "Extra headers must be a JSON object.",
                )
                return
            extra_headers = {str(k): str(v) for k, v in parsed.items()}
        input_cost = float(msg.get("input_cost_per_mtok") or 0.0)
        output_cost = float(msg.get("output_cost_per_mtok") or 0.0)
        max_html = int(msg.get("max_html_chars") or _DEFAULT_MAX_HTML_CHARS)
        force_json = bool(msg.get("force_json_mode", False))
        try:
            provider_obj = get_provider(
                PROVIDER_OPENAI_COMPATIBLE,
                api_key=api_key,
                model=model,
                base_url=base_url,
                input_cost_per_mtok=input_cost,
                output_cost_per_mtok=output_cost,
                max_html_chars=max_html,
                force_json_mode=force_json,
                extra_headers=extra_headers,
            )
            await provider_obj.validate_credentials()
        except AIAuthenticationError:
            connection.send_error(
                msg["id"], "invalid_key", "The endpoint rejected the API key."
            )
            return
        except AIProviderError as err:
            connection.send_error(
                msg["id"],
                "openai_compat_unreachable",
                f"Could not reach the endpoint: {err}",
            )
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("OpenAI-compat validation error")
            connection.send_error(msg["id"], "validation_error", str(err))
            return
        new_options.update(
            {
                CONF_AI_PROVIDER: PROVIDER_OPENAI_COMPATIBLE,
                CONF_API_KEY: api_key,
                CONF_MODEL: model,
                CONF_BASE_URL: base_url,
                CONF_INPUT_COST_PER_MTOK: input_cost,
                CONF_OUTPUT_COST_PER_MTOK: output_cost,
                CONF_MAX_HTML_CHARS: max_html,
                CONF_FORCE_JSON_MODE: force_json,
                CONF_EXTRA_HEADERS: extra_headers,
            }
        )

    # Global domain blocklist — independent of provider, persisted only
    # when the panel actually sent the field (so a provider-only save
    # doesn't wipe it). Accept a list or a newline/comma-delimited string;
    # normalize to bare lowercase hosts and de-dupe (order preserved).
    if "excluded_domains" in msg:
        raw_excl = msg.get("excluded_domains")
        if raw_excl is None:
            raw_excl = []
        elif isinstance(raw_excl, str):
            raw_excl = re.split(r"[\n,]+", raw_excl)
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in raw_excl:
            norm = _normalize_domain(str(item))
            if norm and norm not in seen:
                seen.add(norm)
                cleaned.append(norm)
        new_options[CONF_EXCLUDED_DOMAINS] = cleaned

    # Persist. async_update_entry mutates settings.options in place, so the
    # _current_provider_state() call below reflects the new values.
    hass.config_entries.async_update_entry(settings, options=new_options)

    # Reload product entries so each coordinator rebuilds its AIProvider
    # from the new settings. The settings entry has no platforms / update
    # listener, so this won't cascade. Scheduled (not awaited) so the panel
    # gets a snappy reply — a product re-fetch can take several seconds.
    scheduled = 0
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
            continue
        hass.async_create_task(
            hass.config_entries.async_reload(entry.entry_id)
        )
        scheduled += 1

    _LOGGER.info(
        "Provider settings updated to %s; scheduled reload of %d product entries",
        provider,
        scheduled,
    )
    connection.send_result(
        msg["id"],
        {**_current_provider_state(settings), "reloaded": scheduled},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "price_watch/exclude_domain",
        # A hostname or a full URL — we normalize either to a bare host.
        vol.Required("domain"): str,
    }
)
@websocket_api.async_response
async def ws_exclude_domain(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Append one host to the global excluded-domains blocklist.

    The lightweight counterpart to set_provider_settings' excluded_domains
    field: lets the panel's "Search & add" results offer a one-click
    "exclude this site" button without re-sending (and re-validating) the
    whole provider payload. Idempotent — re-excluding an already-blocked
    host is a no-op. Returns the updated, normalized list.

    No product reload is scheduled: the blocklist is read fresh on every
    search (ws_search) and alternatives run, so the next search already
    honors it. Provider/coordinator config is untouched.
    """
    settings = _settings_entry(hass)
    if settings is None:
        connection.send_error(
            msg["id"], "no_settings", "No Price Watch settings entry exists yet."
        )
        return

    norm = _normalize_domain(str(msg.get("domain") or ""))
    if not norm:
        connection.send_error(
            msg["id"],
            "invalid_domain",
            "Could not read a hostname from that value.",
        )
        return

    current = _read_excluded_domains(settings)
    added = norm not in current
    updated = [*current, norm] if added else current
    if added:
        new_options = {**settings.options, CONF_EXCLUDED_DOMAINS: updated}
        hass.config_entries.async_update_entry(settings, options=new_options)
        _LOGGER.info("Added %s to excluded domains (now %d)", norm, len(updated))

    connection.send_result(
        msg["id"], {"excluded_domains": updated, "added": norm, "was_new": added}
    )


# ---------------------------------------------------------------------------
# Selector tester (panel "Advanced — custom price selector" feature).
#
# Advanced users grab a CSS selector from their browser's dev tools (F12 →
# right-click the price → Copy selector) or via the Price Watch bookmarklet,
# and need to confirm it actually extracts the right value before committing
# it as a listing's custom_parser. This command fetches the page server-side
# with the SAME engine the tracker uses (curl_cffi Chrome impersonation, so
# the test reflects what the coordinator will really see — not what the
# user's logged-in browser sees) and reports what each selector matched.
# ---------------------------------------------------------------------------

# Cap how much matched text we echo back, so a selector that accidentally
# grabs <body> can't flood the panel.
_SELECTOR_RAW_CAP = 300


@websocket_api.websocket_command(
    {
        vol.Required("type"): "price_watch/test_selector",
        vol.Required("url"): str,
        vol.Required("price_selector"): str,
        vol.Optional("title_selector"): vol.Any(None, str),
        # Accept the same shapes _normalize_cookies handles: a Cookie-header
        # string (what the panel sends), a {name: value} dict, or a list of
        # cookie dicts.
        vol.Optional("request_cookies"): vol.Any(None, str, dict, list),
    }
)
@websocket_api.async_response
async def ws_test_selector(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Fetch a page and report what the given CSS selector(s) extract.

    Reply shape:
        {
          "fetch_ok": true,
          "page_title": "<page title>",
          "price": {"selector": "...", "found": bool,
                    "raw": "<matched text or attr>", "value": <float|null>},
          "title": {"selector": "...", "found": bool, "raw": "..."}  # if asked
        }
    On a fetch failure (timeout, robot-check, network) sends a typed WS error.
    """
    # Imported lazily — mirrors extractor.extract_product, which pulls the
    # parser helpers in on demand, and keeps these heavyweight deps off the
    # module import path for the common (search) case.
    from bs4 import BeautifulSoup

    from .extractor import _normalize_cookies, fetch_html
    from .parsers import _apply_transforms

    url = (msg.get("url") or "").strip()
    price_selector = (msg.get("price_selector") or "").strip()
    title_selector = (msg.get("title_selector") or "").strip()
    if not url:
        connection.send_error(msg["id"], "url_required", "A listing URL is required.")
        return
    if not price_selector:
        connection.send_error(
            msg["id"], "selector_required", "A price selector is required."
        )
        return

    cookies = _normalize_cookies(msg.get("request_cookies"))
    session = async_get_clientsession(hass)
    try:
        html = await fetch_html(url, session=session, cookies=cookies)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("test_selector fetch failed for %s: %s", url, err)
        connection.send_error(
            msg["id"],
            "fetch_failed",
            f"Could not fetch the page: {type(err).__name__}: {err}",
        )
        return

    soup = BeautifulSoup(html, "html.parser")
    page_title = (
        soup.title.string.strip()
        if soup.title and soup.title.string
        else ""
    )

    def _run(selector: str) -> dict[str, Any]:
        """Apply one selector, supporting the `selector@attr` form."""
        sel = selector
        attr: str | None = None
        if "@" in sel:
            sel, attr = sel.rsplit("@", 1)
        try:
            element = soup.select_one(sel.strip())
        except Exception as err:  # noqa: BLE001 — invalid selector syntax
            return {"selector": selector, "found": False, "raw": None,
                    "error": f"Invalid selector: {err}"}
        if element is None:
            return {"selector": selector, "found": False, "raw": None}
        if attr:
            raw = str(element.get(attr.strip(), "") or "")
        else:
            raw = element.get_text(strip=True)
        return {"selector": selector, "found": True, "raw": raw[:_SELECTOR_RAW_CAP]}

    price_result = _run(price_selector)
    if price_result.get("found") and price_result.get("raw"):
        # Reuse the production price cleaner so the previewed value matches
        # exactly what the listing's parser would store.
        price_result["value"] = _apply_transforms(price_result["raw"], "price_clean")
    else:
        price_result["value"] = None

    reply: dict[str, Any] = {
        "fetch_ok": True,
        "page_title": page_title,
        "price": price_result,
    }
    if title_selector:
        reply["title"] = _run(title_selector)

    connection.send_result(msg["id"], reply)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "price_watch/list_variants",
        vol.Required("entry_id"): str,
        vol.Optional("listing_id"): vol.Any(None, str),
    }
)
@websocket_api.async_response
async def ws_list_variants(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Enumerate a product's selectable Wix variants for the panel picker.

    Fetches the listing page, parses the embedded option groups + combos
    via ``extractor.list_wix_variants``, and returns them along with the
    variant currently pinned (so the panel pre-selects it).

    Reply shape:
        {
          "supported": true,
          "options": [{"title": "Remote", "choices": [...]}, ...],
          "variants": [{"labels": [...], "price": ..., "currency": ...,
                        "in_stock": ...}, ...],
          "current": ["1xIR Remote", "5-48V"],
          "currency": "USD"
        }
    When the page isn't a Wix variant page, replies {"supported": false}.
    On fetch failure sends a typed WS error.
    """
    from .coordinator import PriceWatchCoordinator
    from .extractor import _normalize_cookies, fetch_html, list_wix_variants

    entry_id = (msg.get("entry_id") or "").strip()
    listing_id = (msg.get("listing_id") or "").strip()

    coord = hass.data.get(DOMAIN, {}).get(entry_id)
    if not isinstance(coord, PriceWatchCoordinator):
        connection.send_error(
            msg["id"], "not_found", f"No tracked product with id {entry_id!r}."
        )
        return

    # Resolve which URL + currently-pinned variant to surface. Default is the
    # primary listing (product-level variant_options fallback); an explicit
    # listing_id targets that listing's URL + per-listing variant.
    url = coord.url
    current: list[str] = list(coord.entry.options.get("variant_options") or [])
    cookies_raw: Any = None
    listings = coord.entry.options.get("listings") or []
    if listing_id:
        for listing in listings:
            if isinstance(listing, dict) and listing.get("id") == listing_id:
                url = listing.get("url") or url
                current = list(listing.get("variant_options") or [])
                cookies_raw = listing.get("request_cookies")
                break

    if not url:
        connection.send_error(msg["id"], "no_url", "Product has no URL to inspect.")
        return

    cookies = _normalize_cookies(cookies_raw)
    session = async_get_clientsession(hass)
    try:
        html = await fetch_html(url, session=session, cookies=cookies)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("list_variants fetch failed for %s: %s", url, err)
        connection.send_error(
            msg["id"],
            "fetch_failed",
            f"Could not fetch the page: {type(err).__name__}: {err}",
        )
        return

    data = list_wix_variants(html)
    if not data:
        connection.send_result(msg["id"], {"supported": False})
        return

    connection.send_result(
        msg["id"],
        {
            "supported": True,
            "options": data.get("options", []),
            "variants": data.get("variants", []),
            "current": current,
            "currency": data.get("currency", ""),
        },
    )
