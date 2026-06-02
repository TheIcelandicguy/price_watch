"""Config flow for Price Watch.

Two-stage setup:
1. First-time install: prompt for API key (stored in a "settings" entry).
2. Each subsequent flow: paste URL, preview extracted data, confirm.

The settings entry uses a sentinel domain inside config flow data so we can
fetch it from any product entry's setup. Could alternatively use HA's
`config_entry.data` but a single shared entry is cleaner for the API key.

OPTIONS FLOW SHAPE:
Per-product options is a multi-step flow with a menu router because the
field count crossed the threshold where one giant form became unfriendly
(2024-spec: 14+ fields covering basic settings, parser config, AI
provider override, and maintenance actions). The menu segments these
into logical pages — the user only sees the fields relevant to what
they're trying to change.

Settings options is single-step because its field set mirrors the
first-install settings step almost exactly — putting them on one page
keeps the UI familiar and lets users edit any combination of values in
one save.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
    CONF_COOKIES,
    CONF_CUSTOM_PARSER,
    CONF_DAILY_ALTERNATIVES,
    CONF_DAILY_BUDGET_USD,
    CONF_EXTRA_HEADERS,
    CONF_FORCE_DISCONTINUED,
    CONF_FORCE_JSON_MODE,
    CONF_HOME_CURRENCY,
    CONF_USER_REGION,
    CONF_INPUT_COST_PER_MTOK,
    CONF_MAX_HTML_CHARS,
    CONF_MODEL,
    CONF_MONTHLY_BUDGET_USD,
    CONF_OUTPUT_COST_PER_MTOK,
    CONF_PAUSED,
    CONF_SCAN_INTERVAL,
    CONF_TARGET_PRICE,
    CONF_URL,
    DEFAULT_DAILY_BUDGET,
    DEFAULT_MODEL,
    DEFAULT_MONTHLY_BUDGET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_PRODUCT,
    ENTRY_TYPE_SETTINGS,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .cookies import to_header_str as cookies_to_header_str
from .extractor import ExtractionError, extract_product
from .presets import find_preset, normalize_url as preset_normalize_url

_LOGGER = logging.getLogger(__name__)

# Form-local field names — distinct from CONF_MODEL so the same form
# can carry both an Anthropic-model dropdown and a free-text
# OpenAI-compat model input without voluptuous schema collisions.
# Both ultimately resolve to CONF_MODEL in the saved entry data.
CONF_MODEL_ANTHROPIC = "model_anthropic"
CONF_MODEL_OPENAI = "model_openai"

# Sentinel used by the per-product provider-override step. When the
# user picks this from the provider dropdown, we write `None` (or
# remove the override entirely) into the entry options so the
# coordinator falls back to the settings entry. Distinct from
# PROVIDER_ANTHROPIC / PROVIDER_OPENAI_COMPATIBLE because those are
# real provider types in the ai/ package.
PROVIDER_INHERIT = "_inherit"

# Form-local sentinel for the provider-picker step's "Free / no AI"
# choice. Selecting it stores CONF_AI_PROVIDER=anthropic with a null
# api_key, which the provider resolver treats as "JSON-LD / custom
# parser only" (no AI). Kept distinct from the real provider types so
# the picker can offer Free as a first-class, clearly-labelled option.
PROVIDER_NONE = "none"


def _provider_choice_selector(
    *, include_inherit: bool = False, default_label_free: str = "Free"
) -> SelectSelector:
    """Radio-style selector for the provider-picker step.

    Renders as a vertical list of radio buttons (mode=list) rather than
    a cramped dropdown — far friendlier for a 3-way choice. Labels are
    inline so they don't need separate translation keys.

    include_inherit adds the per-product "Inherit from settings" option
    used by the options override flow; the install/settings flows omit
    it (there's nothing to inherit from yet).
    """
    options: list[SelectOptionDict] = []
    if include_inherit:
        options.append(
            SelectOptionDict(
                value=PROVIDER_INHERIT,
                label="Inherit from shared settings (recommended)",
            )
        )
    options.extend(
        [
            SelectOptionDict(
                value=PROVIDER_NONE,
                label=f"{default_label_free} — no AI, free (Schema.org / custom parser)",
            ),
            SelectOptionDict(
                value=PROVIDER_ANTHROPIC,
                label="Anthropic (Claude) — paste an sk-ant-… key",
            ),
            SelectOptionDict(
                value=PROVIDER_OPENAI_COMPATIBLE,
                label="OpenAI-compatible — OpenAI / Ollama / Groq / OpenRouter / LM Studio",
            ),
        ]
    )
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            mode=SelectSelectorMode.LIST,
        )
    )

# Form field name used on every per-product sub-step to provide a
# "back without saving" path. HA's options flow framework doesn't
# render an explicit back button on form steps — only menu steps —
# so each sub-step embeds this checkbox. When the user submits with
# it ticked, the handler returns to the menu without applying any
# of the other form fields, effectively discarding the in-progress
# edits for that sub-step. The working dict is untouched, so other
# sub-steps' pending edits are preserved.
BACK_TO_MENU = "back_to_menu"

# Anthropic model choices live in const.ANTHROPIC_MODELS (shared with the
# panel's provider editor). Imported above.


def _read_setting(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Read a setting from a ConfigEntry, options taking precedence over data.

    The settings entry stores initial values in `entry.data`; the options flow
    writes updates to `entry.options`. Anywhere that reads settings must check
    options first or it'll keep using stale values.
    """
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


def _parser_get_cookies(custom_parser_raw: Any) -> str:
    """Extract the cookie string from a serialized custom_parser config.

    Returns "" when no cookies are set. Defensive — handles the parser
    being None, a JSON string, a dict, or malformed input.
    """
    if not custom_parser_raw:
        return ""
    if isinstance(custom_parser_raw, str):
        try:
            parsed = json.loads(custom_parser_raw)
        except (ValueError, TypeError):
            return ""
    elif isinstance(custom_parser_raw, dict):
        parsed = custom_parser_raw
    else:
        return ""
    cookies = parsed.get("request_cookies") if isinstance(parsed, dict) else None
    # Round-trip whatever shape was stored (string/dict/list) back to a
    # header string for editing convenience. Shared with the services so the
    # str/dict/list handling stays in one place.
    return cookies_to_header_str(cookies)


def _parser_with_cookies(custom_parser_raw: Any, cookies: str) -> str:
    """Return a serialized parser JSON string with request_cookies set.

    Preserves the existing parser config (selectors, transforms, etc).
    When `cookies` is empty, the request_cookies field is removed entirely
    rather than left as an empty string — the extractor treats both as
    "no cookies", but the cleaner persisted shape is no key at all.

    When the existing parser is empty AND cookies is non-empty, creates
    a minimal cookies-only parser config: { "request_cookies": "..." }.
    The extractor's cookie path runs regardless of whether the parser
    has a `type` or `selectors`, so this is a valid degenerate config.
    Such a parser config will fail at the actual parsing step, but the
    cookied response goes through the JSON-LD / AI fallback path which
    is the whole point of using cookies (to access content that's
    cookie-walled, like Amazon).
    """
    # Decode existing
    parsed: dict[str, Any] = {}
    if custom_parser_raw:
        if isinstance(custom_parser_raw, str):
            try:
                p = json.loads(custom_parser_raw)
                if isinstance(p, dict):
                    parsed = p
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "custom_parser is not valid JSON; rebuilding from cookies "
                    "(prior content lost): %r", str(custom_parser_raw)[:100],
                )
        elif isinstance(custom_parser_raw, dict):
            parsed = dict(custom_parser_raw)

    cookies = (cookies or "").strip()
    if cookies:
        parsed["request_cookies"] = cookies
    else:
        parsed.pop("request_cookies", None)

    if not parsed:
        return ""  # No parser config at all
    return json.dumps(parsed)


