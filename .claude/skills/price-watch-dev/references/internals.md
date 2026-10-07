# Internal details (verified against source — 2026-06, re-checked 2026-10-07)

Confirmed by reading current source, with file locations. The code still wins — if a refactor moves something, re-confirm and fix the entry.

## Listings / entity IDs (panel)

- **Entity `unique_id` scheme** (`sensor.py`, `image.py`): the PRIMARY listing keeps the legacy `{entry_id}_{key}` form (back-compat); SECONDARY listings use `{entry_id}_{listing_id}_{key}`, where `listing_id` is `l_<hex>` (12 hex chars in practice).
- **`parseUniqueId()`** (`panel/src/utils.ts`) splits a unique_id: `entryId` is the ULID before the first `_` (ULIDs contain no `_`, so the split is reliable); the remainder matches `^(l_[0-9a-z]+)_(.+)$` → a secondary listing (`{listingId, key}`), otherwise the whole remainder is the `key` (primary). Returns `{entryId, listingId|null, key}`.
- **Primary listing id is deterministic:** `l_<last 12 of entry_id, lowercased>`.

## Coordinator (mixins)

- **`_ensure_primary_listing()`** lives in `coordinator_storage.py` (storage mixin), called after load; **idempotent**. It reconciles `self._listings` (runtime state) against `entry.options.listings` (the declared set), prunes orphans, and aliases `self._state` to the primary listing's dict. Back-compat: if `options.listings` is empty but storage has the deterministic primary id, primary is treated as declared (v1-migrated / single-URL products).
- **Implicit-primary materialization:** a from-scratch / panel-track product has no `listings[]` array; the first `edit_listing` on it (`__init__.py`) materializes the primary from `entry.data.url` so a selector/cookies can attach.

## Provider precedence

- **`resolve_provider_config()`** (`provider_config.py` — *no* leading underscore) + **`build_ai_provider()`**. `AI_CONFIG_KEYS` frozenset = `{ai_provider, api_key, model, base_url, input/output cost, max_html_chars, force_json_mode, extra_headers}`.
- AI-config keys inherit from the **settings entry ONLY**, *unless* the product set an explicit override (it has `ai_provider`/`model`/`base_url`/`api_key` in its own options) — then product-first precedence. Non-AI keys always use product-first. This keeps a global provider switch live instead of a stale per-product snapshot shadowing it.

## Discovery enrichment — two paths, don't confuse them

- **`AISynthesizerSearchProvider._enrich_prices()`** (`search/ai_synthesizer.py`) runs INSIDE `find_alternatives` for the Ollama/OpenAI-compat synthesizer path; **JSON-LD only**. `self._session` is set in `__init__` (line ~190), so the old "AttributeError swallowed inside `gather()` → enrichment silently empty" risk is **closed**. Per-fetch timeout + semaphore; failures leave `price=None`.
- **`search/enrich.py: enrich_alternatives_via_jsonld(hass, alternatives)`** (moved out of `coordinator_alternatives.py` in 0.2.2) is the SHARED path used by the coordinator's `async_find_alternatives` AND the websocket `ws_search`; JSON-LD **plus** `<meta>`/microdata fallback (`find_meta_price`). This is the broader-coverage one. (AnthropicNative-provider results go through this, not the synthesizer's.)

## Misc (confirmed)

- Custom-parser `min_price`/`max_price` out of bound → raises `ParserError` → deliberately drops to the AI fallback rather than committing a bad number (`parsers.py`).
- `try_jsonld` ProductGroup hotfix (`extractor.py`): keeps a `ProductGroup`'s own top-level offer as the preferred candidate (jysk.ie shape) and strips currency symbols in `_offer_price` ("€475" → 475).
- `daily_alternatives` rising-edge: the **options flow** (`config_flow.py`) detects a False→True transition and fires an immediate `async_find_alternatives()` kickoff task; the TTL-gated maybe-refresh lives in `coordinator_alternatives.py`.
