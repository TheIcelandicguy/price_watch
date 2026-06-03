# Search-First Product Tracking — Design Doc

**Status:** Phases 1–4 SHIPPED + IN PRODUCTION. Phase 1/2/3a/3b shipped 2026-05-28;
Phase 4 (panel listing rows) + Phase 3c (per-listing images) + the "Ships to me only"
shipping filter shipped 2026-05-30/31. `async_remove_entry` validated end-to-end
2026-05-31. Phase 5 (production migrate) happened during Phase 1. A large follow-up
wave (variant tracking, cookie capture, free-mode extraction hardening, the FX
home-currency fix, failed-product resilience, and a real test suite) shipped
2026-06-02/03 — see **"Post-Phase-4: shipped reality (2026-06-02/03)"** below for the
authoritative current state. The earlier "Post-3b: shipped reality (2026-05-30/31)"
section remains accurate for its window; the per-phase sections above are the
historical design record.

### Phase 2 sub-phases (2026-05-28, all shipped same evening as Phase 1)

**Phase 2.1 — Per-listing storage architecture:**
- Added `self._listings: dict[str, dict]`, `self._product_state: dict`,
  `self._primary_listing_id: str` to coordinator
- `self._state` becomes an alias for `self._listings[primary_id]` — all
  existing code that mutates self._state continues to operate on the
  primary listing's dict, propagating naturally via shared reference
- `_load_v2_storage` replaces `_flatten_v2_storage` — populates BOTH
  self._listings (per-URL state) and self._product_state (shared)
- `_build_v2_storage` rewritten to iterate over self._listings and
  emit N listings to storage
- `_ensure_primary_listing` helper initializes primary listing if
  missing from storage and aliases self._state to it
- `_empty_listing_state` returns default per-listing fields

**Phase 2.2 — Update loop iteration:**
- New `_async_update_one_listing(listing_id, listing)` helper holds the
  per-URL extraction logic (~150 lines): pre-fetch UNCHANGED check,
  discontinued handling with per-listing LKG, history append, lowest/
  highest tracking, transition events (PRICE_DROP, NEW_LOW,
  BACK_IN_STOCK), target hit (primary only), FX + image (primary only)
- `_async_update_data` becomes an outer iterator (~80 lines) that
  applies product-level shortcuts (paused, force_discontinued) once,
  then calls the helper for each listing
- Primary listing failure raises UpdateFailed (whole tick fails);
  secondary listing failures are logged and the tick succeeds
- All events from the new helper carry `listing_id` + listing URL in
  the event payload so consumers can disambiguate
- `self._listing_results: dict[str, ExtractionResult]` cache holds
  per-listing results (in-memory only, used for "previous" lookups
  and UNCHANGED short-circuits)

**Phase 2.3 — Per-listing sensors:**
- Coordinator gained `listing_ids`, `primary_listing_id`,
  `get_listing_state(id)`, `get_listing_result(id)`, `get_listing_config(id)`
  accessors
- `sensor.py.async_setup_entry` iterates `coordinator.listing_ids` and
  creates 5 monetary + 1 stock-count sensor per listing (4 monetary
  for secondary listings — no price_local, since FX is still product-
  level in Phase 2)
- Primary listing keeps legacy unique_id form `{entry_id}_{key}` for
  back-compat with existing entity registry entries AND the panel's
  unique_id parser (which splits at the first underscore)
- Secondary listings use `{entry_id}_{listing_id}_{key}` — the panel's
  parser stores them under a non-matching key and gracefully ignores
  them, so they don't break the panel
- Secondary listing entity names are prefixed with the retailer:
  `"<Retailer> Price"` etc., for clarity in the entity list
- Each sensor reads state via `coordinator.get_listing_result(self._listing_id)`
  and `coordinator.get_listing_state(self._listing_id)` rather than
  `self.coordinator.data` / `.lowest` / `.history` — those still work
  but route through the primary listing alias
- The price sensor exposes a new `listing_id` attribute so consumers
  can identify which listing a sensor belongs to
- Alternatives attributes (alternatives, alternatives_fetched_at,
  alternatives_error) only appear on the PRIMARY listing's price
  sensor — they're product-level, no value in duplicating across
  listings

**Phase 2 deferrals (still to do in Phase 3):**
- binary_sensor.py, button.py, image.py — still primary-only. The
  in-stock / discontinued binary sensors and the image entity remain
  product-level. Adding per-listing variants is straightforward but
  has zero observable effect until there's a UI to add a second
  listing.
- Config flow rewrite for shell-then-populate add-flow
- add_listing / remove_listing services
- Panel UI for listing rows

**Phase 2 verification:**
- All 3 production entries (Lenovo, Corsair, GIGABYTE) post-restart
  remained in `loaded` (Corsair still `setup_retry` due to pre-
  existing Amazon CAPTCHA, unchanged from before)
- GIGABYTE round-trip confirmed: new history entry appended at
  21:29:45 UTC (Phase 2.2 verification) and another at 21:40:58 UTC
  (Phase 2.3 verification — full path through per-listing sensor
  code), state v2-shape preserved on disk
- Sensors now expose a `listing_id` attribute identifying which
  listing they belong to

### Phase 3a — add_listing/remove_listing services + binary_sensor (2026-05-28)

**add_listing service:**
- `price_watch.add_listing(entry_id, url, retailer?, currency?,
  custom_parser?, request_cookies?)` adds a new listing to an
  existing product entry
- Generates a unique listing_id via `secrets.token_hex(6)` (12 hex
  chars, prefixed with `l_` to match migration-generated primary IDs)
- Defensive: refuses to add a duplicate URL (avoids silent double-polling)
- Updates `entry.options.listings`, then calls `async_reload` so the
  new coordinator + new sensors materialize on the next tick
- services.yaml descriptor exposes it in the HA UI service picker

**remove_listing service:**
- `price_watch.remove_listing(entry_id, listing_id)` removes a listing
- Refuses to remove the PRIMARY listing (primary identity is tied to
  entry creation; delete the entry to remove it)
- Cleans up `entry.options.listings`, drops the listing from the
  in-memory `self._listings` and `self._listing_results`, persists,
  then reloads so HA prunes the per-listing entities

**Bug fix (critical for Phase 3a):**
The Phase 2.1 `_ensure_primary_listing()` only ensured the primary
listing existed in `self._listings`. After add_listing wrote a new
listing to `entry.options` and triggered reload, the new coordinator's
`_load_v2_storage` read storage (which had no entry for the new
listing) and didn't create runtime state for it. Sensors then iterated
`coordinator.listing_ids` (which is keyed off `self._listings`) and
the new listing was invisible.

Fix: extended `_ensure_primary_listing()` into a full sync:
1. Collect declared listing IDs from `entry.options.listings`
   (always including primary as a baseline)
2. Listings declared in options but missing from `self._listings`
   → create empty runtime state via `_empty_listing_state()`
3. Listings in `self._listings` but NOT declared in options
   → prune (orphan cleanup with logging)

Entry options is now the declarative source of truth for WHICH
listings exist; `self._listings` is the runtime cache, kept in sync.

**Per-listing binary_sensor:**
- `binary_sensor.py` refactored to iterate `coordinator.listing_ids`
- Each listing gets its own `in_stock` + `discontinued` entities
- Primary listing keeps legacy unique_id form for back-compat
- Secondary listings get `{entry}_{listing}_{key}` unique_ids with
  retailer-prefixed names (e.g. "Newegg In stock", "Newegg Discontinued")
- DiscontinuedSensor's extra_state_attributes now read per-listing
  state (lkg_*, discontinued_at) — discontinuation is independent
  across listings (Komplett can delist while Newegg keeps selling)

