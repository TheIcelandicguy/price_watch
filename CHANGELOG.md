# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-09

First public beta. Reframes Price Watch from a single Claude-powered URL
tracker into a **free-by-default, multi-retailer price tracker with a sidebar
panel** — AI is now optional.

### Added
- **Free-first extraction.** Reads price/stock from Schema.org `Product` /
  Open Graph data with no AI and no key — the default mode. AI (Anthropic
  **or** any OpenAI-compatible endpoint, including local **Ollama**) is an
  optional fallback, and can be set to fallback-only so discovery stays free.
- **Sidebar panel.** Add, search, sort, filter, compare and manage everything
  from one screen — no YAML or dashboard wiring. Includes a custom
  price-selector editor (with a "Test on live page" button and an
  element-picker bookmarklet), cookie capture, a variant/size picker, an
  alert-builder dialog, and an AI-provider settings editor.
- **Multi-retailer listings.** Track the same product at several shops as
  separate listings under one product, each with its own price/stock/photo.
- **Discovery & "Search & add".** Look a product up across the web, price the
  results that expose a price (JSON-LD or `<meta>`/microdata), filter out
  review/category/search pages, sort priced results first, and add any with
  one click. Region-aware: flags and can hide listings that won't ship to you.
- **Currency conversion** — every price also reported in your home currency
  (`sensor.<slug>_price_local`).
- **Per-store stock** (e.g. Húsasmiðjan, JYSK) and **variant pickers**
  (lumber length, sizes) on supported sites.
- **On-sale detection** — `price_watch_discount` event when a retailer's own
  sale/strikethrough appears; plus `price_watch_discontinued`.
- **Price context** — all-time low / "at low" flags, typical price, and a
  per-unit price (e.g. kr/m), with a manual unit override.
- **Custom parsers** — CSS / regex / JSONPath / raw-JSON, with cookies and
  per-listing currency/retailer/unit overrides, all editable from the panel.
- **SearXNG** as an alternative search source; a global excluded-domains
  blocklist.
- New services: `track_product`, `add_listing`, `remove_listing`,
  `edit_listing`, `set_variant`, `set_paused`, `find_alternatives`.

### Changed
- More resilient fetching: realistic browser TLS impersonation with an
  automatic fresh-session retry for sites that block reused sessions or serve
  an interstitial (Amazon-style "continue shopping", 403/429), plus a
  per-host politeness gap and a global concurrency cap so a large fleet of
  products doesn't burst-hit a store.
- Daily-downsampled long-term history alongside the fine-grained recent
  history.

### Fixed
- Cookie-walled sites with no custom selector no longer fail extraction; a
  cookies-only parser fetches with its cookies and falls through to the
  JSON-LD / AI pipeline.
- `request_cookies` set via `add_listing` / `edit_listing` now actually
  reaches the extractor (stored inside `custom_parser.request_cookies`);
  accepts a header string, a `{name: value}` dict, or a list of cookie dicts.
- Paused products keep their last-known price instead of going unavailable.
- Removing a listing cleans up its entities (no "unavailable" ghost rows).

### Internal
- Coordinator split into focused mixins (events / fx / storage / update /
  alternatives); cookie normalization consolidated into one `cookies` module.
- CI: hassfest, HACS validation, pytest (3.12 + 3.13) and ruff on every push.

## [0.1.0] - 2026-04-29

Initial release.

### Added
- Universal product extraction via Anthropic Claude Haiku 4.5 (with prompt caching).
- Config flow: paste a product URL, confirm extracted preview, set target price and check interval.
- Per-product device with sensors: `price`, `lowest`, `highest`, `target_diff`, `in_stock`.
- Native HA events: `price_watch_price_drop`, `price_watch_target_hit`, `price_watch_new_low`, `price_watch_back_in_stock`.
- Cost optimisations: JSON-LD fallback (free), content-hash skip when page unchanged, prompt caching, configurable scan interval (default 6 h).
- Custom parser support for zero-cost extraction on specific sites: CSS selectors, regex, and JSONPath against `__NEXT_DATA__`-style state objects.
- Persistent price history (last 30 entries) and lifetime extremes per product.
- Services: `refresh_now`, `set_target`, `reset_history`.
- English and Icelandic translations.
- HACS-ready metadata (`hacs.json`, `info.md`).
- CI: hassfest, HACS validation, pytest matrix on Python 3.12 and 3.13, ruff lint and format check.
