"""Constants for the Price Watch integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "price_watch"

# Entry types — distinguish the shared "settings" config entry (holds
# the AI provider api_key, model, currency, budgets) from per-product
# entries. Both live under the same DOMAIN but behave differently.
ENTRY_TYPE_SETTINGS: Final = "settings"
ENTRY_TYPE_PRODUCT: Final = "product"

# Configuration keys
CONF_API_KEY: Final = "api_key"
CONF_URL: Final = "url"
CONF_TARGET_PRICE: Final = "target_price"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_CUSTOM_PARSER: Final = "custom_parser"
CONF_PARSER_TYPE: Final = "parser_type"  # "claude" | "css" | "jsonpath" | "regex"
CONF_PARSER_CONFIG: Final = "parser_config"
CONF_DAILY_BUDGET_USD: Final = "daily_budget_usd"
CONF_MONTHLY_BUDGET_USD: Final = "monthly_budget_usd"
CONF_MODEL: Final = "model"
CONF_HOME_CURRENCY: Final = "home_currency"

# AI provider selection. When unset, defaults to Anthropic for backward
# compatibility with existing config entries that predate the provider
# abstraction.
CONF_AI_PROVIDER: Final = "ai_provider"
# OpenAI-compatible provider config keys. base_url and model are
# required when ai_provider == 'openai_compatible'. The cost knobs are
# user-supplied because pricing varies wildly across endpoints (OpenAI
# vs Ollama vs OpenRouter vs ...). 0.0 means "free / unknown".
CONF_BASE_URL: Final = "base_url"
CONF_INPUT_COST_PER_MTOK: Final = "input_cost_per_mtok"
CONF_OUTPUT_COST_PER_MTOK: Final = "output_cost_per_mtok"
CONF_MAX_HTML_CHARS: Final = "max_html_chars"
CONF_FORCE_JSON_MODE: Final = "force_json_mode"
CONF_EXTRA_HEADERS: Final = "extra_headers"

# Per-product options flow additions:
# - paused: bool. Skip refresh polling without unloading the entry. The
#   entry stays "loaded" so its history/state survives; the coordinator
#   short-circuits its update method to return last data. Useful when
#   a retailer is temporarily blocking us and we want to silence the
#   error log spam without losing the entry.
# - force_discontinued: bool. Manual override to mark a product as
#   discontinued without waiting for the detector to fire. Same
#   downstream behavior as a real discontinuation: polling stops, the
#   discontinued binary sensor turns on, price shows last known good.
# - cookies: str. First-class field that surfaces the
#   custom_parser.request_cookies field — so the user doesn't have to
#   hand-edit JSON to add/update cookies. Persisted INTO the parser
#   config; this constant is only the form field name.
# - sentinel "inherit from settings" for per-product provider override
#   fields. When the user picks "inherit", we write None into the entry
#   options for that key, and the coordinator's read precedence falls
#   through to the settings entry. When the user picks a real value,
#   we store it on the product entry to take precedence.
CONF_PAUSED: Final = "paused"
CONF_FORCE_DISCONTINUED: Final = "force_discontinued"
CONF_COOKIES: Final = "cookies"

# Alternatives feature flags. When daily_alternatives is True the
# coordinator runs a maybe-refresh check on every _async_update_data
# tick and triggers a fresh search if the last fetch was more than
# ALTERNATIVES_REFRESH_HOURS ago. On-demand fetches via the service
# bypass the TTL.
#
# max_alternatives controls how many results the search provider
# returns at most. Default 5 is small enough to render compactly in
# the panel; the service accepts an override per-call.
CONF_DAILY_ALTERNATIVES: Final = "daily_alternatives"
CONF_MAX_ALTERNATIVES: Final = "max_alternatives"
CONF_ALTERNATIVES_REGION: Final = "alternatives_region"
# ISO 3166-1 alpha-2 country code for the user, used to evaluate
# whether alternatives' retailers ship to them. Lives on the settings
# entry's options by default and can be overridden per-product. Empty
# string disables shipping evaluation. Distinct from
# CONF_ALTERNATIVES_REGION which biases the SEARCH; this filters the
# RESULTS for delivery feasibility.
CONF_USER_REGION: Final = "user_region"

# Global list of retailer hostnames to drop from alternatives results.
# Stored on the settings entry's options as a list of bare hosts (e.g.
# ["amazon.de", "alza.cz"]). Matching is host-suffix based so "amazon.de"
# also excludes "www.amazon.de". Distinct from the ships-to-region
# heuristic: this removes the result entirely rather than flagging it.
CONF_EXCLUDED_DOMAINS: Final = "excluded_domains"

# When True, a configured AI provider is used ONLY as a price-extraction
# fallback (when JSON-LD/free parsing can't read a price). Alternatives
# discovery stays on free DuckDuckGo instead of the AI search path. Lets a
# user keep search free/fast while still having an AI safety net for odd
# product pages. Default False = AI used for both discovery and extraction.
CONF_AI_FALLBACK_ONLY: Final = "ai_fallback_only"

# Per-retailer "seasonal offers" landing pages. Global, on the settings
# entry — a list of {"host", "url"}. A card whose listing host matches one
# gets a "Tilboð hjá <store>" link. Editable in the panel so a store's
# offers URL (e.g. Húsa's rotating seasonal campaign) can be updated without
# a code change. DEFAULTS are the verified pages as of 2026-06; Húsa has no
# stable offers URL so it points at the current seasonal campaign.
CONF_STORE_OFFER_LINKS: Final = "store_offer_links"
DEFAULT_STORE_OFFER_LINKS: Final = [
    {"host": "byko.is", "url": "https://byko.is/tilbod"},
    {"host": "jysk.is", "url": "https://jysk.is/tilbodsvorur/"},
    {"host": "husa.is", "url": "https://www.husa.is/sumarhatid/"},
]

# Approximate fallback: when CONF_USER_REGION is not set, derive a
# country code from the home_currency. Covers the common case where
# a user configures their currency but doesn't know to set this
# additional field. Only includes currencies where the mapping is
# unambiguous (EUR is omitted because it spans 20 countries).
CURRENCY_TO_COUNTRY: Final = {
    "ISK": "IS",
    "NOK": "NO",
    "SEK": "SE",
    "DKK": "DK",
    "USD": "US",
    "GBP": "GB",
    "CAD": "CA",
    "AUD": "AU",
    "JPY": "JP",
    "CHF": "CH",
    "PLN": "PL",
}

# How often the daily-alternatives refresh actually fires. The
# coordinator's main update tick runs more often than this (every
# scan_interval, typically 6h), so we gate the alternatives refresh
# behind a separate TTL. 24h chosen because alternatives don't move
# fast and per-call cost matters.
ALTERNATIVES_REFRESH_HOURS: Final = 24
DEFAULT_MAX_ALTERNATIVES: Final = 5

# Sensor attribute names exposed on the price sensor for alternatives.
ATTR_ALTERNATIVES: Final = "alternatives"
ATTR_ALTERNATIVES_FETCHED_AT: Final = "alternatives_fetched_at"
ATTR_ALTERNATIVES_ERROR: Final = "alternatives_error"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = timedelta(hours=6)
DEFAULT_MODEL: Final = "claude-haiku-4-5-20251001"
# Selectable Anthropic models, newest-cheapest first. Shared by the
# config/options flow and the panel's provider editor so both stay in
# sync. DEFAULT_MODEL must be a member.
ANTHROPIC_MODELS: Final = (
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
)
DEFAULT_DAILY_BUDGET: Final = 0.50
DEFAULT_MONTHLY_BUDGET: Final = 5.00
MIN_SCAN_INTERVAL_MINUTES: Final = 15
MAX_HISTORY_ENTRIES: Final = 30

# Storage
STORAGE_VERSION: Final = 2
STORAGE_KEY_PREFIX: Final = "price_watch"
STORAGE_KEY_BUDGET: Final = "price_watch.budget"

# Events
EVENT_PRICE_DROP: Final = "price_watch_price_drop"
EVENT_TARGET_HIT: Final = "price_watch_target_hit"
EVENT_NEW_LOW: Final = "price_watch_new_low"
EVENT_BACK_IN_STOCK: Final = "price_watch_back_in_stock"
# Fired when a product's on-sale flag flips off→on (the retailer's own
# strikethrough/discount appears). Distinct from EVENT_PRICE_DROP (any
# decrease) — this means a sale specifically started. Payload adds
# original_price + discount_percent.
EVENT_DISCOUNT: Final = "price_watch_discount"
EVENT_DISCONTINUED: Final = "price_watch_discontinued"

# Sensor attributes
ATTR_PRODUCT_URL: Final = "product_url"
ATTR_IMAGE_URL: Final = "image_url"
ATTR_RETAILER: Final = "retailer"
ATTR_CURRENCY: Final = "currency"
ATTR_LAST_CHECK: Final = "last_check"
ATTR_PRICE_HISTORY: Final = "price_history"
ATTR_SKU: Final = "sku"
ATTR_TITLE: Final = "title"
ATTR_STOCK_COUNT: Final = "stock_count"

# HTTP
USER_AGENT: Final = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT: Final = 30.0

# Currency conversion - frankfurter.app, ECB rates, free, no auth
FX_API_URL: Final = "https://api.frankfurter.dev/v1/latest"
FX_CACHE_TTL_HOURS: Final = 24
FX_STORAGE_KEY: Final = "price_watch.fx_rates"

# Cost tracking — each AI provider owns its own pricing table inside
# the corresponding ai/<provider>_provider.py file. const.py used to
# carry Anthropic's table; it moved to ai/anthropic_provider.py when
# the provider abstraction landed.