**Phase 3a verification:**
- Tested end-to-end: removed manually-added test listing via
  `remove_listing`, added Newegg back via `add_listing` (proper service
  call from HA), verified 5 new sensors + 2 new binary_sensors all
  materialized and showing live extracted data from Newegg ($219 USD)
- GIGABYTE entry now legitimately tracks 2 listings via the service-
  based flow: Komplett (2230 NOK) + Newegg (219 USD)
- All 4 production entries in `loaded` state (Corsair came back from
  setup_retry)

### Phase 3b — Shell-then-populate config flow + coordinator handling (2026-05-28)

**Config flow rewrite:**
- `async_step_user` for product entries now shows a menu via
  `async_show_menu(step_id="user", menu_options=["product", "shell"])`
  with translations rendering as:
  - "Add by URL (paste a product link, integration fetches details)"
  - "Add by name (create empty entry, add retailer URLs later)"
- The first-install path (no settings entry yet) still routes
  directly to `async_step_settings` unchanged — only product-
  creation invocations get the menu
- New `async_step_shell`: asks for product name only (no URL),
  creates entry with `entry.data.url = ""` and
  `entry.options.listings = []`
- Uniqueness keyed off `"shell:<name.lower()>"` (no URL to collide
  on, so name-based uniqueness is the alternative)
- Translations added to both `en.json` and `is.json` (Icelandic);
  `name_required` error added to the config error namespace

**Coordinator shell-safe handling:**
- `_ensure_primary_listing()` rewritten with three-way primary
  resolution:
  1. Prefer the deterministic primary_listing_id when present in
     `self._listings` (back-compat for v1-migrated entries)
  2. Otherwise use the first listing in `self._listings` and
     update `self._primary_listing_id` to track it (covers shell
     entries whose first listing was added later with a random ID)
  3. If `self._listings` is empty (shell with no listings), point
     `self._state` at a throwaway sentinel dict not in
     `self._listings` — legacy code that reads `self._state[X]`
     gets defaults, writes don't persist (no listing to persist to)
- `_async_update_data()` guards on empty listings:
  ```python
  if not self._listings:
      _LOGGER.debug("%s: no listings configured (shell entry), "
                    "skipping refresh", self.entry.entry_id)
      return self.data  # may be None — DataUpdateCoordinator accepts that
  ```
- Net effect: shell entries stay `loaded`, no setup_retry, no
  UpdateFailed; sensors materialize when the first listing is added
  via `add_listing` service and a reload triggers fresh sensor
  creation against the now-populated `self._listings`

**Note on shell-first sensors:**
When the first listing is added to a shell entry via `add_listing`,
its randomly-generated listing_id won't match the deterministic
primary_listing_id. The three-way primary resolution promotes it
to runtime primary, so it gets legacy unique_id form
(`{entry_id}_{key}`) rather than listing-prefixed. This means the
first listing always looks like the "primary" to the panel and to
sensor consumers, regardless of which retailer it represents — a
consequence of the panel still expecting legacy unique_ids until
Phase 4 lands.

**Smoke test (pending Davíð UI confirmation):**
1. Settings → Devices & Services → + Add Integration → "Price Watch"
2. Menu should show two options:
   - "Add by URL (paste a product link, integration fetches details)"
   - "Add by name (create empty entry, add retailer URLs later)"
3. Pick the second option → enter a name (e.g. "Test shell product")
4. Entry should be created in `loaded` state with NO sensors
5. Call `price_watch.add_listing` service:
   ```yaml
   service: price_watch.add_listing
   data:
     entry_id: <new_shell_entry_id>
     url: https://www.komplett.no/product/1234567
   ```
6. After reload, sensors should materialize + first refresh extracts
   price

### Post-3b: shipped reality (2026-05-30/31)

Everything below shipped AFTER the Phase 3b writeup and is live in production.
This section is the authoritative "what's actually deployed" record; the
per-phase design sections above are the historical plan.

**Phase 4 — panel UI for listing rows (commit history through 2026-05-30):**
- The product card renders a Listings section: each listing is a row with a
  PRIMARY badge (primary only), sparkline, stock chip, and price; secondaries
  carry a `×` remove control (primary cannot be removed from the card).
- Panel code: `panel/src/{types,utils,card,panel}.ts` — `parseUniqueId`,
  `buildListing`, `renderListings`/`renderListingRow`.
- The unique_id parser handles both legacy `{entry}_{key}` (primary) and
  extended `{entry}_{listing}_{key}` (secondary) forms.

**Phase 3c — per-listing images (commit `60e19d9`, 2026-05-31):**
- Each tracked listing gets its OWN photo entity. `coordinator.py` caches image
  bytes per `listing_id` (the three product-level scalars became dicts keyed by
  listing_id: `_listing_image_bytes`, `_listing_image_content_type`,
  `_listing_cached_image_url`).
- `image.py` creates one `ListingImage` per listing — primary keeps the legacy
  unique_id `{entry}_photo`; secondaries use `{entry}_{listing}_photo`.
- Panel: `Listing.imageProxyUrl` / `imageBroken`; rows render a 32px thumbnail
  (placeholder when the entity is `unavailable`).
- The product-level `image_bytes` / `image_content_type` accessors are now
  back-compat shims over the primary listing's per-listing bytes.

**"Ships to me only" shipping filter (commit `2bd89a7`, 2026-05-31):**
- Panel-wide header toggle (persisted to `localStorage` under
  `price-watch:hide-non-shipping`) that hides options the shipping heuristic is
  confident won't reach the user's region.
