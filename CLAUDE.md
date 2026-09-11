# CLAUDE.md — Price Watch

Home Assistant custom integration. Domain `price_watch`, version **0.2.1**,
repo `TheIcelandicguy/price_watch`, branch `main`, HA minimum 2024.10.0.

Source `E:\price_watch` → deployed to `Z:\custom_components\price_watch`.

Before ending a session, run `python check_docs.py` and update this file.

Free-by-default multi-retailer price tracker with a Lit sidebar panel.
Icelandic retailers are first-class and prices are ISK; AI is optional and, on
the extraction path, strictly a last resort.

## Layout that matters

```
custom_components/price_watch/
  __init__.py       setup, migration hook, all 11 service handlers
  const.py          every CONF_/EVENT_/ATTR_ key — read this first
  config_flow.py    ConfigFlow VERSION = 2 (settings / product / shell)
  coordinator.py    PriceWatchCoordinator = 5 mixins + TimestampDataUpdateCoord
  coordinator_*.py  the mixins (map below)
  extractor.py      fetch + extraction cascade (~1950 lines)
  parsers.py        custom-parser engine (css / jsonpath / regex / raw_json)
  presets/          per-retailer auto-config: tolvutek, elko, rafland, amazon
  ai/               AIProvider ABC + anthropic_provider, openai_compat_provider
  search/           duckduckgo, searxng, anthropic_native, ai_synthesizer,
                    region_heuristic, filters (URL/domain junk filters),
                    enrich (JSON-LD price backfill) — the last two are
                    shared by the coordinator and websocket.py
  listings.py store.py fx.py cookies.py migration.py websocket.py panel.py
  frontend/price-watch-panel.js    BUILT artifact — never hand-edit
panel/src/          panel.ts, card.ts, utils.ts, types.ts (Lit 3 + TypeScript)
tests/  11 modules      scripts/  live-site probes, not shipped
```

## Coordinator / mixin map

One `PriceWatchCoordinator` per tracked **product** (not per listing). MRO:

```python
class PriceWatchCoordinator(
    AlternativesMixin, EventsMixin, FxMixin, StorageMixin, UpdateMixin,
    TimestampDataUpdateCoordinator[ExtractionResult],
)
```

| File | Owns |
|---|---|
| `coordinator.py` | init, pause / force-discontinued, target, per-listing accessors, `device_info`, `user_region` |
| `coordinator_alternatives.py` | discovery, search-provider choice, `async_find_alternatives`, 24h TTL refresh. URL filters and JSON-LD enrichment moved to `search/filters.py` / `search/enrich.py` |
| `coordinator_events.py` | every `hass.bus.async_fire` payload (one shape) |
| `coordinator_fx.py` | `price_local` / home-currency conversion |
| `coordinator_storage.py` | v2 Store load/save, `effective_custom_parser`, discontinued restore |
| `coordinator_update.py` | `_async_update_data`, `_async_update_one_listing`, image bytes |
| `provider_config.py` | which `AIProvider` an entry gets (free functions, not a mixin) |

Mixins are plain classes with a `TYPE_CHECKING` block declaring the attributes
they borrow from the concrete coordinator. Keep that convention.

A product holds N listings. `_listings[listing_id]` is per-listing state;
`_state` **aliases** the primary listing's dict, so `self._state[k] = v` also
mutates `_listings[primary][k]`. `_product_state` holds product-wide
alternatives. `_listing_results` is an in-memory-only ExtractionResult cache.

The primary listing is often **implicit**: products from the URL config flow
or the panel's `track_product` (source `panel_track`) have it only as
`entry.data.url`, never written to `options["listings"]`. Its id is
`derive_listing_id(entry)` = `l_<last-12-of-entry-id>`. `_ensure_primary_listing`
auto-declares it whenever `entry.data.url` is set, so it is not pruned as an
orphan once other listings are declared; any service that appends to
`options["listings"]` must first call `_materialize_primary_listing`.

## Extraction: how a page becomes a price

`extractor.extract_product(url, session, ai_provider, custom_parser,
previous_hash, variant_options)` is a **cascade**, not a user-selected mode.
There is no "mode" setting — the mode is whichever step succeeds first.