# ---- Shared settings-form helpers (used by both install + options flows) ----
#
# The settings form was historically one flat 13-field page that crammed
# Anthropic and OpenAI-compatible fields together unconditionally — ugly
# and confusing. It's now a provider PICKER step (radio list) that routes
# to a short, provider-specific detail step. These module-level helpers
# hold the schema-building and validation logic so the install ConfigFlow
# and the post-install OptionsFlow stay in lockstep without duplicating it.

# OpenAI-compat fields zeroed when switching to Anthropic/Free, so a
# provider change doesn't leave stale endpoint config confusing the
# coordinator.
_OPENAI_CLEARED: dict[str, Any] = {
    CONF_BASE_URL: None,
    CONF_INPUT_COST_PER_MTOK: 0.0,
    CONF_OUTPUT_COST_PER_MTOK: 0.0,
    CONF_MAX_HTML_CHARS: 100_000,
    CONF_FORCE_JSON_MODE: False,
    CONF_EXTRA_HEADERS: None,
}


def _common_fields(ui: dict[str, Any]) -> dict[Any, Any]:
    """Currency / region / budget fields shared by every provider detail step."""
    return {
        vol.Optional(
            CONF_HOME_CURRENCY, default=ui.get(CONF_HOME_CURRENCY, "") or ""
        ): str,
        vol.Optional(
            CONF_USER_REGION, default=ui.get(CONF_USER_REGION, "") or ""
        ): str,
        vol.Optional(
            CONF_DAILY_BUDGET_USD,
            default=ui.get(CONF_DAILY_BUDGET_USD, DEFAULT_DAILY_BUDGET),
        ): vol.Coerce(float),
        vol.Optional(
            CONF_MONTHLY_BUDGET_USD,
            default=ui.get(CONF_MONTHLY_BUDGET_USD, DEFAULT_MONTHLY_BUDGET),
        ): vol.Coerce(float),
    }


def _free_schema(ui: dict[str, Any]) -> vol.Schema:
    """Free / no-AI detail step: just the common fields."""
    return vol.Schema(_common_fields(ui))


def _anthropic_schema(ui: dict[str, Any]) -> vol.Schema:
    """Anthropic detail step: API key + model + common fields."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_API_KEY, default=ui.get(CONF_API_KEY, "") or ""
            ): str,
            vol.Optional(
                CONF_MODEL_ANTHROPIC,
                default=ui.get(CONF_MODEL_ANTHROPIC, DEFAULT_MODEL),
            ): vol.In(list(ANTHROPIC_MODELS)),
            **_common_fields(ui),
        }
    )


def _openai_schema(ui: dict[str, Any]) -> vol.Schema:
    """OpenAI-compatible detail step: endpoint + model + costs + common."""
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_URL, default=ui.get(CONF_BASE_URL, "") or ""
            ): str,
            vol.Required(
                CONF_MODEL_OPENAI, default=ui.get(CONF_MODEL_OPENAI, "") or ""
            ): str,
            vol.Optional(
                CONF_API_KEY, default=ui.get(CONF_API_KEY, "") or ""
            ): str,
            vol.Optional(
                CONF_INPUT_COST_PER_MTOK,
                default=ui.get(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0,
            ): vol.Coerce(float),
            vol.Optional(
                CONF_OUTPUT_COST_PER_MTOK,
                default=ui.get(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0,
            ): vol.Coerce(float),
            vol.Optional(
                CONF_MAX_HTML_CHARS,
                default=ui.get(CONF_MAX_HTML_CHARS, 100_000) or 100_000,
            ): vol.Coerce(int),
            vol.Optional(
                CONF_FORCE_JSON_MODE,
                default=bool(ui.get(CONF_FORCE_JSON_MODE, False)),
            ): bool,
            vol.Optional(
                CONF_EXTRA_HEADERS, default=ui.get(CONF_EXTRA_HEADERS, "") or ""
            ): str,
            **_common_fields(ui),
        }
    )


def _parse_common(ui: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate + normalize the common fields. Returns (values, errors)."""
    errors: dict[str, str] = {}
    region_raw = (ui.get(CONF_USER_REGION) or "").strip().upper()
    if region_raw and not (len(region_raw) == 2 and region_raw.isalpha()):
        errors[CONF_USER_REGION] = "invalid_region_code"
        region_raw = ""
    values = {
        CONF_HOME_CURRENCY: (ui.get(CONF_HOME_CURRENCY) or "").upper() or None,
        CONF_USER_REGION: region_raw or None,
        CONF_DAILY_BUDGET_USD: ui.get(CONF_DAILY_BUDGET_USD, DEFAULT_DAILY_BUDGET),
        CONF_MONTHLY_BUDGET_USD: ui.get(
            CONF_MONTHLY_BUDGET_USD, DEFAULT_MONTHLY_BUDGET
        ),
    }
    return values, errors


def _free_config() -> dict[str, Any]:
    """Provider config for the Free / no-AI choice.

    Stored as provider=anthropic + null key, which the provider resolver
    treats as "Schema.org / custom parser only" (no AI calls). OpenAI
    endpoint fields are cleared so a later switch doesn't see stale config.
    """
    return {
        CONF_AI_PROVIDER: PROVIDER_ANTHROPIC,
        CONF_API_KEY: None,
        CONF_MODEL: DEFAULT_MODEL,
        **_OPENAI_CLEARED,
    }


