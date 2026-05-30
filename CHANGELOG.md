# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