1. **Custom parser** (cost 0, `method="custom"`) — only if `custom_parser` is
   set AND has `selectors`. A parser with cookies but no selectors is a
   *cookies-only* config: its cookies are lifted into `passthrough_cookies`,
   the parser is dropped, and flow continues at step 3.
   On `ParserError`: if an `ai_provider` exists and type != `raw_json`, AI
   retries against the same body (`method="custom+<provider>"`). If the AI
   also fails, the **original** parser error is re-raised.
2. **Variant override** (cost 0) — only when `variant_options` is set. Tries
   `try_wix_variant` then `try_byko_variant`; no match logs a warning and
   falls through.
3. **JSON-LD** (cost 0, `method="jsonld"`) — taken only if `try_jsonld()`
   yields a truthy `price`. This is the "free" path and the normal one.
4. **AI** (`method=<provider.name>`) — reached only when 1–3 produced nothing.
   If `ai_provider is None` it raises instead: *"No JSON-LD found and no AI
   provider configured for fallback extraction"*.

So **free mode = no API key configured anywhere**: `build_ai_provider()`
returns `None` and the integration is JSON-LD/parser-only. Nothing else
selects it.

`previous_hash` equal to the new content hash raises `ExtractionError`
("UNCHANGED") before any parsing — that is the no-op short-circuit, not a
failure. A bot wall / CAPTCHA body at 2xx, or an HTTP 403/429, raises
`TransientBlockError` (an `ExtractionError` subclass) from
`_raise_if_blocked()` in both fetch paths, after the fresh-session retry.
`coordinator_update.py` treats it like UNCHANGED when a previous result
exists — keeps the last known result, logs a warning, writes nothing — so a
retailer that challenges every other poll no longer flaps the sensors
between a price and unavailable. With no previous result it is an ordinary
`UpdateFailed`. The AI's `NO_PRODUCT_FOUND` / `<UNKNOWN>` / price<=0 sentinels are
rejected as "no product", while `is_discontinued` is a *successful* terminal
result that stops polling.

### AI provider and the fallback-only flag

`ai_provider` is `anthropic` (legacy default) or `openai_compatible`. Keys come
from the shared settings entry unless the product set an explicit override
(`ai_provider`, `model`, `base_url` or `api_key` in its options) — so a global
provider switch isn't shadowed by a stale per-product snapshot. A failed
provider build logs a warning and returns `None`; it never bricks the
coordinator. Default model `claude-haiku-4-5-20251001`; `ANTHROPIC_MODELS` in
`const.py` is the selectable list shared by config flow and panel.

`CONF_AI_FALLBACK_ONLY` affects **discovery only** — it keeps alternatives
search on free DuckDuckGo/SearXNG. It does *not* gate the extraction fallback:
`coordinator_update.py` always passes `self._ai_provider` to `extract_product`.

## Config entries

Two kinds under the same domain, keyed by `entry.data["entry_type"]`:
- `settings` — one shared entry: api_key, model, home_currency, budgets,
  excluded_domains, searxng_url, store_offer_links, user_region.
- `product` — one per tracked product. Every platform's `async_setup_entry`
  early-returns unless `entry_type == "product"`.

`ConfigFlow.VERSION = 2`; `async_migrate_entry` converts v1 (flat options) to
v2 (`options.product` + `options.listings[]`). `_LIVE_OPTION_KEYS`
(paused / force_discontinued / target_price) are read live each tick, so
changing only those skips the entry reload that would wipe in-memory data.

## Services, events, entities

11 services, registered in `__init__.py`, documented in `services.yaml`:
`refresh_now`, `set_target`, `set_variant`, `reset_history`, `set_paused`,
`find_alternatives`, `add_listing`, `remove_listing`, `edit_listing`,
`track_product`, `untrack_product`. The first six share `target_schema`
(`entry_id` and `device_id` both optional = apply to all products).

Events — `price_watch_price_drop`, `_target_hit`, `_new_low`,
`_back_in_stock`, `_discount`, `_discontinued`. Every payload has the same
base shape from `EventsMixin._fire_event`: `entry_id, title, url, retailer,
price, currency, previous_price, target, image_url, in_stock`.
`_discontinued` adds `discontinued_at/_reason`, `last_known_price/_currency`
and `manual`.