async def _validate_anthropic(
    ui: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate the Anthropic detail form. Returns (provider_config, errors).

    An empty key is allowed — it's equivalent to the Free choice (no AI),
    just reached via the Anthropic page. Endpoint fields are cleared.
    """
    errors: dict[str, str] = {}
    api_key = (ui.get(CONF_API_KEY) or "").strip() or None
    model = ui.get(CONF_MODEL_ANTHROPIC, DEFAULT_MODEL)
    config = {
        CONF_AI_PROVIDER: PROVIDER_ANTHROPIC,
        CONF_API_KEY: api_key,
        CONF_MODEL: model,
        **_OPENAI_CLEARED,
    }
    if api_key:
        if not api_key.startswith("sk-ant-"):
            errors[CONF_API_KEY] = "invalid_key_format"
        else:
            try:
                provider = get_provider(
                    PROVIDER_ANTHROPIC, api_key=api_key, model=model
                )
                await provider.validate_credentials()
            except AIAuthenticationError:
                errors[CONF_API_KEY] = "invalid_key"
            except AIProviderError:
                _LOGGER.exception("Failed to validate API key")
                errors[CONF_API_KEY] = "validation_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating API key")
                errors[CONF_API_KEY] = "validation_error"
    return config, errors


async def _validate_openai(
    ui: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate the OpenAI-compatible detail form. Returns (config, errors)."""
    errors: dict[str, str] = {}
    api_key = (ui.get(CONF_API_KEY) or "").strip() or None
    base_url = (ui.get(CONF_BASE_URL) or "").strip()
    model = (ui.get(CONF_MODEL_OPENAI) or "").strip()
    if not base_url:
        errors[CONF_BASE_URL] = "base_url_required"
    if not model:
        errors[CONF_MODEL_OPENAI] = "model_required"

    extra_headers_raw = (ui.get(CONF_EXTRA_HEADERS) or "").strip()
    extra_headers: dict[str, str] | None = None
    if extra_headers_raw:
        try:
            parsed = json.loads(extra_headers_raw)
            if not isinstance(parsed, dict):
                errors[CONF_EXTRA_HEADERS] = "extra_headers_not_object"
            else:
                extra_headers = {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            errors[CONF_EXTRA_HEADERS] = "extra_headers_invalid_json"

    config = {
        CONF_AI_PROVIDER: PROVIDER_OPENAI_COMPATIBLE,
        CONF_API_KEY: api_key,
        CONF_MODEL: model,
        CONF_BASE_URL: base_url or None,
        CONF_INPUT_COST_PER_MTOK: float(
            ui.get(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0
        ),
        CONF_OUTPUT_COST_PER_MTOK: float(
            ui.get(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0
        ),
        CONF_MAX_HTML_CHARS: int(ui.get(CONF_MAX_HTML_CHARS, 100_000) or 100_000),
        CONF_FORCE_JSON_MODE: bool(ui.get(CONF_FORCE_JSON_MODE, False)),
        CONF_EXTRA_HEADERS: extra_headers,
    }

    if not errors:
        try:
            provider = get_provider(
                PROVIDER_OPENAI_COMPATIBLE,
                api_key=api_key,
                model=model,
                base_url=base_url,
                input_cost_per_mtok=config[CONF_INPUT_COST_PER_MTOK],
                output_cost_per_mtok=config[CONF_OUTPUT_COST_PER_MTOK],
                max_html_chars=config[CONF_MAX_HTML_CHARS],
                force_json_mode=config[CONF_FORCE_JSON_MODE],
                extra_headers=extra_headers,
            )
            await provider.validate_credentials()
        except AIAuthenticationError:
            errors[CONF_API_KEY] = "invalid_key"
        except AIProviderError as err:
            _LOGGER.warning("OpenAI-compat validation failed: %s", err)
            errors["base"] = "openai_compat_unreachable"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating OpenAI-compat endpoint")
            errors["base"] = "validation_error"
    return config, errors


class PriceWatchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Price Watch config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._url: str | None = None
        self._preview: dict[str, Any] | None = None
        self._api_key: str | None = None
        # If the URL matches a known retailer preset, this holds the
        # auto-generated parser config so we can persist it on submit.
        self._preset_parser: dict[str, Any] | None = None
        self._preset_name: str | None = None

    def _settings_entry(self) -> ConfigEntry | None:
        """Find existing settings entry, if any."""
        for entry in self._async_current_entries():
            if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
                return entry
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Entry point.

        First install (no settings entry yet) routes to the settings step
        so the user can configure their AI provider.

        Subsequent invocations show a menu choosing how to add a new
        tracked product:
            - 'product' — paste a URL, integration extracts and previews
              the product before creating the entry (existing flow)
            - 'shell' — provide a name only; entry is created with no
              listings, and the user adds retailer URLs later via the
              price_watch.add_listing service or panel UI (Phase 3b)
        """
        if self._settings_entry() is None:
            return await self.async_step_settings()
        return self.async_show_menu(
            step_id="user",
            menu_options=["product", "shell"],
        )

    async def async_step_shell(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Shell-then-populate flow: create an entry with name only, no URL.

        The user provides just the product name (e.g. "GIGABYTE Z890
        motherboard"). The entry is created with:
            - entry.data.url = "" (no URL yet)
            - entry.options.listings = [] (no listings yet)

        The coordinator's `_async_update_data` short-circuits on shell
        entries (no listings → no extraction, no errors). Sensors aren't
        created until the user adds the first listing via:
            - the price_watch.add_listing service, OR
            - the panel UI's "Add listing" affordance (Phase 4)

        Uniqueness: keyed off the name (case-insensitive, "shell:<name>"
        prefix) to prevent accidental duplicates. URL-based collision
        checking doesn't apply since there is no URL.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                # Uniqueness keyed off name (no URL to collide on)
                await self.async_set_unique_id(f"shell:{name.lower()}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        "entry_type": ENTRY_TYPE_PRODUCT,
                        CONF_URL: "",  # shell entry — no URL yet
                    },
                    options={
                        CONF_SCAN_INTERVAL: int(
                            DEFAULT_SCAN_INTERVAL.total_seconds() / 60
                        ),
                        "listings": [],  # populated later via add_listing
                    },
                )

        return self.async_show_form(
            step_id="shell",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First-run settings: pick an AI provider (radio list).

        This is now just a router — it shows a friendly 3-way radio
        picker (Free / Anthropic / OpenAI-compatible) and forwards to a
        short, provider-specific detail step. No credential fields live
        here, so the user isn't faced with a wall of irrelevant inputs.
        """
        if user_input is not None:
            choice = user_input[CONF_AI_PROVIDER]
            if choice == PROVIDER_NONE:
                return await self.async_step_settings_free()
            if choice == PROVIDER_OPENAI_COMPATIBLE:
                return await self.async_step_settings_openai()
            return await self.async_step_settings_anthropic()

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AI_PROVIDER, default=PROVIDER_NONE
                    ): _provider_choice_selector(),
                }
            ),
        )

    async def async_step_settings_free(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Free / no-AI detail: currency, region, budgets only."""
        errors: dict[str, str] = {}
        if user_input is not None:
            common, errors = _parse_common(user_input)
            if not errors:
                return self.async_create_entry(
                    title="Price Watch (settings)",
                    data={
                        "entry_type": ENTRY_TYPE_SETTINGS,
                        **_free_config(),
                        **common,
                    },
                )
        return self.async_show_form(
            step_id="settings_free",
            data_schema=_free_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_settings_anthropic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Anthropic detail: API key + model + common fields."""
        errors: dict[str, str] = {}
        if user_input is not None:
            config, errors = await _validate_anthropic(user_input)
            common, common_errors = _parse_common(user_input)
            errors.update(common_errors)
            if not errors:
                return self.async_create_entry(
                    title="Price Watch (settings)",
                    data={
                        "entry_type": ENTRY_TYPE_SETTINGS,
                        **config,
                        **common,
                    },
                )
        return self.async_show_form(
            step_id="settings_anthropic",
            data_schema=_anthropic_schema(user_input or {}),
            errors=errors,
            description_placeholders={
                "docs_url": "https://docs.claude.com/en/docs/about-claude/pricing",
            },
        )

    async def async_step_settings_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """OpenAI-compatible detail: endpoint + model + costs + common."""
        errors: dict[str, str] = {}
        if user_input is not None:
            config, errors = await _validate_openai(user_input)
            common, common_errors = _parse_common(user_input)
            errors.update(common_errors)
            if not errors:
                return self.async_create_entry(
                    title="Price Watch (settings)",
                    data={
                        "entry_type": ENTRY_TYPE_SETTINGS,
                        **config,
                        **common,
                    },
                )
        return self.async_show_form(
            step_id="settings_openai",
            data_schema=_openai_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_product(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a product. User pastes URL (and optional cookies for
        bot-protected sites), we extract and show preview."""
        errors: dict[str, str] = {}
        settings = self._settings_entry()

        ai_provider = None
        if settings is not None:
            provider_type = _read_setting(
                settings, CONF_AI_PROVIDER, PROVIDER_ANTHROPIC
            )
            try:
                if provider_type == PROVIDER_ANTHROPIC:
                    api_key = _read_setting(settings, CONF_API_KEY)
                    if api_key:
                        ai_provider = get_provider(
                            PROVIDER_ANTHROPIC,
                            api_key=api_key,
                            model=_read_setting(settings, CONF_MODEL, DEFAULT_MODEL),
                        )
                elif provider_type == PROVIDER_OPENAI_COMPATIBLE:
                    base_url = _read_setting(settings, CONF_BASE_URL)
                    model = _read_setting(settings, CONF_MODEL)
                    if base_url and model:
                        ai_provider = get_provider(
                            PROVIDER_OPENAI_COMPATIBLE,
                            api_key=_read_setting(settings, CONF_API_KEY),
                            model=model,
                            base_url=base_url,
                            input_cost_per_mtok=float(
                                _read_setting(settings, CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0
                            ),
                            output_cost_per_mtok=float(
                                _read_setting(settings, CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0
                            ),
                            max_html_chars=int(
                                _read_setting(settings, CONF_MAX_HTML_CHARS, 100_000) or 100_000
                            ),
                            force_json_mode=bool(
                                _read_setting(settings, CONF_FORCE_JSON_MODE, False)
                            ),
                            extra_headers=_read_setting(settings, CONF_EXTRA_HEADERS),
                        )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to build AI provider for preview")
                ai_provider = None

        if user_input is not None:
            url = user_input[CONF_URL].strip()
            cookies_raw = (user_input.get("cookies") or "").strip()

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            preset = find_preset(url)
            preset_parser: dict[str, Any] | None = None
            if preset is not None:
                normalized = preset_normalize_url(preset, url)
                if normalized != url:
                    _LOGGER.info(
                        "%s preset normalized URL: %s -> %s",
                        preset.NAME, url, normalized,
                    )
                    url = normalized
                    await self.async_set_unique_id(url)
                    self._abort_if_unique_id_configured()
                try:
                    preset_parser = preset.build_parser(url)
                    if preset_parser:
                        _LOGGER.info(
                            "Using %s preset for %s", preset.NAME, url
                        )
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Preset %s build_parser raised", preset.NAME)
                    preset_parser = None

            if cookies_raw:
                # Cookies must reach the extractor even when no preset
                # matched — build a cookies-only parser in that case. The
                # extractor's cookie path runs regardless of parser
                # type/selectors, and extraction falls through to JSON-LD /
                # AI, which is the whole point of cookies (reach
                # cookie-walled content like Amazon).
                if preset_parser is None:
                    preset_parser = {}
                preset_parser["request_cookies"] = cookies_raw
                _LOGGER.info(
                    "Cookies attached to parser config for %s (%s)",
                    url, preset.NAME if preset else "cookies-only",
                )

            try:
                result = await extract_product(
                    url=url,
                    session=async_get_clientsession(self.hass),
                    ai_provider=ai_provider,
                    custom_parser=preset_parser,
                )
            except ExtractionError as err:
                _LOGGER.warning("Extraction failed for %s: %s", url, err)
                msg = str(err)
                if "No JSON-LD" in msg or "no ai provider" in msg.lower() or "no api key" in msg.lower():
                    errors["base"] = "needs_api_or_parser"
                elif "HTTP 4" in msg or "HTTP 5" in msg or "Network error" in msg or "Timeout" in msg:
                    errors["base"] = "fetch_failed"
                else:
                    errors["base"] = "extraction_failed"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error extracting %s: %s: %s", url, type(err).__name__, err)
                errors["base"] = "unknown"
            else:
                self._url = url
                self._preset_parser = preset_parser
                self._preset_name = preset.NAME if preset else None
                self._preview = {
                    "title": result.title,
                    "price": result.price,
                    "currency": result.currency,
                    "image_url": result.image_url,
                    "retailer": result.retailer,
                    "in_stock": result.in_stock,
                    "method": result.method,
                    "cost_usd": result.cost_usd,
                    "preset": self._preset_name,
                }
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="product",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Optional("cookies", default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show extracted preview, let user set target + name + interval."""
        if user_input is not None and self._preview and self._url:
            settings = self._settings_entry()
            options: dict[str, Any] = {
                CONF_TARGET_PRICE: user_input.get(CONF_TARGET_PRICE),
                CONF_SCAN_INTERVAL: user_input.get(
                    CONF_SCAN_INTERVAL,
                    int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                ),
            }
            if self._preset_parser:
                options[CONF_CUSTOM_PARSER] = json.dumps(self._preset_parser)

            entry_data: dict[str, Any] = {
                "entry_type": ENTRY_TYPE_PRODUCT,
                CONF_URL: self._url,
            }
            if settings is not None:
                provider_type = _read_setting(
                    settings, CONF_AI_PROVIDER, PROVIDER_ANTHROPIC
                )
                if provider_type == PROVIDER_ANTHROPIC:
                    entry_data[CONF_API_KEY] = _read_setting(settings, CONF_API_KEY)
                    entry_data[CONF_MODEL] = _read_setting(
                        settings, CONF_MODEL, DEFAULT_MODEL
                    )

            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or self._preview["title"],
                data=entry_data,
                options=options,
            )

        preview = self._preview or {}
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=preview.get("title", "")): str,
                    vol.Optional(CONF_TARGET_PRICE): vol.Coerce(float),
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)),
                }
            ),
            description_placeholders={
                "title": str(preview.get("title", "")),
                "price": f"{preview.get('price', '?')} {preview.get('currency', '')}",
                "retailer": str(preview.get("retailer") or "unknown"),
                "method": str(preview.get("method", "")),
                "cost_usd": f"${preview.get('cost_usd', 0):.4f}",
                "preset": str(preview.get("preset") or "none"),
            },
        )

    async def async_step_panel_track(
        self, info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a product entry directly from an in-panel search pick.

        Source-based, single-step flow invoked by the
        price_watch.track_product service (which the panel calls after
        the user picks a live-search result and confirms in the dialog).

        Unlike async_step_product, this does NOT fetch/extract a preview:
        the panel already has the title/url from the search, and forcing
        a synchronous extraction here would make "Track" slow and able to
        fail on transient fetch errors. We just persist the entry; the
        coordinator runs the first live fetch on setup like any product.

        `info` carries: url (required), name (optional, defaults to url),
        target_price (optional float). Mirrors the entry data/options
        shape produced by async_step_confirm so the coordinator and
        options flow treat it identically to a URL-added product.
        """
        info = info or {}
        url = (info.get(CONF_URL) or "").strip()
        if not url:
            return self.async_abort(reason="no_url")

        name = (info.get(CONF_NAME) or "").strip()
        target_raw = info.get(CONF_TARGET_PRICE)
        try:
            target = float(target_raw) if target_raw is not None else None
        except (TypeError, ValueError):
            target = None

        await self.async_set_unique_id(url)
        self._abort_if_unique_id_configured()

        # Preset detection for a better parser (mirrors async_step_product).
        preset = find_preset(url)
        preset_parser: dict[str, Any] | None = None
        if preset is not None:
            normalized = preset_normalize_url(preset, url)
            if normalized != url:
                url = normalized
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
            try:
                preset_parser = preset.build_parser(url)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Preset %s build_parser raised", preset.NAME)
                preset_parser = None

        options: dict[str, Any] = {
            CONF_TARGET_PRICE: target,
            CONF_SCAN_INTERVAL: int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
        }
        if preset_parser:
            options[CONF_CUSTOM_PARSER] = json.dumps(preset_parser)

        entry_data: dict[str, Any] = {
            "entry_type": ENTRY_TYPE_PRODUCT,
            CONF_URL: url,
        }
        # Snapshot the Anthropic key/model onto the entry like
        # async_step_confirm does, so the coordinator can run AI
        # extraction without re-reading the settings entry.
        settings = self._settings_entry()
        if settings is not None:
            provider_type = _read_setting(
                settings, CONF_AI_PROVIDER, PROVIDER_ANTHROPIC
            )
            if provider_type == PROVIDER_ANTHROPIC:
                entry_data[CONF_API_KEY] = _read_setting(settings, CONF_API_KEY)
                entry_data[CONF_MODEL] = _read_setting(
                    settings, CONF_MODEL, DEFAULT_MODEL
                )

        return self.async_create_entry(
            title=name or url,
            data=entry_data,
            options=options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow for the given entry."""
        return PriceWatchOptionsFlow()


class PriceWatchOptionsFlow(OptionsFlow):
    """Options flow.

    For SETTINGS entries: single-step form covering provider + currency
    + budgets. Mirrors the first-install settings step.

    For PRODUCT entries: multi-step menu-driven flow. The first step is
    a menu router (basic / parser / provider / maintenance). Each sub-
    step is a focused form. Sub-steps save their fields back to a
    working dict, then return to the menu so users can edit multiple
    sections in one session. "Save and exit" commits.

    NOTE: Do NOT define __init__ accepting config_entry. As of HA 2024.12,
    OptionsFlow exposes config_entry as a read-only property set
    automatically by the framework. Assigning to it raises AttributeError.
    """

    def __init__(self) -> None:
        # Cache the options we're building up across menu sub-steps.
        # Initialized lazily on first step from the live entry options.
        self._working: dict[str, Any] | None = None

    # ---- Entry-type router --------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step. Routes by entry type."""
        if self.config_entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
            return await self._async_step_settings_options(user_input)
        return await self._async_step_product_menu()

    # ---- Settings options (single step) ------------------------------------

    def _settings_seed(self) -> dict[str, Any]:
        """Seed dict of current settings values, keyed by form-field name.

        Used to prefill the provider detail steps with the live config so
        editing feels like editing, not re-entering from scratch. Maps the
        stored CONF_MODEL onto the right form-local model field
        (CONF_MODEL_ANTHROPIC / CONF_MODEL_OPENAI) based on current provider.
        """
        o = self.config_entry.options
        d = self.config_entry.data

        def cur(key: str, default: Any = None) -> Any:
            return o.get(key, d.get(key, default))

        provider = cur(CONF_AI_PROVIDER, PROVIDER_ANTHROPIC)
        extra = cur(CONF_EXTRA_HEADERS)
        return {
            CONF_API_KEY: cur(CONF_API_KEY, "") or "",
            CONF_MODEL_ANTHROPIC: (
                cur(CONF_MODEL, DEFAULT_MODEL)
                if provider == PROVIDER_ANTHROPIC
                else DEFAULT_MODEL
            ),
            CONF_MODEL_OPENAI: (
                cur(CONF_MODEL, "")
                if provider == PROVIDER_OPENAI_COMPATIBLE
                else ""
            )
            or "",
            CONF_BASE_URL: cur(CONF_BASE_URL, "") or "",
            CONF_INPUT_COST_PER_MTOK: cur(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0,
            CONF_OUTPUT_COST_PER_MTOK: cur(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0,
            CONF_MAX_HTML_CHARS: cur(CONF_MAX_HTML_CHARS, 100_000) or 100_000,
            CONF_FORCE_JSON_MODE: bool(cur(CONF_FORCE_JSON_MODE, False)),
            CONF_EXTRA_HEADERS: (
                json.dumps(extra) if isinstance(extra, dict) else (extra or "")
            ),
            CONF_HOME_CURRENCY: cur(CONF_HOME_CURRENCY, "") or "",
            CONF_USER_REGION: cur(CONF_USER_REGION, "") or "",
            CONF_DAILY_BUDGET_USD: cur(CONF_DAILY_BUDGET_USD, DEFAULT_DAILY_BUDGET),
            CONF_MONTHLY_BUDGET_USD: cur(
                CONF_MONTHLY_BUDGET_USD, DEFAULT_MONTHLY_BUDGET
            ),
        }

    async def _async_step_settings_options(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Settings entry options: provider PICKER (radio list) router.

        Same shape as the install flow — a clean 3-way picker that routes
        to a focused detail step — so switching providers post-install is
        just as friendly as first setup. Defaults the radio to the current
        provider.
        """
        if user_input is not None:
            choice = user_input[CONF_AI_PROVIDER]
            if choice == PROVIDER_NONE:
                return await self.async_step_settings_opt_free()
            if choice == PROVIDER_OPENAI_COMPATIBLE:
                return await self.async_step_settings_opt_openai()
            return await self.async_step_settings_opt_anthropic()

        current = self.config_entry.options.get(
            CONF_AI_PROVIDER,
            self.config_entry.data.get(CONF_AI_PROVIDER, PROVIDER_ANTHROPIC),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AI_PROVIDER, default=current
                    ): _provider_choice_selector(),
                }
            ),
        )

    async def async_step_settings_opt_free(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options: Free / no-AI detail."""
        errors: dict[str, str] = {}
        if user_input is not None:
            common, errors = _parse_common(user_input)
            if not errors:
                return self.async_create_entry(
                    title="", data={**_free_config(), **common}
                )
        return self.async_show_form(
            step_id="settings_opt_free",
            data_schema=_free_schema(user_input or self._settings_seed()),
            errors=errors,
        )

    async def async_step_settings_opt_anthropic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options: Anthropic detail."""
        errors: dict[str, str] = {}
        if user_input is not None:
            config, errors = await _validate_anthropic(user_input)
            common, common_errors = _parse_common(user_input)
            errors.update(common_errors)
            if not errors:
                return self.async_create_entry(
                    title="", data={**config, **common}
                )
        return self.async_show_form(
            step_id="settings_opt_anthropic",
            data_schema=_anthropic_schema(user_input or self._settings_seed()),
            errors=errors,
            description_placeholders={
                "docs_url": "https://docs.claude.com/en/docs/about-claude/pricing",
            },
        )

    async def async_step_settings_opt_openai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options: OpenAI-compatible detail."""
        errors: dict[str, str] = {}
        if user_input is not None:
            config, errors = await _validate_openai(user_input)
            common, common_errors = _parse_common(user_input)
            errors.update(common_errors)
            if not errors:
                return self.async_create_entry(
                    title="", data={**config, **common}
                )
        return self.async_show_form(
            step_id="settings_opt_openai",
            data_schema=_openai_schema(user_input or self._settings_seed()),
            errors=errors,
        )

    # ---- Product options (multi-step menu) ---------------------------------

    def _ensure_working(self) -> dict[str, Any]:
        """Initialize the working options dict from live entry on first access.

        Sub-steps mutate this in place; the final menu "save_exit"
        action commits it back to the config entry. Until then, edits
        are pending — closing the dialog mid-flight discards them,
        which matches the HA convention for multi-step options.
        """
        if self._working is None:
            self._working = dict(self.config_entry.options)
        return self._working

    async def _async_step_product_menu(self) -> ConfigFlowResult:
        """The hub. User picks which section of options they want to edit.

        After each sub-step submits, we return here so the user can edit
        additional sections in one session. "Save and exit" commits.
        """
        self._ensure_working()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "basic",
                "parser",
                "provider",
                "maintenance",
                "save_exit",
            ],
        )

    async def async_step_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Basic per-product options: target, interval, paused."""
        working = self._ensure_working()
        if user_input is not None:
            # User chose "back without saving" — return to menu and skip
            # apply. Other sub-steps' pending edits in `working` are
            # preserved.
            if user_input.get(BACK_TO_MENU):
                return await self._async_step_product_menu()
            working[CONF_TARGET_PRICE] = (
                user_input.get(CONF_TARGET_PRICE) or None
            )
            working[CONF_SCAN_INTERVAL] = int(
                user_input.get(
                    CONF_SCAN_INTERVAL,
                    int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                )
            )
            working[CONF_PAUSED] = bool(user_input.get(CONF_PAUSED, False))
            working[CONF_DAILY_ALTERNATIVES] = bool(
                user_input.get(CONF_DAILY_ALTERNATIVES, False)
            )
            return await self._async_step_product_menu()

        target_default = working.get(CONF_TARGET_PRICE)
        schema_dict: dict[Any, Any] = {}
        # voluptuous quirk: passing default=None for a Coerce(float)
        # field causes the form to render a literal "None" string in
        # the input. Omit the default key entirely when the value is
        # unset.
        if target_default is not None:
            schema_dict[
                vol.Optional(CONF_TARGET_PRICE, default=target_default)
            ] = vol.Coerce(float)
        else:
            schema_dict[vol.Optional(CONF_TARGET_PRICE)] = vol.Coerce(float)

        schema_dict[
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=working.get(
                    CONF_SCAN_INTERVAL,
                    int(DEFAULT_SCAN_INTERVAL.total_seconds() / 60),
                ),
            )
        ] = vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES))

        schema_dict[
            vol.Optional(
                CONF_PAUSED,
                default=bool(working.get(CONF_PAUSED, False)),
            )
        ] = bool

        # Daily alternatives auto-refresh. Off by default — the
        # feature has a per-call cost (Anthropic) or compute load
        # (Ollama) so users opt in. Manual on-demand refresh is
        # always available via the find_alternatives service.
        schema_dict[
            vol.Optional(
                CONF_DAILY_ALTERNATIVES,
                default=bool(working.get(CONF_DAILY_ALTERNATIVES, False)),
            )
        ] = bool

        # Back-to-menu escape hatch. See BACK_TO_MENU constant.
        schema_dict[vol.Optional(BACK_TO_MENU, default=False)] = bool

        return self.async_show_form(
            step_id="basic",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_parser(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Parser options: cookies (first-class) + raw custom_parser JSON.

        Cookies edit roundtrips through the custom_parser config so the
        extractor's existing code path (which reads
        custom_parser.request_cookies) keeps working unchanged. Users
        only see/edit the cookie string and never the JSON wrapping.
        """
        working = self._ensure_working()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Back-without-saving (see BACK_TO_MENU constant). Returns
            # to the menu before any validation runs, so a half-typed
            # invalid parser JSON doesn't block the escape route.
            if user_input.get(BACK_TO_MENU):
                return await self._async_step_product_menu()
            cookies = (user_input.get(CONF_COOKIES) or "").strip()
            raw_parser = (user_input.get(CONF_CUSTOM_PARSER) or "").strip()

            # Validate the parser JSON if non-empty. Catch bad JSON
            # early rather than silently storing garbage that fails at
            # the next coordinator tick.
            if raw_parser:
                try:
                    parsed_for_check = json.loads(raw_parser)
                    if not isinstance(parsed_for_check, dict):
                        errors[CONF_CUSTOM_PARSER] = "custom_parser_not_object"
                except json.JSONDecodeError:
                    errors[CONF_CUSTOM_PARSER] = "custom_parser_invalid_json"

            if not errors:
                # Merge cookies into the (possibly empty) parser config.
                # If the user provided raw_parser, that's the new
                # baseline; otherwise use the existing config.
                base_parser = raw_parser or working.get(CONF_CUSTOM_PARSER, "")
                merged = _parser_with_cookies(base_parser, cookies)
                working[CONF_CUSTOM_PARSER] = merged or ""
                return await self._async_step_product_menu()

        return self.async_show_form(
            step_id="parser",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_COOKIES,
                        default=_parser_get_cookies(
                            working.get(CONF_CUSTOM_PARSER)
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CUSTOM_PARSER,
                        default=str(working.get(CONF_CUSTOM_PARSER, "") or ""),
                    ): str,
                    # Back-to-menu escape hatch. See BACK_TO_MENU constant.
                    vol.Optional(BACK_TO_MENU, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_provider(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Per-product AI provider override.

        Three modes:
        - inherit: clear all per-product overrides; coordinator falls
          through to the shared settings entry. Default state.
        - anthropic: override with a specific Anthropic key + model.
          Useful when one product needs a different (cheaper or more
          capable) model than the default.
        - openai_compatible: override with a full OpenAI-compat config.
          Useful when one product is on a different endpoint.

        We DON'T validate credentials here — that would block on a
        slow endpoint and the user is making a free-form choice that
        may not currently work but will once they fix something else
        (e.g. starting a local Ollama). Coordinator will surface
        credential errors on its next refresh as usual.
        """
        working = self._ensure_working()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Back-without-saving (see BACK_TO_MENU constant). Runs
            # before mode evaluation so the user can escape even if
            # they've left required fields empty.
            if user_input.get(BACK_TO_MENU):
                return await self._async_step_product_menu()
            mode = user_input.get(CONF_AI_PROVIDER, PROVIDER_INHERIT)
            if mode == PROVIDER_INHERIT:
                # Clear all per-product provider overrides.
                for k in (
                    CONF_AI_PROVIDER,
                    CONF_API_KEY,
                    CONF_MODEL,
                    CONF_BASE_URL,
                    CONF_INPUT_COST_PER_MTOK,
                    CONF_OUTPUT_COST_PER_MTOK,
                    CONF_MAX_HTML_CHARS,
                    CONF_FORCE_JSON_MODE,
                    CONF_EXTRA_HEADERS,
                ):
                    working.pop(k, None)
                return await self._async_step_product_menu()

            if mode == PROVIDER_ANTHROPIC:
                api_key = (user_input.get(CONF_API_KEY) or "").strip() or None
                if api_key and not api_key.startswith("sk-ant-"):
                    errors[CONF_API_KEY] = "invalid_key_format"
                else:
                    model = user_input.get(CONF_MODEL_ANTHROPIC, DEFAULT_MODEL)
                    working[CONF_AI_PROVIDER] = PROVIDER_ANTHROPIC
                    working[CONF_API_KEY] = api_key
                    working[CONF_MODEL] = model
                    # Clear OpenAI-compat fields so a switch doesn't
                    # leave stale config.
                    for k in (
                        CONF_BASE_URL,
                        CONF_INPUT_COST_PER_MTOK,
                        CONF_OUTPUT_COST_PER_MTOK,
                        CONF_MAX_HTML_CHARS,
                        CONF_FORCE_JSON_MODE,
                        CONF_EXTRA_HEADERS,
                    ):
                        working.pop(k, None)
                    return await self._async_step_product_menu()

            elif mode == PROVIDER_OPENAI_COMPATIBLE:
                base_url = (user_input.get(CONF_BASE_URL) or "").strip()
                model = (user_input.get(CONF_MODEL_OPENAI) or "").strip()
                if not base_url:
                    errors[CONF_BASE_URL] = "base_url_required"
                if not model:
                    errors[CONF_MODEL_OPENAI] = "model_required"

                extra_headers_raw = (
                    user_input.get(CONF_EXTRA_HEADERS) or ""
                ).strip()
                extra_headers: dict[str, str] | None = None
                if extra_headers_raw:
                    try:
                        parsed = json.loads(extra_headers_raw)
                        if not isinstance(parsed, dict):
                            errors[CONF_EXTRA_HEADERS] = "extra_headers_not_object"
                        else:
                            extra_headers = {
                                str(k): str(v) for k, v in parsed.items()
                            }
                    except json.JSONDecodeError:
                        errors[CONF_EXTRA_HEADERS] = "extra_headers_invalid_json"

                if not errors:
                    api_key = (user_input.get(CONF_API_KEY) or "").strip() or None
                    working[CONF_AI_PROVIDER] = PROVIDER_OPENAI_COMPATIBLE
                    working[CONF_API_KEY] = api_key
                    working[CONF_MODEL] = model
                    working[CONF_BASE_URL] = base_url
                    working[CONF_INPUT_COST_PER_MTOK] = float(
                        user_input.get(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0
                    )
                    working[CONF_OUTPUT_COST_PER_MTOK] = float(
                        user_input.get(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0
                    )
                    working[CONF_MAX_HTML_CHARS] = int(
                        user_input.get(CONF_MAX_HTML_CHARS, 100_000) or 100_000
                    )
                    working[CONF_FORCE_JSON_MODE] = bool(
                        user_input.get(CONF_FORCE_JSON_MODE, False)
                    )
                    working[CONF_EXTRA_HEADERS] = extra_headers
                    return await self._async_step_product_menu()

        # Render. Defaults from working dict so re-opening shows the
        # current state.
        current_provider = working.get(CONF_AI_PROVIDER) or PROVIDER_INHERIT
        return self.async_show_form(
            step_id="provider",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AI_PROVIDER, default=current_provider
                    ): vol.In(
                        {
                            PROVIDER_INHERIT: "Inherit from settings (default)",
                            PROVIDER_ANTHROPIC: "Anthropic (Claude)",
                            PROVIDER_OPENAI_COMPATIBLE: "OpenAI-compatible",
                        }
                    ),
                    vol.Optional(
                        CONF_API_KEY,
                        default=working.get(CONF_API_KEY, "") or "",
                    ): str,
                    vol.Optional(
                        CONF_MODEL_ANTHROPIC,
                        default=(
                            working.get(CONF_MODEL, DEFAULT_MODEL)
                            if current_provider == PROVIDER_ANTHROPIC
                            else DEFAULT_MODEL
                        ),
                    ): vol.In(list(ANTHROPIC_MODELS)),
                    vol.Optional(
                        CONF_BASE_URL,
                        default=working.get(CONF_BASE_URL, "") or "",
                    ): str,
                    vol.Optional(
                        CONF_MODEL_OPENAI,
                        default=(
                            working.get(CONF_MODEL, "")
                            if current_provider == PROVIDER_OPENAI_COMPATIBLE
                            else ""
                        ) or "",
                    ): str,
                    vol.Optional(
                        CONF_INPUT_COST_PER_MTOK,
                        default=working.get(CONF_INPUT_COST_PER_MTOK, 0.0) or 0.0,
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_OUTPUT_COST_PER_MTOK,
                        default=working.get(CONF_OUTPUT_COST_PER_MTOK, 0.0) or 0.0,
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_MAX_HTML_CHARS,
                        default=working.get(CONF_MAX_HTML_CHARS, 100_000) or 100_000,
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_FORCE_JSON_MODE,
                        default=bool(working.get(CONF_FORCE_JSON_MODE, False)),
                    ): bool,
                    vol.Optional(
                        CONF_EXTRA_HEADERS,
                        default=(
                            json.dumps(working.get(CONF_EXTRA_HEADERS))
                            if isinstance(working.get(CONF_EXTRA_HEADERS), dict)
                            else (working.get(CONF_EXTRA_HEADERS) or "")
                        ),
                    ): str,
                    # Back-to-menu escape hatch. See BACK_TO_MENU constant.
                    vol.Optional(BACK_TO_MENU, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_maintenance(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Maintenance actions: force discontinued + reset history.

        Unlike the other steps, the values here aren't just persisted
        to options — they invoke coordinator methods that mutate
        runtime state (HA Store, polling interval, sensor data).

        force_discontinued is bi-directional: setting True marks the
        product discontinued (stops polling, freezes price); setting
        False unmarks it and resumes polling.

        reset_history is transient — it doesn't get stored back to
        options. The checkbox is a "do it now" trigger; the next
        time you open this dialog it'll be unchecked again.
        """
        working = self._ensure_working()
        if user_input is not None:
            # Back-without-saving (see BACK_TO_MENU constant). Runs
            # before any coordinator-side calls so a misclick on the
            # menu doesn't accidentally fire force_discontinued.
            if user_input.get(BACK_TO_MENU):
                return await self._async_step_product_menu()
            force_disc = bool(user_input.get(CONF_FORCE_DISCONTINUED, False))
            reset_hist = bool(user_input.get("reset_history", False))

            # Persist the FORCE flag into the working dict (which gets
            # committed on save_exit) AND immediately to the entry so
            # the coordinator's options-read in async_force_discontinued
            # sees the new value.
            working[CONF_FORCE_DISCONTINUED] = force_disc
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=working
            )

            coordinator = self.hass.data.get(DOMAIN, {}).get(
                self.config_entry.entry_id
            )
            if coordinator is not None:
                # Apply force-discontinued only if the value changed
                # (avoid no-op state mutations on every save).
                currently_forced = bool(
                    self.config_entry.options.get(CONF_FORCE_DISCONTINUED, False)
                )
                if force_disc != currently_forced or force_disc:
                    # We always call when force_disc=True (idempotent
                    # set) and only-when-changed for clearing. The
                    # second condition handles the case where a user
                    # turns the toggle on for the first time.
                    try:
                        await coordinator.async_force_discontinued(force_disc)
                    except Exception:  # noqa: BLE001
                        _LOGGER.exception(
                            "async_force_discontinued raised on %s",
                            self.config_entry.entry_id,
                        )

                if reset_hist:
                    try:
                        await coordinator.async_reset_history()
                    except Exception:  # noqa: BLE001
                        _LOGGER.exception(
                            "async_reset_history raised on %s",
                            self.config_entry.entry_id,
                        )
            else:
                _LOGGER.warning(
                    "Maintenance action invoked but coordinator not found "
                    "for entry %s",
                    self.config_entry.entry_id,
                )

            return await self._async_step_product_menu()

        return self.async_show_form(
            step_id="maintenance",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FORCE_DISCONTINUED,
                        default=bool(
                            working.get(CONF_FORCE_DISCONTINUED, False)
                        ),
                    ): bool,
                    # reset_history is transient — a "do it now" toggle,
                    # not a persisted option. The submit handler reads
                    # it but doesn't store it back.
                    vol.Optional("reset_history", default=False): bool,
                    # Back-to-menu escape hatch. See BACK_TO_MENU constant.
                    vol.Optional(BACK_TO_MENU, default=False): bool,
                }
            ),
        )

    async def async_step_save_exit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Commit working options to the entry and close the flow.

        Always called via menu; user_input is unused. Returning
        async_create_entry persists `working` as the new options dict
        and fires the entry update listener, which triggers a
        coordinator refresh via the listener wired up in __init__.py.

        Rising-edge detection: if CONF_DAILY_ALTERNATIVES flipped
        False -> True in this save, fire an immediate one-shot
        alternatives fetch instead of making the user wait up to 6
        hours for the next price tick to trigger one. Fire-and-forget
        via async_create_task so the form submission isn't blocked
        by a ~60s AI call.

        We compare the working value against the entry's pre-save
        options. Initial-creation (no entry yet) is not a concern here
        because save_exit only runs from the per-product options menu,
        which requires an existing entry.
        """
        working = self._ensure_working()

        # Detect False -> True transition on daily_alternatives. The
        # check is deliberately strict (==): treating "missing" as
        # False so a user enabling it for the first time on an entry
        # that never had the key set still triggers a fetch.
        prev_daily = bool(
            self.config_entry.options.get(CONF_DAILY_ALTERNATIVES, False)
        )
        new_daily = bool(working.get(CONF_DAILY_ALTERNATIVES, False))
        should_fire_immediate = (not prev_daily) and new_daily

        if should_fire_immediate:
            coord = self.hass.data.get(DOMAIN, {}).get(
                self.config_entry.entry_id
            )
            # The coordinator is the per-product PriceWatchCoordinator;
            # settings entries don't have one and don't have this option
            # either, so this is doubly safe. Defensive isinstance check
            # avoids a hard import cycle if someone reshuffles types.
            if coord is not None and hasattr(coord, "async_find_alternatives"):
                async def _kickoff() -> None:
                    try:
                        await coord.async_find_alternatives()
                    except Exception:  # noqa: BLE001
                        # Logged inside the coordinator's own error
                        # handling; swallowing here keeps the task from
                        # surfacing as an unhandled exception in HA's
                        # event loop.
                        pass

                self.hass.async_create_task(
                    _kickoff(),
                    name=(
                        "price_watch_daily_alternatives_immediate_"
                        f"{self.config_entry.entry_id}"
                    ),
                )

        return self.async_create_entry(title="", data=working)
