# Price Watch — Project Overview

> A free-by-default, multi-retailer price tracker for Home Assistant. Paste a
> product URL and get price/stock sensors, a rolling history, and alert events —
> all managed from a dedicated sidebar panel. AI extraction is an optional
> fallback, not a requirement.

- **Domain:** `price_watch`
- **Type:** HACS custom integration (`integration_type: service`, `iot_class: cloud_polling`) + a Lit/TypeScript sidebar panel
- **Repo:** [TheIcelandicguy/price_watch](https://github.com/TheIcelandicguy/price_watch)
- **Version:** 0.2.2 (public beta) · **Minimum HA:** 2024.10.0
- **License:** MIT

---

## Table of contents

1. [What it is](#1-what-it-is)
2. [Key features](#2-key-features)
3. [Installation & configuration](#3-installation--configuration)
4. [Usage](#4-usage)
5. [Architecture](#5-architecture)
6. [Reference: services, events, entities](#6-reference-services-events-entities)
7. [Data flow](#7-data-flow)
8. [Development & deployment](#8-development--deployment)
9. [Known limitations & roadmap](#9-known-limitations--roadmap)

---

## 1. What it is

Price Watch tracks the price and stock of product pages on the open web from
inside Home Assistant. Each tracked product becomes its own config entry / HA
device that exposes price, lowest/highest-seen, target-diff and stock sensors,
a product image, a "refresh now" button, and a rolling price history. Home
Assistant `event`s fire on price drops, target hits, new all-time lows,
back-in-stock, on-sale and discontinued transitions so users can build
notification automations.

Extraction is **free by default**: it reads price/stock from a page's
Schema.org `Product` JSON-LD or Open Graph/microdata meta tags, which most
major retailers expose — no account, no API key, no per-call cost. For sites
that render a price but ship no structured data, a **custom parser**
(CSS / regex / JSONPath / raw-JSON API) can be pointed at the price, still for
free. An optional **AI provider** (Anthropic Claude, or any OpenAI-compatible
endpoint including local Ollama / LM Studio) can be added purely as a fallback
for the tricky pages and for smarter discovery.

The project was originally (0.1.0) a single Claude-powered URL tracker; 0.2.0
reframed it as a free-first, multi-retailer tracker with a sidebar panel, with
AI demoted to optional. 0.2.1 added per-card delete (`untrack_product`) and
moved every confirm/alert into a themed in-panel dialog.

## 2. Key features

- **Free-by-default extraction** — JSON-LD / Open Graph first; AI only if configured, and can be set fallback-only so discovery stays free.
- **Multi-retailer listings** — track the same product at several shops as separate *listings* under one product entry, each with its own price/stock/photo/history.
- **Per-product config entries** — every product is an HA device with its own sensors and its own options flow.
- **Discovery / "Search & add"** — a live web search (`price_watch/search` WS command) finds the product across the web, prices the results it can (JSON-LD / meta), filters out review/category/search pages, sorts priced hits first, and lets the user add any with one click.
- **Region-awareness** — a shipping heuristic (`search/region_heuristic.py`) flags (and can hide) listings that won't ship to the user's country, including a per-region block list of retailers verified not to ship there (Komplett for Iceland); a global excluded-domains blocklist drops unwanted hosts.
- **FX conversion** — every price is also reported in the user's home currency via `sensor.<slug>_price_local`, using free frankfurter.dev ECB rates.
- **Smart alerts** — bus events on drop / target / new-low / restock / discount / discontinued; the panel can write the automations for you.
- **The Lit sidebar panel** — add, search, sort, filter, compare and manage everything with no YAML: a custom price-selector editor (with "Test on live page" + an element-picker bookmarklet), cookie capture, a variant/size picker, an alert-builder dialog, and an AI-provider settings editor.
- **Price context** — all-time low / "is at low" flags, a median-of-daily-closes "typical" price, and per-unit pricing (e.g. kr/m).
- **Resilient fetching** — curl_cffi Chrome-131 TLS impersonation, fresh-session retry for bot-walls (Amazon "Continue shopping"), a per-host politeness gap, a global concurrency cap, and block tolerance: a CAPTCHA / 403 / 429 on one poll keeps the last known price instead of flipping the sensors unavailable.

## 3. Installation & configuration

### Install

- **HACS (custom repository):** HACS → ⋮ → Custom repositories → add
  `https://github.com/TheIcelandicguy/price_watch` as category **Integration**
  → install **Price Watch** → restart HA → Settings → Devices & Services →
  **Add Integration** → **Price Watch**.
- **Manual:** copy `custom_components/price_watch/` into HA's
  `config/custom_components/` and restart.
- Requirements (from `manifest.json`): `anthropic>=0.40.0`,
  `openai>=1.40.0`, `beautifulsoup4>=4.12.0`, `curl_cffi>=0.15.0`.
  Depends on the `http` component. Minimum HA **2024.10.0**.

### Two kinds of config entry

Both live under the same domain but behave differently (`const.ENTRY_TYPE_SETTINGS`
vs `ENTRY_TYPE_PRODUCT`):

- **Settings entry** (one, shared) — created on first install. Holds the AI
  provider choice + credentials, home currency, user region, budgets, and the
  global lists (excluded domains, store-offer links, SearXNG URL,
  ai-fallback-only). The first-run config flow is a radio picker — **Free /
  Anthropic / OpenAI-compatible** — that routes to a short provider-specific
  detail step (`async_step_settings_free/_anthropic/_openai`).
- **Product entry** (one per tracked product) — created by pasting a URL
  (`async_step_product` → preview → `async_step_confirm`), by the "shell"
  flow (name-only, listings added later), or by the panel's live-search
  "Track" (`async_step_panel_track`, driven by the `track_product` service).

### Per-product options flow

A menu-router options flow (basic / parser / provider / maintenance) covers
target price, scan interval (min 15 min, default 6 h), custom parser + cookies,
pause / force-discontinued, a per-product AI-provider override ("inherit from
settings" by default), and daily-alternatives settings. Provider credential
resolution (`provider_config.resolve_provider_config`) merges product entry
over settings entry, with a deliberate "no override → read settings live" rule
so switching the global provider updates existing products.

## 4. Usage

1. Open **Price Watch** in the sidebar.
2. **Add product** → paste a URL (optionally paste cookies for bot-walled
   sites), or use **Search & add** to find one. The page is fetched and a
   preview appears; confirm to start tracking.
3. Set a **target price** to be notified when the price drops to/below it.
4. To compare retailers, open a card and **Add listing** (another shop's URL
   for the same item), or add one straight from a Search & add result.

The panel's 🔔 alert dialog writes automations for you (stable ids
`pw_alert_<entry_id>_<trigger>`), which are cleaned up automatically when the
product is removed (`_remove_alert_automations` in `__init__.py`). A store not
working? Use the ✎ editor's custom price selector ("Test on live page" runs the
`price_watch/test_selector` WS command with the real curl_cffi fetch path), or
download redacted diagnostics from the device's ⋮ menu (`diagnostics.py` strips
API keys and cookies).

Example automation on a target hit:

```yaml
alias: Notify on target hit
triggers:
  - trigger: event
    event_type: price_watch_target_hit
actions:
  - action: notify.notify
    data:
      title: "Target hit: {{ trigger.event.data.title }}"
      message: "{{ trigger.event.data.price }} {{ trigger.event.data.currency }}"
      data:
        url: "{{ trigger.event.data.url }}"
```

## 5. Architecture

### Repo layout

```
price_watch/
├── custom_components/price_watch/     # the HA integration
│   ├── __init__.py                    # setup/unload, migration, service registration
│   ├── config_flow.py                 # install + per-product/settings flows, options flow
│   ├── const.py                       # keys, defaults, event/attr names
│   ├── coordinator.py                 # PriceWatchCoordinator (one per product)
│   ├── coordinator_update.py          # UpdateMixin — the fetch/extract/persist loop
│   ├── coordinator_events.py          # EventsMixin — HA bus events
│   ├── coordinator_fx.py              # FxMixin — home-currency conversion
│   ├── coordinator_storage.py         # StorageMixin — v2 Store load/save, listing config
│   ├── coordinator_alternatives.py    # AlternativesMixin — discovery + 24 h alternatives refresh
│   ├── provider_config.py             # AI-provider resolution (product↔settings merge)
│   ├── extractor.py                   # fetch + JSON-LD / Wix-variant / meta / AI pipeline
│   ├── parsers.py                     # custom parser engine (css/regex/jsonpath/raw_json)
│   ├── presets/                       # per-retailer URL→parser presets (tolvutek, elko, rafland, amazon)
│   ├── ai/                            # AIProvider protocol + anthropic / openai-compat impls
│   ├── search/                        # SearchProvider protocol + anthropic-native/ddg/searxng/ai-synth,
│   │                                  #   region_heuristic (shipping), filters (URL junk), enrich (JSON-LD pricing)
│   ├── cookies.py, fx.py, store.py    # cookie normalization, FX cache, per-entry Store
│   ├── listings.py, migration.py      # TrackedListing dataclass, v1→v2 entry migration
│   ├── sensor.py / binary_sensor.py / button.py / image.py   # entity platforms
│   ├── panel.py / websocket.py        # sidebar registration + panel WS API
│   ├── diagnostics.py                 # redacted diagnostics download (strips keys + cookies)
│   ├── services.yaml / translations/  # service schemas, en/is strings
│   └── frontend/price-watch-panel.js  # built Lit bundle (served to the sidebar)
├── panel/                             # Lit + TypeScript source (src/panel.ts, card.ts, utils.ts, types.ts)
├── docs/custom_parsers.md             # custom-parser guide
├── scripts/                           # ad-hoc retailer probe/diagnostic scripts (NOT deploy, untracked)
├── tests/                             # pytest suite (11 modules)
├── CLAUDE.md / check_docs.py          # working notes for the repo + a drift check that fails when they go stale
└── deploy.ps1                         # thin wrapper over the shared E:\tools\deploy-to-ha.ps1
```

### Coordinator design

`PriceWatchCoordinator` (a `TimestampDataUpdateCoordinator[ExtractionResult]`)
is instantiated once per product entry and composed from focused **mixins**
(order matters — they precede the base class so their `_async_update_data`
wins): `AlternativesMixin`, `EventsMixin`, `FxMixin`, `StorageMixin`,
`UpdateMixin`. A single product can hold **N listings**; the coordinator keeps
per-listing runtime state in `self._listings` (history, extremes, last-hash,
discontinued/LKG, cost) plus product-level `self._product_state`
(alternatives). The **primary listing** backs the legacy single-listing API
(`.data`, `.lowest`, `.history`) and keeps legacy entity `unique_id`s; secondary
listings use `{entry}_{listing}_{key}` ids. Persistence is a v2 nested Store
(`store.py`) with built-in v1→v2 migration.

The primary listing is often **implicit**. A product created from a URL (the
config flow or the panel's `track_product`) has its primary only as
`entry.data.url` — nothing writes it into `options["listings"]` until a service
touches it. Its id is deterministic (`derive_listing_id(entry)` =
`l_<last-12-of-entry-id>`), `StorageMixin._ensure_primary_listing` always
declares it when `entry.data.url` is set, and `add_listing` / `edit_listing`
materialize it via `_materialize_primary_listing` before appending anything
else. That invariant is what stops the original listing being pruned as an
orphan the first time a second retailer is added.

Update flow per tick (`UpdateMixin._async_update_data`): short-circuit if
paused / force-discontinued / shell (no listings); otherwise iterate listings,
each via `_async_update_one_listing`, save once, then fire-and-forget a daily
alternatives refresh. A primary-listing failure fails the whole tick; a
secondary failure is logged and the tick still succeeds. One class of failure
is soft: a `TransientBlockError` (CAPTCHA / bot wall / 403 / 429) on a listing
that already has an in-memory result keeps that result and logs a warning,
exactly like the `UNCHANGED` short-circuit — so a retailer that challenges
every other request no longer flaps the sensors between a price and
unavailable.

### Extraction modes

`extractor.extract_product()` is the single entry point, in preference order:

1. **Custom parser** (`parsers.apply_custom_parser`) — if configured and has
   selectors. Types: `css`, `regex`, `jsonpath` (`__NEXT_DATA__`-style state),
   and `raw_json` (POST to a retailer JSON API). Can override
   URL/method/body/headers/cookies and apply chained `transforms`
   (`regex:`, `replace:`, `prefix:`, `coalesce:`, `float`, `int`, `strip`,
   `lower`, `price_clean`). A selector-less parser is treated as
   **cookies-only**: its cookies are lifted and extraction falls through to the
   free pipeline (the Amazon workaround). On parser failure with an AI provider
   set, AI rescue runs on the same HTML.
2. **Wix / Byko variant override** — when `variant_options` is pinned, reads a
   specific option-combo's price from the page's embedded variant JSON.
3. **JSON-LD** (`try_jsonld`) — Schema.org `Product` / `ProductGroup` /
   `@graph`, case-insensitive keys (handles Wix), Shopify `?variant=` matching,
   `AggregateOffer` low-price. Enriched with per-store availability (Húsa /
   JYSK), JYSK strike-through "was" price + size options, and Byko/Húsa product
   numbers. **This is the free default path.**
4. **Open Graph / microdata meta** (`find_meta_price` / `find_meta_image`) —
   used mainly to price discovery results.
5. **AI fallback** (`ai/` providers) — only if an `AIProvider` is configured
   and JSON-LD found nothing. Uses a shared extraction prompt + tool schema
   (`ai/base.py`); recognizes discontinued pages and rejects
   `NO_PRODUCT_FOUND` / bot-check sentinels.

The network layer uses curl_cffi with a pinned `chrome131` fingerprint, a
persistent cookie-accumulating session, a per-host fresh-session escape for
Amazon-style bot-walls (`_looks_like_botwall`), a 5-wide concurrency semaphore
and a 3 s per-host politeness gap. When the fresh-session retry still comes
back blocked, `_raise_if_blocked` raises `TransientBlockError` (a subclass of
`ExtractionError`) rather than a generic error, in both the curl_cffi and the
aiohttp fallback paths; 404/410 and 5xx stay ordinary failures.

### AI & search subpackages

`ai/` defines the `AIProvider` Protocol (`extract_product`,
`validate_credentials`) with `AnthropicProvider` and an OpenAI-compatible
provider (each owns its own cost table). `search/` defines the `SearchProvider`
Protocol and `Alternative` / `SearchQuery` dataclasses, with four backends:
`AnthropicNativeSearchProvider` (Claude `web_search`), `AISynthesizerSearchProvider`
(DDG/SearXNG + any AI), `DuckDuckGoSearchProvider` and `SearxngSearchProvider`
(raw, free). The coordinator/websocket pick the most capable backend the
configured provider supports, falling back to raw DDG in Free mode.

### The Lit panel

`panel.py` registers a `panel_custom` sidebar entry (`module_url`, ES module,
`embed_iframe=False`, cache-busted by bundle mtime) serving
`frontend/price-watch-panel.js`. The source lives in `panel/src`: `panel.ts`
(root `<price-watch-panel>` — bootstraps its own WS connection via
`window.hassConnection`, reads the entity registry, derives `TrackedProduct[]`
from `hass.states`), `card.ts` (`<price-watch-card>` per product), `utils.ts`
(`buildProducts`, formatters, `sparklinePath`), `types.ts`. Built with Rollup +
Lit 3. The panel talks to backend WS commands in `websocket.py`:
`price_watch/search`, `get_provider_settings`, `set_provider_settings`,
`test_selector`, `list_variants`, `exclude_domain`, `list_notify_targets`.
Every confirm and error in the panel goes through one themed in-panel dialog
(0.2.1) rather than the browser's `confirm()` / `alert()`; each card has a
delete button that calls `untrack_product`.

## 6. Reference: services, events, entities

### Services (`services.yaml`, registered in `__init__._register_services`)

| Service | Purpose |
|---|---|
| `price_watch.refresh_now` | Force an immediate check (one product or all). |
| `price_watch.set_target` | Update/clear the target price. |
| `price_watch.set_variant` | Pin a product-level Wix variant (option labels) for entries with no materialized listing. |
| `price_watch.reset_history` | Wipe price history + lifetime extremes. |
| `price_watch.set_paused` | Pause/resume polling (keeps last-known price). |
| `price_watch.find_alternatives` | Run a discovery search (one product or all), optional `max_results`. |
| `price_watch.add_listing` | Add a retailer listing (url, retailer, currency, custom_parser, request_cookies) to a product. |
| `price_watch.remove_listing` | Remove a non-primary listing (deletes its sensors + history). |
| `price_watch.edit_listing` | Edit a listing in place: custom parser, cookies, currency, retailer, variant, unit price, or swap URL. Allowed on the primary. |
| `price_watch.track_product` | Create a product from a URL in one step (panel "Track"). |
| `price_watch.untrack_product` | Remove a whole product — its entry, every listing's entities, its history and its alert automations (panel delete button). |

The first six share a target schema and resolve by `entry_id`, `device_id`, or
all products; the listing services and `untrack_product` take one `entry_id`.

### Events (bus `event` types, payload from `EventsMixin`)

| Event | Fires when |
|---|---|
| `price_watch_price_drop` | Price decreased vs previous. |
| `price_watch_target_hit` | Price reached/crossed the target (primary listing). |
| `price_watch_new_low` | New all-time low for the listing. |
| `price_watch_back_in_stock` | Went from out-of-stock to in-stock. |
| `price_watch_discount` | Retailer's own sale/strikethrough appeared (adds `original_price`, `discount_percent`). |
| `price_watch_discontinued` | Product looks permanently delisted (adds `discontinued_at/reason`, `last_known_price`). |

Common payload: `entry_id`, `listing_id`, `title`, `url`, `retailer`, `price`,
`currency`, `previous_price`, `target`, `image_url`, `in_stock`.

### Entities (per product; `<slug>` is the primary listing)

| Entity | Description |
|---|---|
| `sensor.<slug>_price` | Current price (main sensor; carries the rich attribute set below). |
| `sensor.<slug>_price_local` | Price converted to home currency (primary only). |
| `sensor.<slug>_lowest` / `_highest` | Lifetime lowest / highest seen. |
| `sensor.<slug>_target_diff` | Current price minus target (negative = at/below). |
| `sensor.<slug>_stock_count` | Units in stock where exposed. |
| `binary_sensor.<slug>_in_stock` | Stock availability (prefers numeric count). |
| `binary_sensor.<slug>_discontinued` | Product looks discontinued (device_class problem). |
| `image.<slug>_photo` | Product photo (bytes-mode, fetched via curl_cffi). |
| `button.<slug>_refresh_now` | Refresh this product now. |

The price sensor's attributes include `product_url`, `image_url`, `retailer`,
`currency`, `last_check`, `price_history`, `extraction_method`, `listing_id`,
`target_price`, `paused`, `has_cookies`, on-sale (`original_price`,
`discount_percent`), `store_availability` / `available_stores`, `size_options`,
`product_number` / `description_name`, `unit_price` / `unit_label`,
`price_lowest_ever` / `is_at_low` / `price_typical`, `ships_to_user_region`,
and (primary only) `alternatives` + `alternatives_fetched_at` / `_error`.

## 7. Data flow

From a tracked URL to a price update to an alert:

1. **Schedule** — the coordinator ticks every `scan_interval` (default 6 h;
   first poll after setup/restart is jittered to spread the fleet).
2. **Fetch** — `extract_product` fetches the listing URL through the curl_cffi
   Chrome-impersonation layer (concurrency-capped, per-host spaced, fresh-session
   retry on a detected bot-wall).
3. **Change detection** — the page's text is SHA-256 hashed; if it equals the
   listing's `last_hash`, extraction short-circuits (`UNCHANGED`) and the prior
   result is reused (FX is still recomputed for the primary listing). A
   blocked fetch (`TransientBlockError`) takes the same exit when a prior
   result exists.
4. **Extract** — custom parser → Wix/Byko variant → JSON-LD → meta → AI
   fallback, producing an `ExtractionResult` (`title`, `price`, `currency`,
   `in_stock`, `stock_count`, `image_url`, `original_price`, store/size options,
   unit price, discontinued flags, `method`, `cost_usd`).
5. **Persist & derive** — append fine history (30 pts) and a daily-downsampled
   bucket (180 days), track lowest/highest, convert to home currency
   (`FxMixin`), and fetch/cache the image bytes.
6. **Fire events** — `UpdateMixin` edge-triggers `price_watch_price_drop`,
   `_new_low`, `_back_in_stock`, `_discount`, `_discontinued`, and (primary)
   `_target_hit`, guarding on a known previous so nothing fires on the first
   poll or first poll after restart.
7. **Surface** — sensors/binary-sensors/image re-render from coordinator state;
   the panel reads their attributes; user automations react to the events.

Discovery ("Search & add" / `find_alternatives`) is a parallel path: a
`SearchProvider` returns candidate `Alternative`s, which are enriched with
prices via a bounded JSON-LD/meta pass, filtered (non-shop domains, listing /
category pages, excluded domains), and either returned in the WS reply or
persisted onto the primary price sensor's `alternatives` attribute.

## 8. Development & deployment

```bash
# Backend tests
pip install -r requirements_test.txt
pytest tests/          # extractor, parsers, fx, presets_*, alternatives_filter, diagnostics,
                       # untrack_product, region_heuristic, implicit_primary_listing, transient_block
python check_docs.py   # fails when CLAUDE.md drifts from the source (paths, version, services)

# Panel (Lit + Rollup)
cd panel && npm install && npm run build   # emits custom_components/price_watch/frontend/price-watch-panel.js
npm run watch                              # rebuild on save (hard-refresh the panel)
```

CI (`.github/workflows/validate.yml`) runs hassfest, HACS validation, pytest
(3.12 + 3.13) and ruff on every push. `pytest.ini` and `requirements_test.txt`
configure the test env; `.ruff_cache` is local. `ruff.toml` pins the rule set
on purpose (Ruff's defaults drifted and reddened CI). **pytest cannot collect
on Windows**: `conftest.py` loads `pytest_homeassistant_custom_component`,
which imports `homeassistant.runner`, which imports the POSIX-only `fcntl`.
Linux CI is the real run; locally, test modules that need no HA fixture can be
driven directly.

**Deployment (developer workflow):** the working repo lives on `E:\price_watch`
and is deployed to the HA config's `Z:\custom_components\price_watch` with
`.\deploy.ps1` (`-DryRun` to preview), a thin wrapper over the shared
`E:\tools\deploy-to-ha.ps1`: robocopy `/E /R:2 /W:2` with the standard
exclusions, a newer-on-Z: warning, a list of files Z: has that the repo no
longer does (`/E` never deletes), and a check of the deployed `manifest.json`
version. On Windows an occasional file lock / EPERM on the running component
is worked around by retrying. After copying, restart HA — a config-entry
reload does not re-import changed Python. The panel bundle must be built
(`npm run build`) before the sidebar registers; otherwise `panel.py` logs a
warning and skips registration while the rest of the integration keeps
working.

**Retailer notes:** Icelandic retailers are first-class (Tölvutek, Elko,
Rafland, Byko, Húsasmiðjan, JYSK/Rúmfatalagerinn presets and parsers). The
`presets/` package makes adding a retailer a single new file. Store-offer links
and per-store stock (Húsa "Til á lager", JYSK warehouse asterisk) are handled
specially. **Hard fact to preserve: Komplett does NOT ship to Iceland**, so it
must never be recommended as an Icelandic retailer / alternative — enforced in
`search/region_heuristic.py`: `_REGION_BLOCKED_RETAILERS["IS"]` returns a
confident "doesn't ship" for all three Komplett storefronts, and Iceland is
deliberately outside the `_NORDIC_MAINLAND` group so a `.no`/`.se`/`.dk`/`.fi`
host is never taken as evidence of shipping to Iceland. The
`scripts/` directory holds ad-hoc probe scripts (`retailer_probe.py`,
`jysk_probe*.py`, `amazon_*`, etc.) used to test the fetch/extract path against
live sites — they are diagnostics, not part of the shipped integration.

## 9. Known limitations & roadmap

- **Aggressive bot-walls.** Some big retailers actively block automation
  (Amazon, Best Buy, Home Depot, Lowe's, MediaMarkt at times). The Chrome TLS
  impersonation gets many but never all; where a page loads but hides
  structured data, a one-click custom price selector usually fixes it, and
  pasted browser cookies get through cookie-walled pages (they expire and must
  be re-pasted).
- **"See price in cart" / MAP pricing** genuinely isn't on the page and can't
  be read.
- **Discovery quality depends on the search source** — AI search finds real
  product pages; the free DuckDuckGo path is weaker for niche items (both
  filter out review/category/search pages).
- **FX is product-level.** Secondary listings have their own price, stock,
  photo and history rows in the panel, but `price_local` (home-currency
  conversion) exists for the primary listing only.
- **A block on the very first poll after a restart** still shows the product
  unavailable until a real page comes back — the keep-last-known behaviour
  needs a result from this HA session to keep (`last_result` in storage is
  never written, so there is nothing to rehydrate from).
- **API keys** entered for AI providers are stored in HA's `.storage` in plain
  text (like other HA integrations); a local Ollama endpoint avoids storing a
  secret. AI cost is bounded by content-hash skipping, prompt caching and
  daily/monthly budget caps (~$0.50–$2/month typical for ~10 products; free
  with Ollama).

This is a beta actively soliciting retailer reports (works / doesn't work) and
bug reports via the GitHub issue tracker.