Platforms: `SENSOR, BINARY_SENSOR, BUTTON, IMAGE`. Per **listing**: five
monetary sensors (`price`, `lowest`, `highest`, `target_diff`, plus
`price_local` on the primary listing only — FX is product-level), a
`stock_count` sensor, and `in_stock` + `discontinued` binary sensors. Per
product: one `RefreshNowButton` and one bytes-mode `ProductImage` (image CDNs
behind Cloudflare reject HA's aiohttp URL fetcher).

Unique-id rule: the primary listing keeps legacy `{entry_id}_{key}`; secondary
listings use `{entry_id}_{listing_id}_{key}`. **Do not change this** — it is
what preserves entity-registry history.

The panel also drives a WebSocket API in `websocket.py`: `price_watch/search`,
`get_provider_settings`, `set_provider_settings`, `exclude_domain`,
`list_notify_targets`, `test_selector`, `list_variants`.

## Commands

Tests and lint, from `E:\price_watch`:

```bash
pip install -r requirements_test.txt
pytest tests/          # pytest.ini: asyncio_mode=auto, pythonpath=.
pytest tests/ -v --cov=custom_components.price_watch --cov-report=term-missing
ruff check custom_components/price_watch
```

`ruff.toml` pins `select = ["E4","E7","E9","F"]` on purpose — Ruff's defaults
drifted (0.16 turned on `I`) and reddened CI. Don't "modernise" it casually.

Panel build:

```bash
cd panel
npm install
npm run build   # → ../custom_components/price_watch/frontend/price-watch-panel.js
npm run watch   # dev, skips terser
```

Deploy — no committed script, this is the whole procedure, then restart HA:

```powershell
robocopy E:\price_watch\custom_components\price_watch `
         Z:\custom_components\price_watch /E
```

CI (`.github/workflows/validate.yml`): hassfest, HACS validate, pytest on 3.12
and 3.13, ruff — on push to main, PRs, manual, weekly Sunday.

## Gotchas

- **Komplett does not ship to Iceland.** Never recommend it as a retailer or
  alternative for an Icelandic user. `search/region_heuristic.py` enforces
  this in two places: `_REGION_BLOCKED_RETAILERS["IS"]` holds all three
  Komplett storefronts (`.no` / `.se` / `.dk`) and returns a confident
  `False`, and `_NORDIC_MAINLAND` (`NO SE DK FI`) deliberately excludes `IS`,
  so a mainland-Nordic TLD no longer upgrades an Icelandic user's result to
  `True` — it returns `None` and the AI's guess stands. `False` both shows
  the panel's "Doesn't ship" badge and drops the alternative from the card.
  Add further verified retailer→region blocks to `_REGION_BLOCKED_RETAILERS`,
  not to the country groups. `excluded_domains` on the settings entry
  (`CONF_EXCLUDED_DOMAINS`, host-suffix match, empty by default) still exists
  as a per-user override but is no longer the only block.
- **EPERM / file lock on deploy.** robocopy fails on files a running Home
  Assistant holds open (usually `__pycache__` and loaded `.py`). Retry the
  copy; deleting the target `__pycache__` first avoids most of it; otherwise
  stop HA, copy, start.
- `Z:\custom_components\price_watch.v1-rollback` exists and is **v0.1.0** — a
  parked pre-v2-migration copy, not a live component. HA ignores it because
  the folder name isn't a valid domain. Leave it alone.
- `frontend/price-watch-panel.js` is generated. Edit `panel/src/*.ts` and
  rebuild. If the bundle is missing, `panel.py` logs a warning and skips
  sidebar registration — the rest of the integration still loads.
- `requirements_test.txt` omits `curl_cffi` although `manifest.json` requires
  it, so CI never exercises the curl_cffi fetch path — tests pass on the
  aiohttp degrade path only.
- `_IMPERSONATE = "chrome131"` in `extractor.py` is pinned deliberately —
  newer fingerprints get 403'd by Best Buy / B&H. Don't bump it blind.
- Doc drift: `services.yaml` omits `edit_listing`'s `url`, `unit_quantity` and
  `unit_label` (the schema accepts them); `panel/README.md` wrongly claims the
  bundle URL is unversioned. `OVERVIEW.md` is accurate but untracked, as are
  `scripts/` and `.claude/`.