- Applies to BOTH AI alternatives (`shipsToUserRegion === false`) AND tracked
  listings. For listings, `sensor.py` computes a per-listing `ships_to_user_region`
  attribute via the same `search/region_heuristic.evaluate_shipping`
  (ai_guess=None → only speaks on ground truth, e.g. Newegg→IS = won't ship).
- The PRIMARY listing is never hidden. `null`/unknown is always kept visible.
  Each section shows "N hidden (don't ship to your region)".
- Reuses the authoritative `evaluate_shipping` heuristic rather than duplicating
  shipping logic in TypeScript.

**Post-3b hotfixes (all live):**
- **configuration_url shell-safety:** `device_info` returns `None` (not `""`)
  for shell entries with no listing URL — HA's device registry rejects empty
  string as an invalid URL. Falls back to entry URL → primary listing URL → None.
- **URL-entry sensor regression fix:** `_ensure_primary_listing` now auto-declares
  the deterministic primary for "Add by URL" entries (entry.data.url set but
  options.listings never populated) so sensors materialize on first setup. Shell
  entries (empty URL + no listings) still fall through to the sentinel path.
- **ProductGroup → hasVariant JSON-LD fix:** `extractor.try_jsonld()` handles
  Shopify/Shelly `ProductGroup` schema with nested `hasVariant`.
- **Alternatives price enrichment:** `search/ai_synthesizer.py` enriches alt
  prices from JSON-LD.
- **Orphaned-listing fix:** `remove_listing` (`__init__.py`) now calls
  `er.async_remove` on entities whose unique_id starts with
  `{entry_id}_{listing_id}_` — previously the listing was dropped from
  options+storage but its entities lingered as "unavailable" orphans that the
  panel rendered as un-dismissable ghost rows. The primary's legacy
  `{entry_id}_{key}` form never matches the prefix, so the primary is safe.

**`async_remove_entry` — VALIDATED end-to-end (2026-05-31):**
- Deleting a product config entry cleans up: the per-entry Store file
  `.storage/price_watch.{entry_id}`, all its entities, and its device, with no
  orphans. The settings entry is skipped (no URL/listings/storage file).
- Validated with a throwaway shell entry populated via `add_listing` (real
  storage file ~1142 B, 10 entities, 1 device), deleted via HA's normal DELETE
  path: storage gone ~1s, entities 10→0, device 1→0, config entry→0, production
  untouched.

**Phase 5:** Production migrate already happened during Phase 1.

**Author:** Claude + Davíð (conversation)
**Estimated effort:** 7–12 hours across 4–5 sessions (Step 6 revised down — see Q6 DECIDED)
**Date to revisit:** Tomorrow, with fresh eyes

---

### Post-Phase-4: shipped reality (2026-06-02/03)

A large follow-up wave landed after the search-first refactor was in
production. This is now the authoritative "what's deployed" record. All
commits are on `main` (pushed to origin); the test suite passes (43 tests).

**Variant tracking (Wix stores) — `431296f`, picker `98937f3`:**
- Sites like athom.tech (Wix) embed EVERY variant's price in the page with no
  per-variant URL — variant selection is client-side JS the server fetch never
  triggers. `extractor.try_wix_variant()` reads the embedded `options` (selection
  id→label) + `productItems` (each combo's `optionsSelections` + price) and
  resolves a pinned combo's price (selling price = lower of `price`/`comparePrice`
  when on sale, robust to both Wix conventions).
- Pinned per-listing via `TrackedListing.variant_options`, OR product-wide via
  the new `set_variant` service for from-scratch/panel-track entries that have no
  materialized `listings[]` array. `coordinator._variant_options` mirrors
  `_custom_parser` as the product-level fallback for the primary listing.
- Panel ⚙ picker: `price_watch/list_variants` WS command (`extractor.list_wix_variants`)
  returns the option groups + concrete combos + the currently-pinned combo; the
  card's ⚙ button opens dropdowns with a live price preview. Save routes to
  `set_variant` (primary) or `edit_listing.variant_options` (secondary).

**Cookie capture — merged from `claude/price-watch-chrome-extension-qTO74` (`24543fc`):**
- The extractor reads cookies from EXACTLY one place: `custom_parser.request_cookies`
  (stored as a header string, converted to a dict at fetch time via `cookies.py`).
- THE critical fix: a selector-less ("cookies-only") parser lifts its cookies,
  sets `custom_parser=None`, and falls through to the standard JSON-LD → AI
  pipeline — so a cookie-walled page (Amazon-style "returning visitor" content)
  is read normally instead of hard-failing the free tier on an empty CSS parse.
  Cookies are ORTHOGONAL to the rest of the parser in `edit_listing` (a selector
  edit must not wipe cookies; the panel never sees the secret cookie value).
- `has_cookies` boolean attribute; `coordinator.effective_custom_parser()` is the
  single tolerant read boundary (JSON-string vs dict, primary fallback).
  Note: the standalone Chrome-extension design (`docs/` design note) was NOT built;
  only the in-tree cookie plumbing shipped.

**Free-mode extraction hardening (no AI needed):**
- **Capitalized JSON-LD keys (`189e313`):** Wix emits `"Offers"`/`"Availability"`;
  `extractor._ci_get()` does a case-insensitive Schema.org lookup.
- **AggregateOffer (`112d15e`):** sites that advertise a price RANGE (e.g.
  logitech.com) emit an `AggregateOffer` with no `price`, only `lowPrice`/
  `highPrice`. `extractor._offer_price()` falls back to `lowPrice` (what a
  shopper pays) then `highPrice`.
- **Amazon preset (`presets/amazon.py`) hardened (`76ff0de`, `ada2f90`, `ea116be`):**
  `parsers._apply_regex` now accepts a LIST of patterns per field, tried in
  PRIORITY order (first match wins) rather than leftmost-in-HTML. The Amazon
  price strategies are ranked: formatted strings (`displayPrice`, `olpMessage`
  "from $X") first; raw JSON numerics (`priceToPay`/`priceAmount`/`buyingPrice`)
  ONLY with a decimal point so an integer-cents value (4999 = $49.99) can't 100×
  the price; generic `.a-offscreen` last (it grabs the first price on the page).
- Reality check: Amazon's served markup VARIES between fetches — the preset gets
  many pages right but can't be made 100% reliable in free mode; JS-rendered
  buy-box prices need AI. Clean stores (JSON-LD / static price) "just work."

**Failed-product resilience — `5deda99`, `9badc8d`:**
- A product whose first fetch fails (no JSON-LD, cookie wall, parser not
  configured) used to raise `ConfigEntryNotReady` → `setup_retry` → NO entities,
  NO panel card — hiding the very product that needs fixing, with no way to reach
  the ✎ editor. Now `async_setup_entry` calls `async_refresh()` (records the
  failure without raising) and sets the entry up anyway; the card shows in an
  "unknown" state and the coordinator keeps retrying.
- The PRIMARY price sensor stays AVAILABLE (state "unknown") whenever there's a
  URL, and exposes `product_url`/title in `extra_state_attributes` even with no
  result — HA strips ALL attributes from an `unavailable` entity, which would
  otherwise hide the URL the editor's "Test on live page" button needs.
- `edit_listing` MATERIALIZES the implicit primary listing (deterministic id
  `l_<last-12-of-entry-id>`, from `entry.data.url`) when it's not yet in
  `options["listings"]`, so the first selector/cookie edit on a panel-track
  product has somewhere to land instead of failing "Listing not found".

**FX / home-currency conversion fix — `b794b39` (the nastiest bug):**
- `price_local` was ALWAYS unavailable for every product. Root cause: the FX
  cache `Store` was built with the product-data `STORAGE_VERSION`, which got
  bumped 1→2 for the v2 model — orphaning every version-1 fx cache file so
  `Store.async_load` raised `NotImplementedError` ("no migration") on every load.
  The exception escaped `convert()` and was swallowed as `None` upstream,
  silently disabling ALL conversion; the cache could never refresh because
  `_load()` died before `_save()` was reached.
- Fixes: dedicated `_FX_STORE_VERSION = 1` (permanently decoupled from product
  storage); defensive `_load()` (any failure → refetch, never breaks conversion);
  and `convert()` now CROSS-RATES through whatever base the cached matrix has
  (`amount * rate_to / rate_from`), so one ECB matrix in any base serves every
  pair it lists, with a stale matrix as a usable fallback. Verified live: Logitech
  89.99 USD → 11 093 ISK. Covered by `tests/test_fx.py`.

**Panel additions:**
- **Exclude-site button + verify links (`a09c541`):** each Search & Add result is
  a clickable link (opens the page to verify) with an "Exclude site" button that
  appends the host to the global blocklist (`price_watch/exclude_domain` WS) and
  drops it from results. `ws_search` already filters the blocklist, so future
  searches honor it.
- **Settings shortcut (`23c7984`):** header "🛠 Settings" button navigates to the
  HA Price Watch integration page via the client-side router (panel renders in the
  main document, `embed_iframe=False`).
- **"doesn't ship" badge** on listing rows when `shipsToUserRegion === false`.

**Test suite + infra — `2dc3759`, `d9b69ed`:**
- `tests/test_fx.py` (new): cross-rate, stale fallback, version-decoupling guard.
- `tests/test_parsers.py`: priority-list regex + `price_clean` format cases.
- `tests/test_extractor.py`: AggregateOffer cases.
- `pytest.ini` (new): `asyncio_mode=auto` (required by
  pytest-homeassistant-custom-component) — the repo previously had no pytest
  config, so the suite errored at fixture setup. `requirements_test.txt` gained
  `openai` (imported unconditionally at module load).
- Run from repo root in a Linux env (Windows lacks `fcntl`): a WSL venv works.
  **43 passed.**

---

## Session log

**Session 1 (2026-05-26 evening) — COMPLETE**
- All 11 questions documented; 9 of 11 decisions captured (Q9-doc and Q10-doc strawmen unchallenged, accepted as proposals)
- Phase 1 Step 1: `listings.py` written, `TrackedListing` dataclass smoke-tested
- Phase 1 Step 2: `migration.py` written with both `migrate_entry_v1_to_v2` and `migrate_storage_v1_to_v2`
- 5 issues caught in dry-run iteration and fixed: leaked api_key, empty titles, stringified custom_parser, lifted min/max bounds, lifted cookies
- short_name derivation upgraded from retailer-default to product-title-cleaned
- Dry-run against all 3 production entries (Lenovo / Corsair / GIGABYTE): all migrations clean, round-trip lossless, idempotency verified
- Backups taken: `.storage` snapshot + code snapshot + `Z:\custom_components\price_watch.v1-rollback` deployed copy + `G:\price_watch` independent-drive copy
- Step 3 audit completed — identified 11 things to handle, including the **critical finding that Step 3 alone breaks the coordinator** (storage shape mismatch). Forces Step 3 + Step 4 together or shim approach.

**Session 2 (2026-05-28) — COMPLETE**
- Chose option α (pragmatic refactor): coordinator stays single-listing-flat in memory,
  storage migrates to v2 nested shape. Sensors and config_flow unchanged.
- Bumped STORAGE_VERSION 1→2 in const.py
- Bumped PriceWatchConfigFlow.VERSION 1→2 in config_flow.py
- Added `async_migrate_entry` in __init__.py:
  - Settings entries: explicit `async_update_entry(version=2)` (HA doesn't auto-bump on return True)
  - Product entries: deterministic listing_id from entry_id last 12 chars, calls `migrate_entry_v1_to_v2`
- Updated migration.py: top-level options preserved alongside v2 nesting (eliminates need for
  coordinator entry-shape changes). min_price/max_price/cookies mirrored to listing level,
  not removed from parser blob (parsers.py v1 code path still finds them).
- Added `_PriceWatchStore(Store)` subclass in coordinator.py with `_async_migrate_func` override
  that calls `migrate_storage_v1_to_v2` on v1 → v2 transitions
- Added `_flatten_v2_storage` (v2 nested → flat self._state) and `_build_v2_storage`
  (flat → v2 nested) helpers. Only modified `async_load` and `_async_save`; all 8 callers
  of `_async_save` work unchanged.
- Pre-restart checks: offline simulation of full migrate→flatten→modify→save→re-flatten
  round-trip against all 3 production entries; HA `ha_check_config` passed.
- HA restart at 20:01 — clean reload, all 4 entries (Settings/Lenovo/Corsair/GIGABYTE)
  in `loaded` state. Storage migrated to v2 on disk. All sensors updating, history
  preserved, alternatives preserved.
- Backups in place if rollback ever needed:
  - `Z:\.storage\pre-phase1-20260526-212119\` (storage)
  - `E:\price_watch\.backups\pre-phase1-20260526-212119\` (code)
  - `Z:\custom_components\price_watch.v1-rollback` (deployed code, ready to swap)
  - `G:\price_watch` (independent-drive snapshot)

**Session 3 (2026-05-28) — COMPLETE**
- Phase 2: Multi-listing sensors per product (N listings → N sensors; secondaries
  use `{entry}_{listing}_{key}` unique_ids, primary keeps legacy `{entry}_{key}`)
- Phase 3a: add_listing / remove_listing services + per-listing binary_sensors
- Phase 3b: shell-then-populate config flow (Add by URL / Add by name)

**Session 4+ (2026-05-30/31) — COMPLETE** (see "Post-3b: shipped reality" above)
- Phase 4: Panel UI — listings as rows under each product card
- Phase 3c: per-listing image entities + per-listing image byte cache
- "Ships to me only" shipping filter (panel toggle + per-listing
  `ships_to_user_region` sensor attribute)
- Hotfixes: configuration_url shell-safety, URL-entry sensor regression,
  ProductGroup JSON-LD, orphaned-listing entity cleanup
- `async_remove_entry` validated end-to-end (storage + entities + device, no orphans)

**Remaining (not blocking):**
- Corsair/Amazon entry chronically flaps into `setup_retry` (Amazon CAPTCHA);
  plan: pause it, later add MicroCenter/Pangoly as an alt listing (would also
  exercise the shipping filter since MicroCenter is US-only)
- `coordinator.py` split into focused modules (in progress 2026-05-31)

---

---

## Problem statement

Price Watch's current data model is **"track one URL forever."** Each config entry
points at a single URL; the integration polls that URL every N minutes and records
the price. Alternatives are a post-hoc feature bolted on top.

This model fights us when:

- **The chosen URL becomes hostile** (Amazon's anti-bot tripped tonight, leaving
  the Corsair entry stuck in `setup_retry` even though the same product is happily
  trackable at Pangoly / MicroCenter / Newegg).
- **The user actually wants to compare prices across retailers** but our UI shows
  one card per URL, so tracking the same product at 3 retailers creates 3 unrelated
  cards with no shared concept of "this is the same thing."
- **Adding a product is friction-heavy** — you have to find the URL yourself,
  paste it in, then HOPE that URL stays scrapable. The alternatives feature already
  produces the exact list the user could have picked from in the first place.

Davíð's reframe: **a "product" is a search query, not a URL.** You describe what
you want to track; the integration searches; you select which listings to track.
Each tracked listing has its own price history, but they share a "this is the
same product" identity.

---

## Goals

In rough priority order:

1. **Reduce friction to add a product.** Type a query, pick from search results,
   done. URL pasting becomes a fallback for power users, not the default.
2. **Make multi-retailer tracking first-class.** If the user tracks Pangoly + MicroCenter
   for the same RAM kit, the UI should show that as one product with two listings,
   not two cards.
3. **Survive hostile retailers gracefully.** Losing one listing (Amazon CAPTCHA-ing)
   should not break the product — the other listings keep ticking.
4. **Preserve everything we shipped tonight.** Alternatives discovery, JSON-LD
   enrichment, region-aware shipping flags, min_price sanity check, daily refresh
   — all should keep working, ideally with minimal changes.

## Non-goals (explicit)

- We are NOT building a price-comparison engine for browsing. The user picks what
  to track; we don't try to be Pangoly.
- We are NOT solving the Amazon AJAX-rendered price problem. If a listing's URL
  is hostile, the listing fails. The user can remove it.
- We are NOT building cross-currency conversion in the core. Prices stay in their
  native currencies; the UI can compare same-currency listings via delta, others
  side-by-side.

---

## Proposed data model

### Today's model
```
ConfigEntry (1) ──── PriceWatchCoordinator (1) ──── price sensor (1)
                                  └── price_history[]
                                  └── alternatives[]
```

One entry, one URL, one history, one sensor. Alternatives are an attribute on
the sensor, not first-class trackable items.

### Proposed model
```
ConfigEntry (1) ──── PriceWatchCoordinator (1) ──── price sensor (N)
                          └── TrackedListing (N)         └── one per listing
                              ├── url
                              ├── retailer
                              ├── currency
                              ├── price_history[]
                              ├── extraction_config (cookies, custom_parser, etc.)
                              └── shipping eligibility cache
                          └── product_metadata
                              ├── query (text the user used to find it)
                              ├── canonical_title
                              ├── canonical_sku (optional)
                              ├── target_price (shared across listings)
                              └── alternatives_search_config (region, max_results)
```

One entry = one **product**, holding many tracked listings. Per-product config
(target price, alternatives region, scan interval) is shared. Per-listing config
(URL, cookies, custom parser, currency) is isolated. Each listing has its own
price sensor and history.

### Why this shape

- **Listings are isolable.** Amazon CAPTCHA-ing affects one listing's polling;
  the product as a whole keeps working.
- **Product is the unit of user intent.** "I want to track this RAM kit" is the
  intent; which retailers carry it is implementation.
- **Sharing config makes sense.** target_price ("alert me below 250 NOK") is a
  property of the product, not the retailer. Scan interval is the user's polling
  preference, not the retailer's.
- **Per-listing isolation is necessary.** Cookies for Amazon don't apply to
  Komplett. The custom_parser for one is wrong for the other. Currency differs.

---

## Open questions (the hard part)

### Q1. What does "the same product" mean operationally?

When the user searches "Corsair Dominator Titanium 32GB DDR5-6000 CL30 Gray" and
we return 5 listings, are they really the same product? The alternatives feature
already wrestles with this and assigns confidence scores. Our heuristics earlier
tonight caught a real case: Corsair.com listed the SKU as gray in URL but white
in body text — same SKU, possibly different variants.

**Sub-questions:**
- Do we let the user track listings that the AI flagged as low-confidence matches?
- If two listings disagree on price by 10x, is that the same product or a parser
  bug?
- Manufacturer pages (gigabyte.com) usually don't have prices — should they be
  selectable as a tracked listing at all?

**Proposed answer:** Trust the user. Show confidence scores, let them pick. Add
a "this isn't actually the same product" feedback mechanism that removes the
listing. Don't auto-reject.

### Q2. How do existing entries migrate?

There are currently 3 product entries (Lenovo, Corsair, GIGABYTE) and 1 settings
entry. Each product entry today is one-URL-one-history. After the refactor each
should become "one product with one tracked listing (the existing URL)."

**Options:**
- **(a) Automatic migration on upgrade.** On HA restart with new code, detect
  v1-shape entries and rewrite them into v2 shape. Existing history preserved
  under the new "listing" wrapper. No user action.
- **(b) Manual migration via a one-shot service.** Provide a `price_watch.migrate_v1_to_v2`
  service the user runs once.
- **(c) Side-by-side.** v1 and v2 entries coexist; new entries use v2, old ones
  keep working with old code paths. Eventually deprecate v1.

**Proposed answer:** (a). Migration code lives in `__init__.py:async_migrate_entry`
which HA calls automatically when entry version increments. Test on a backup
first.

**DECIDED: (a) — auto-migration on first restart with new code, via
async_migrate_entry on entry version bump.**

**Risk:** If migration has a bug, every existing entry breaks at once. Mitigation:
HA's `async_migrate_entry` is designed for this; we keep a v1 snapshot in
`.storage/core.config_entries.bak-pre-migration-YYYYMMDD-HHMMSS` from our own
explicit backup before HA's upgrade kicks in.

### Q3. Sensor entity naming

If a product has 3 listings, we need 3 sensors. Names like:
- `sensor.corsair_dominator_pangoly_price`
- `sensor.corsair_dominator_microcenter_price`
- `sensor.corsair_dominator_newegg_price`

But the user typed "Corsair Dominator Titanium 32GB DDR5-6000 CL30 Gray." Do we:
- (a) Auto-slug the search query?
- (b) Let the user provide a short name during creation ("Corsair RAM")?
- (c) Use the retailer name only and let the area/device grouping carry product
  identity?

**Proposed answer:** (b) — ask the user for a short product name during add-flow.
Default it to a slug of the search query. Sensor entity_ids are
`sensor.{product_slug}_{retailer_slug}_price`. Device names group them per-product.

**Friendly name:** `<Product short name> @ <retailer>` (e.g. "Corsair RAM @ Pangoly")

**DECIDED:** Ask the user for a short name; default to the **retailer's display
name** (not the search-query slug) so single-listing products read naturally.
Sensor convention: single-listing products use `sensor.{product_slug}_price`;
multi-listing products use `sensor.{product_slug}_{retailer_slug}_price`. This
minimizes sensor entity_id churn during migration of the three existing
single-listing entries.

### Q4. Per-listing vs per-product config — exact split

Re-listing the split:

**Per-product (shared across listings):**
- product_id, query, short_name, canonical_title
- target_price, target_price_currency
- alternatives_search_config (region, max_results, daily_alternatives toggle)
- user_region (or inherit from settings)
- AI provider override (rare; usually inherits settings)
- created_at, paused (paused stops all listings)
- force_discontinued

**Per-listing (isolated):**
- url, retailer, listing_currency
- custom_parser, request_cookies (per-URL config)
- min_price, max_price (per-listing sanity bounds)
- scan_interval (?? — see Q5)
- last_price, price_history, last_check, extraction_method
- listing_paused (one listing can be paused without pausing the product)
- ships_to_user_region (cached heuristic result for THIS listing)

**Edge case:** What if listings have different currencies? Target price is in
NOK but one listing is in USD? Either we convert (no, we said no conversion),
or the target alerts fire per-listing in matching-currency mode only.

**DECIDED (Q4 target_price scope):** Per-product, currency-locked. The product
carries one target_price value and one target_price_currency. Target alerts
fire ONLY for listings whose listing_currency matches target_price_currency.
Listings in other currencies are tracked and displayed but never trigger the
target alert. Rationale: cross-currency conversion is a rabbit hole (live
rates, fees, exchange spread); user almost certainly cares about ONE currency
they actually pay in.

Implementation notes:
- Add-flow asks for target_price + currency together (currency defaults to the
  first selected listing's currency).
- target_price_currency is part of per-product config (see config split above
  — added to "Per-product" list).
- Sensors in the product expose `target_met: bool` only when their currency
  matches. Sensors in non-matching currencies expose `target_met: null`
  (distinguishable in dashboards/automations from a real "not met" state).

### Q5. Scan interval — per-product or per-listing?

Arguments for per-product: it's the user's polling-aggressiveness preference.
"Check this product every 6h" makes sense as one decision.

Arguments for per-listing: some retailers are slow / rate-limited / hostile.
Amazon should be polled less aggressively than Komplett.

**Proposed answer:** per-product, with an override per-listing. Default to the
product's value; user can dial down a specific listing if it's getting blocked.
This adds complexity but matches reality.

**DECIDED (Q5 scan interval):** (b) — per-product with optional per-listing
override. UI surfacing: the per-product options form shows one scan_interval
field as today. Per-listing override is hidden behind an "advanced settings"
toggle on each listing's options sub-step, so the default UI stays clean.
Override is None by default; when set, it wins for that listing's poll cadence.

### Q6. Add-flow UX — step by step

```
Step 1: "What do you want to track?"
        - Text input: search query
        - Optional URL input: paste-a-URL-as-seed (we extract a title and search
          for that)

Step 2: [backend searches via AI synthesizer + DDG + enrichment + region heuristic]
        Show progress: "Searching 5 retailers..."

Step 3: Results screen
        Show all alternatives with:
        - title, retailer, price (or null), confidence, ships-to-region badge
        - checkbox per row
        - "Track selected" button
        - "None of these — let me paste a URL" escape hatch

Step 4: "Name this product"
        - Short name input (default: slug of search query)
        - Target price input (optional)
        - Alternatives region (default: from settings)

Step 5: Commit. Create entry. Create N sensors.
```

**Friction risk:** Step 3 is the new heart of the flow but it's a 60-second wait
while AI runs. We should show partial results as DDG comes back, then update
with AI confidence and prices as they arrive. Streaming UI in a config flow is
hard (HA's flow protocol is request/response). May need to break into two flow
steps: "Searching..." spinner step that polls.

**DECIDED (Q6 add-flow UX):** (c) — search is NOT integrated into the add-flow.
Add-flow is the SHELL creation only:

```
Step 1: "What do you want to track?"
        - Search query (free text)
        - Optional URL paste (extracts retailer + title)
Step 2: "Name this product"
        - Short name (default: retailer display name if URL pasted; else
          slug of search query)
        - Target price + currency (optional)
        - Alternatives region (default: from settings)
Step 3: Commit. Create entry with product metadata but ZERO listings.
        Sensors are created lazily as listings are added.
```

Populating listings happens after creation via the existing alternatives
panel UI (the ✓ships badges, refresh button, etc. we already shipped). The
panel card for a fresh product shows "No listings yet — click search to find
retailers" with the refresh button prominent. User clicks search, sees the
familiar alternatives list, picks which ones to track.

**Rationale:**
- Reuses every panel-side feature we already shipped tonight: the alternatives
  rendering, refresh button, ✓ships/✗no-ship badges, JSON-LD enrichment status.
- No streaming-progress-in-config-flow problem to solve (R4 in the risk
  register goes away).
- The add-flow stays under 3 seconds; the user controls when the slow ~60s
  search happens.
- Distinction is clean: config flow = configuration; panel = data interaction.

**Trade-off accepted:** A new product card briefly shows "empty / search to
populate" state for ~60s after creation. This is also a teaching moment for
the search UX — the user immediately sees how to add more listings later.

**Implementation note for Phase 3:** the add-flow becomes drastically simpler
than the original draft. Two steps + commit. No "search results screen" step,
no checkboxes-in-form, no polling-spinner step. This lifts Phase 3 from a
~2-3h estimate to closer to ~1-1.5h.

**Implementation note for Phase 4:** the panel needs a new "empty product"
state for cards with zero listings. Existing alternatives-row rendering
becomes the "untracked search results" rendering with a "Track this" button
per row that promotes a search result to a tracked listing.

### Q7. Adding/removing listings on an existing product

User's tracked the Corsair RAM at Pangoly + MicroCenter. Six months later they
notice Newegg dropped the price. They should be able to:
- (a) Open the product, see "search again to find new listings," pick Newegg from
  results, add it.
- (b) Manually paste a Newegg URL to add directly.

Likewise, removing a listing (Amazon went hostile, just delete it) should leave
the product intact with the remaining listings.

**Implementation:** Per-product options flow has an "Add listing" and "Remove
listing" set of actions, both of which mutate the per-product listings array.

**DECIDED (Q7 add/remove listings):** (b) — both search and URL-paste are
available; search is the primary action.

UI surfacing on existing product cards:
- "Search again" button is the prominent / primary action. Reuses the
  alternatives panel UI from earlier tonight (refresh button, ✓ships badges,
  enrichment, etc.) — same code path as a fresh add.
- "Paste URL" is the secondary fallback action, hidden behind a smaller
  button or expanded panel. For users adding retailers the search couldn't
  find or non-standard sources.

Remove listing:
- Each listing row has a remove control (small ✗ icon or hover-revealed
  button).
- Click triggers a confirmation dialog: "Remove this listing? Price
  history for this listing will be deleted." Yes / Cancel.
- Yes removes the listing from the product's listings array, removes the
  corresponding sensor entity from HA, and deletes that listing's
  price_history from the coordinator's Store. Other listings on the same
  product are unaffected.
- The last remaining listing CAN be removed; the product is then in
  "empty / search to populate" state (same as a freshly created product).
- Removing a product entirely is a separate action (the HA "Delete entry"
  on the integrations page), not a per-listing UI flow.

### Q8. Panel UI — what does the card look like?

Today: one card per entry, showing price + history sparkline + alternatives section.

Tomorrow with N listings per product, options:

- **(a) One big card per product, showing each listing as a row** (like alternatives
  today, but the listings are tracked). Price comparison side-by-side. Best for
  "show me my products." Each row has its own mini-chart.
- **(b) One card per listing, grouped under a product header.** More vertical
  space but clearer per-listing detail.
- **(c) One card per product showing the cheapest current listing; click to expand
  to see all listings.** Compact summary view + drill-down.

**Proposed answer:** Start with (a). Each row in the card is a listing with its
current price, delta vs cheapest, confidence (if it was from alternatives), and
shipping badge. One sparkline at the top shows the cheapest-across-listings
over time.

**DECIDED: (a) — one card per product, listings as rows.**

### Q9. What happens to the alternatives feature?

It IS the search engine now. The "find alternatives" button on an existing
product becomes "search again to find more listings to track." Mechanically the
backend is the same; conceptually it's part of add-flow, not a separate feature.

The alternatives sensor attribute disappears (it was an attribute on the price
sensor — now there is no single price sensor). Replaced by "untracked search
results" data on the coordinator, surfaced in the panel under "search again."

### Q10. Service API changes

Today's services:
- `price_watch.refresh` — refresh one or more entries
- `price_watch.set_target` — set target_price on an entry
- `price_watch.reset_history` — wipe history on an entry
- `price_watch.find_alternatives` — kick off alternatives search

New services needed:
- `price_watch.add_listing(entry_id, url)` — add a listing to a product
- `price_watch.remove_listing(entry_id, listing_id)` — remove a listing
- `price_watch.search_for_listings(entry_id)` — re-run search, return candidates

`refresh` and `reset_history` need to be plumbed per-listing OR per-product.
Default per-product (refreshes all listings, resets all listing histories).

### Q11. Search engine choice — what do we actually search?

The alternatives feature (which becomes the add-flow's search engine) currently
uses **DuckDuckGo HTML scraping → AI synthesis → JSON-LD enrichment → region
heuristic**. That works today and tonight proved it. But the search backend
choice is worth naming explicitly so we don't end up tweaking it without
thought.

**Options surveyed:**

- **DuckDuckGo (current).** Free, no API key, no rate limit yet observed. Result
  count ~10-15 per query; snippet quality is uneven (European retailer meta
  descriptions often omit price, which is why enrichment was so important).
  No structured product data — just (title, URL, snippet) tuples, with the AI
  doing all "is this the same product" judgment.
- **Google Custom Search Engine (CSE) API.** 100 free queries/day, $5/1000
  after. Returns higher-quality structured results than DDG. Requires API key
  and CSE creation in Google's dashboard. For our use case (3-10 products ×
  daily refresh × ~1 search per refresh = 10-30 queries/day), free tier covers
  forever. Sweetener: a hand-curated CSE with ~30-40 retailer domains
  (komplett.no, tolvutek.is, elkjop.no, proshop.no, newegg.com, microcenter.com,
  amazon.com, amazon.ca, etc.) biases results toward known retailers and
  filters out aggregator junk.
- **Brave Search API.** ~$5/month for 2000 queries. Independent index. Privacy-
  respecting. Predictable cost but no free tier last we checked.
- **SerpAPI / SearchAPI / Serper.** Commercial Google-scraping middleware.
  ~$50/month for 5000 queries. Highest quality, expensive, third-party between
  you and Google.
- **Anthropic native web_search tool.** Already wired in as
  `AnthropicNativeSearchProvider`. Returns extracted content not just snippets.
  Costs Anthropic credits — your account balance was $0 at last check, so this
  requires a top-up before use.
- **Bing Web Search API.** Microsoft retired it in August 2025. Dead. Don't
  pursue.
- **Direct retailer scraping.** Skip search engines, hit known retailer search
  endpoints directly (Komplett's search API, Newegg's, etc.). Per-retailer
  code, fragile, doesn't solve hostile retailers (Amazon still hostile).

**Proposed answer:**

- **Primary:** Keep DuckDuckGo as the default. Free, working, no setup friction
  for users.
- **Optional secondary (later phase):** Add Google CSE as an opt-in search
  provider with a hand-curated retailer allowlist. User provides API key + CSE
  ID in settings; if both present, prefer CSE; fall back to DDG on quota
  exhaustion or error.
- **Not pursuing:** Brave (cost), SerpAPI (expensive), direct scraping
  (fragile), Bing (dead).

**Reasoning:**

The search-engine choice is the least interesting part of the system. DDG
works. Google CSE would marginally improve quality (~10-20% lift in result
relevance). Not game-changing. The actual quality work — AI confidence scoring
for product matches, JSON-LD enrichment for prices, region heuristic for
shipping — is what makes search useful, and that's already done.

This means **Q11 is not a Phase 1 blocker.** The refactor should ship with
DDG as-is. Adding Google CSE becomes a polish task for after Phase 5 lands,
or a fork-off side project if a user wants better search quality before then.

**The AI's role stays the same:** validate that results are the actual same
product (SKU matching, variant detection), assign confidence, filter out
aggregators via the region heuristic. The AI's value isn't search — it's
**judgment about what counts as a match**. That's hard for any pure-search
approach, and it's what makes our pipeline more valuable than just "show me
DDG results."

---

## Migration plan

### Phase 0: Preparation (no code) (~30min)
- This doc, reviewed and amended
- Snapshot current production state (3 entries + their histories + the panel
  state) for regression testing
- Backup `.storage/core.config_entries` and `price_watch.*` files
- Define test cases:
  - Lenovo entry migrates cleanly, panel renders
  - Corsair entry migrates with its broken Amazon URL, listing paused for sanity
  - GIGABYTE entry migrates, alternatives keep working
  - New product added via search flow works end-to-end
  - Add listing to existing product works
  - Remove listing works

### Phase 0.5: Test instance prep (no Price Watch code) (~1-2h)
The Hyper-V backup HA at 192.168.0.237:8237 has been off for some time and is
the chosen rollback safety net for Phase 1. Must be brought to a usable state
BEFORE Phase 1 ships.

Steps (own session, before Phase 1):
- Boot the Hyper-V VM
- Update HA OS / HA Core (may be 6+ months behind production; could surface
  breaking changes that need manual recovery)
- Sync HACS to the same version as production
- Sync custom_components from production: copy Z:\custom_components\price_watch
  (current code, BEFORE the refactor) to the test instance
- Copy a snapshot of production's .storage to the test instance
- Verify all 4 entries load and run cleanly on the test instance with the
  current (v1) code
- Document any drift between test and production

Exit criteria: test instance runs current Price Watch code with production data,
all entries loaded, panel renders. THIS is the known-good baseline against which
Phase 1's migration code will be tested.

### Phase 1: Backend refactor — coordinator + data model (~2-3h)
- Add `TrackedListing` dataclass with fields above
- Refactor `PriceWatchCoordinator` to hold `listings: list[TrackedListing]` instead
  of a single URL
- Update `_async_update_data` to iterate over listings, fetch each, store per-listing
- Update HA Store layout — bump storage version, add per-listing history blocks
- Write `async_migrate_entry(hass, entry)` that converts v1 → v2

**Verify after Phase 1:** Existing entries still load, sensors still update,
alternatives still fetch. Internally everything is v2-shaped but only one
listing per product, so external behavior unchanged.

### Phase 2: Sensor entities — multi-listing support (~1-2h)
- One sensor per listing instead of one per entry
- Naming convention from Q3
- Device grouping per product
- Migration: rename existing sensor to follow new convention WITHOUT breaking
  history (use `ha_set_entity` rename + preserve entity_id mapping)

**Verify after Phase 2:** Existing products show one renamed sensor that still
works. New products can have multiple sensors.

### Phase 3: Config flow — search-first add (~2-3h)
- New `async_step_user` is the search query input
- New `async_step_search_results` runs the search and shows checkboxes
- New `async_step_finalize` asks for short name + target price
- New per-product options flow with "Add listing" / "Remove listing" / "Search
  again"
- Old "paste a URL" flow becomes a sub-step in async_step_user

**Verify after Phase 3:** Can add a new product by search. Can paste URL as
fallback. Existing entries still editable.

### Phase 4: Panel UI (~1-2h)
- New card layout from Q8(a)
- Per-listing row rendering with shipping badge, delta, mini-chart
- "Search again" button on cards
- Remove listing UX
- Streaming progress during add-flow search
- **Price display redesign (noted 2026-05-26):** Replace the current
  "highest / lowest / current" three-stat layout with a single
  prominent current price. Show change indicator only when the price
  has moved since the last observation: red arrow + "+$X" (or local
  currency) for an increase, green arrow + "−$X" for a decrease.
  No indicator when unchanged. Applies to both single-listing and
  multi-listing cards. Hover/long-press reveals lifetime high/low
  as secondary info (current behavior, just not prominent).

**Verify after Phase 4:** Panel feels correct on all three migrated products.
Add-flow is end-to-end usable.

### Phase 5: Polish & migrate production (~1h)
- Migrate the real 3 entries on production HA
- Fix any rough edges discovered
- Update memory notes
- Document new model

---

## What stays the same

Reassuring list of things we don't have to touch:

- **AI synthesizer** (`search/ai_synthesizer.py`) — already does the work.
  Just gets called from a different place (add-flow instead of attribute refresh).
- **Region heuristic** (`search/region_heuristic.py`) — already correct. Gets
  applied to listings during add-flow instead of to attribute alternatives.
- **JSON-LD enrichment** — works as-is per listing.
- **Extractor + custom_parser + min_price/max_price** — per-listing extraction
  is the same code, just called per listing in the coordinator loop.
- **AI provider abstraction** — untouched.
- **Settings entry** — untouched. user_region, home_currency, ai_provider all
  inherited as before.

---

## Phase 1 architecture (post-ship reference, 2026-05-28)

The pragmatic decisions made during Phase 1 implementation, captured so
Phase 2+ work picks up cleanly.

### The "single-listing-flat" call

Phase 1 storage is v2-shaped (`{listings: {<id>: {...}}, product: {...}}`)
on disk, but the coordinator's in-memory `self._state` stays the same flat
shape it had under v1 (`{history: [...], lowest, highest, ...}`). The
translation happens only at the load/save boundary via two helpers:

- `_flatten_v2_storage(stored)` — v2 nested → flat. Called from `async_load`.
- `_build_v2_storage()` — flat → v2 nested. Called from `_async_save`.

This deferred the "iterate over listings" work to Phase 2 while letting the
storage shape, deterministic listing_id, and entry-options nesting all land
in production. Sensors and the panel were untouched.

### Why options are duplicated (top-level + nested)

`migrate_entry_v1_to_v2` preserves every key that was at top-level
`entry.options` AND also adds the new `product` and `listings` namespaces.
The duplication is intentional: it lets the coordinator's existing code
keep reading `entry.options.get(CONF_TARGET_PRICE)` etc. without any
changes, while new v2-aware code (Phase 2+) can read from the nested
shape. The migration is a one-way bridge — v1 readers still work.

Drift IS possible: if a user changes target_price after migration,
`async_set_target` writes to the top-level key and NOT to `product.target_price`.
For Phase 1 this is harmless because the coordinator only reads top-level.
Phase 3 (config_flow rewrite) is the right time to remove the top-level
duplicates and write to product/listings exclusively.

### Deterministic listing_id derivation

`f"l_{entry.entry_id[-12:].lower()}"` is the formula. Used in two places
that MUST agree:

1. `async_migrate_entry` in `__init__.py` — assigned to
   `entry.options.listings[0].id` when migrating
2. `_PriceWatchStore` and `_derive_listing_id` in `coordinator.py` — used
   as the nesting key for storage migration AND for in-memory state lookup

If these ever diverge, the coordinator would load v2 storage and find an
empty listing under the wrong key. The 12-char ULID suffix gives plenty
of entropy and the all-lowercase normalization avoids case mismatches.

### The settings-entry skip

`async_migrate_entry` short-circuits on `entry.data["entry_type"] ==
"settings"` because the settings entry has no URL, no listings, and no
storage file. Without the skip, `migrate_entry_v1_to_v2` would produce a
corrupted v2 settings entry with an empty-URL listing. The skip explicitly
calls `hass.config_entries.async_update_entry(entry, version=2)` because
returning `True` alone doesn't auto-bump the version in modern HA.

### Storage migration callback

`_PriceWatchStore` is a `Store[dict[str, Any]]` subclass that overrides
`_async_migrate_func`. The Store's version is `STORAGE_VERSION = 2`; when
HA loads a v1 file the override calls `migrate_storage_v1_to_v2(old_data,
listing_id=self._listing_id)`. The listing_id is captured at Store init
(passed via constructor kwarg) — no closure scope to worry about.

### Backwards-incompatible storage changes are a one-way door

Once the integration writes v2 storage, rolling back to v1 code will
cause HA to refuse loading the storage ("future version") and the
coordinator will start with empty state. **Price history is NOT lost** —
it's on disk, just unreadable by old code. Rollback requires restoring
`.storage/core.config_entries` AND `.storage/price_watch.<entry_id>`
from the pre-migration backups, then swapping the integration code.

## Risk register

**R1: Migration corrupts existing data.** Mitigation: explicit backup, dry-run
on a fresh HA instance with copied .storage first, do production migration only
after the new code works on a test instance.

**R2: New sensor entity_ids break user automations / dashboards.** Some users
(Davíð) have existing dashboards using `sensor.corsair_dominator_...amazon_com_price`.
Renaming = broken dashboards. Mitigation: keep old entity_ids as the canonical
"primary listing" sensor; new listings get new entity_ids. HA's entity rename
preserves history; references in automations/scripts are NOT auto-updated though.
Need a "rename map" document for the user.

**R3: Multi-sensor-per-entry is unusual in HA.** Most integrations are 1:N at
the integration level (one MQTT integration, many sensors) not at the entry
level. The entry-as-product pattern with N child sensors is more like a hub
integration (Hue bridge → many lights). HA supports it, but config flow UX for
"edit this child" is awkward. Mitigation: options flow handles listings via a
sub-menu pattern (similar to what we already have).

**R4: Streaming search progress in config flow is hard.** HA's config flow is
request/response — there's no "show partial results" idiom. Mitigation: do the
search in a separate background task during async_step_search_results, show a
spinner step that polls until ready, then render results. Or fall back to "wait
60s for the form to load" UX, which is bad but works.

**R5: We never get to Phase 5.** Multi-session projects have a high abandonment
rate. Mitigation: ensure each phase is independently shippable. After Phase 1,
existing behavior is preserved; we can stop there if life happens.

---

## Decisions to make before any code

Some now resolved (marked DECIDED). Strawman proposals remain on the open ones.

1. Auto-migration on first restart with new code? **DECIDED: yes (auto-migrate
   via async_migrate_entry on entry version bump).**
2. Short name during add-flow? **DECIDED: yes — ask the user for a short product
   name; default to the retailer's display name (NOT the search query slug) so
   that single-listing products read naturally ("Komplett GIGABYTE Z890" rather
   than "gigabyte-z890-gaming-x-wifi7-hov...amazon-com"). When the user has
   multiple listings under one product, the per-listing sensor friendly name
   becomes "<product short name> @ <retailer>".**
3. Sensor naming convention? **DECIDED: use the product's short name (decision
   #2) as the slug base; per-listing sensors use
   `sensor.{product_slug}_{retailer_slug}_price`. Single-listing products keep
   the simpler form `sensor.{product_slug}_price` to minimize sensor renames
   during migration.**
4. Scan interval per-product with optional per-listing override? **DECIDED: yes (per-product is the visible default; per-listing override hidden behind "advanced").**
5. target_price scope across listings with mixed currencies? **DECIDED: per-product, currency-locked. Target alert fires only for listings matching the target currency; others tracked but never alert.**
6. Add-flow UX — search-in-form vs shell-then-populate? **DECIDED: (c) shell-then-populate. Add-flow only creates an empty product (2 steps: query + name/target). User populates listings from the panel's existing alternatives UI after creation.**
7. Add-listing flow: search vs URL paste? **DECIDED: both, search primary. URL paste is a secondary action behind a smaller button. Remove listing shows confirmation dialog.**
8. Per-listing vs per-product pause? **DECIDED: both available. Product pause is OR-overriding — when product is paused, no listing polls regardless of its own paused state.**
9. Service API additions: add_listing, remove_listing, search_for_listings (proposed: yes — unchanged)
10. Keep alternatives as a separate feature or fold into search? (proposed: fold in — unchanged)
11. Panel card style? **DECIDED: (a) one card per product, listings as rows.**
12. Sensor naming convention? **DECIDED: single-listing `sensor.{product_slug}_price`; multi-listing `sensor.{product_slug}_{retailer_slug}_price`. Short name defaults to retailer display name on add.**
13. Auto-migration on first restart with new code? **DECIDED: yes (async_migrate_entry on version bump).**
14. What's the rollback plan if Phase 1 migration breaks production? **DECIDED: (b) — use the Hyper-V backup HA at 192.168.0.237:8237 as a test instance. Migrate against a copied .storage there FIRST, verify all three entries load, then deploy to production. NOTE: test instance is currently powered off and likely behind on updates; bringing it to a usable state is its own Phase 0.5 prep task (see Migration plan).**
15. Search engine: stick with DDG, add Google CSE later as opt-in? (proposed: yes — not a Phase 1 blocker)

---

## Estimated cost / value

**Cost:** 7-12 hours across 4-5 sessions. Real risk of bugs given the scope.
Real risk of incomplete delivery (Phase 5 never happens, integration is in a
half-state).

**Value:** Solves the structural problem (URL-centric model fighting reality),
eliminates Amazon as a special case (it just becomes "this listing failed,
remove it or leave it broken"), makes the alternatives feature pay back
properly (it IS the add-flow now), and turns Price Watch from "URL monitor"
into "shopping assistant."

**Honest assessment:** This is the right architecture. It's also a lot of work
for a tool with one user (you). If you find yourself wishing it worked this way
multiple times in the next week, do it. If tonight's Amazon frustration was the
only time it really mattered, don't.

---

## Decision pending

Wait at least 24 hours before committing to start Phase 1. Re-read this doc
fresh. Argue with the proposed answers. Pick which questions block starting
(probably Q2 migration, Q3 naming, Q8 panel) and resolve those FIRST. Then
start Phase 1 in a fresh session with rested judgment.

If after 24h this still feels right: commit, start Phase 1 with a fresh session
of energy, and use this doc as the spec.

If after 24h the urgency has faded: the integration in its current state is
fine. The Amazon-CAPTCHA issue is solvable with "switch Corsair to MicroCenter,"
which takes 30 seconds.
