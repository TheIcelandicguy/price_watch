---
name: price-watch-dev
description: "Reference for developing Davíð's Price Watch Home Assistant integration (repo TheIcelandicguy/price_watch; source E:\\price_watch, deployed to Z:\\custom_components\\price_watch) — a free-by-default multi-retailer price tracker with a Lit sidebar panel, AI only as a fallback (v0.2.2). Use whenever working on Price Watch: its mixin-split coordinator, extraction modes, listings, FX, discovery/alternatives, services/events/sensors, the panel — and whenever deploying it (.\\deploy.ps1), running its tests (.\\test.ps1; plain pytest cannot run on Windows), cutting a release (HACS needs the price_watch.zip asset or the install fails), or recommending Icelandic retailers (Komplett does not ship to Iceland). Trigger even if the user just says \"Price Watch\" or asks about shipping for Iceland — don't rely on fuzzy memory for these specifics."
---

# Price Watch Development

Davíð's HACS custom integration that tracks product prices across retailers from inside Home Assistant. Repo: `github.com/TheIcelandicguy/price_watch` (public, MIT). Current version: **0.2.2** (released 2026-09-13). Tags and GitHub releases: **v0.2.2** (latest), v0.2.1, v0.2.0 — each published release carries a `price_watch.zip` asset, which is load-bearing (see Releasing). Minimum HA: **2024.10.0**.

## What it is (as of v0.2.2)

Free-by-default. It reads price/stock from a page's Schema.org `Product` / Open Graph data with **no AI and no key**. AI (Anthropic *or* any OpenAI-compatible endpoint, including local Ollama) is an **optional fallback**, and can be set to fallback-only so discovery stays free. Everything is managed from a **sidebar panel** — no YAML, no dashboard wiring. Products can hold multiple **listings** (the same item at several shops), each with its own price/stock/photo, all converted to a home currency.

- **0.2.1** (2026-08-11) added deleting a product from the panel, the `price_watch.untrack_product` service, and themed in-panel confirm dialogs.
- **0.2.2** (2026-09-13) fixed three things: `add_listing` no longer prunes a by-URL product's implicit primary listing (issue #3 — it silently took that listing's history with it); Iceland is out of the "ships within the Nordics" group and all three Komplett storefronts are blocked for Icelandic users; a bot wall / CAPTCHA / 403 / 429 on one poll keeps the last known price instead of flipping every sensor unavailable. Internally, search-result filters and the JSON-LD price backfill moved out of the coordinator into `search/filters.py` and `search/enrich.py`.

> v0.2.0 was a significant reframe from the original (v0.1.0) "single Claude-powered URL tracker." If reasoning from older context, assume the AI-first framing is stale.

## How to keep this reference honest

Three tiers of confidence:

- **Verified against the repo** (README + CHANGELOG): the extraction modes, the panel build path, and the layout below.
- **Verified against source (2026-06, re-checked 2026-10-07)** — the internal function-level details (the `l_<hex>_<key>` unique-id scheme + `parseUniqueId()`, `_ensure_primary_listing`, `resolve_provider_config`/`AI_CONFIG_KEYS`, the two enrichment paths, etc.) were read against current source and collected with file locations in `references/internals.md`. Still: when one drives a change, open the file first — a later refactor can move things.
- **Verified against source and a live run (2026-09-13)** — the Releasing section, the test runner and test layout, and the event/service surface noted below.

When a detail here drives a code change, open the actual file first. The code wins.

## Repo / local layout

Repo root (= local `E:\price_watch`):

- `custom_components/price_watch/` — the integration (this is what deploys to HA)
- `custom_components/price_watch/frontend/price-watch-panel.js` — built panel bundle
- `custom_components/price_watch/presets/` — the four retailer presets (tolvutek, elko, rafland, amazon)
- `panel/` — panel source (Lit + Rollup)
- `deploy.ps1` — thin wrapper over `E:\tools\deploy-to-ha.ps1` (see below)
- `test.ps1` — runs the suite under WSL (see Tests & CI; plain `pytest` does not work on this machine)
- `check_docs.py` — checks paths, constants, version, test count and services against `CLAUDE.md`; exit 1 on drift. **Run it before ending a session and update `CLAUDE.md`.**
- `CLAUDE.md`, `OVERVIEW.md` — at the repo root since 2026-09-10
- `.claude/skills/price-watch-dev/` — this skill (SKILL.md plus `references/`), kept in the repo so it cannot go stale on claude.ai alone; `build_skill.py` packages it as `dist-skill/price-watch-dev.skill` (or `--out DIR`) for the claude.ai upload, and `check_docs.py` checks it against the source. Update it in the same PR as the change it describes. The rest of `.claude/` is gitignored.
- `scripts/` — dev aids, not shipped: `retailer_probe.py` (does a shop work on the free path, hit a bot wall, or need a preset?) and `convert_brand.py` (re-renders `brand/*.png` from the SVGs). Run both from the repo root. The ~28 one-off per-shop probes (`jysk_probe3.py`, `amazon_*` …) were untracked on 2026-09-18 and are gitignored (`scripts/*` with `!` exceptions): they still exist locally, and a backup is in `F:\For Claude\backups\2026-09-18-repo-cleanup\price_watch\`. Put new one-off probes there, uncommitted.
- `tests/`, `docs/`, `hacs.json`, `README.md`, `CHANGELOG.md`. `info.md` (HACS 1) was removed 2026-09-18; HACS 2 renders the README (`render_readme`).

**Deploy target (HA config):** `Z:\custom_components\price_watch`. `Z:` is a **Samba share** = `\\homeassistant.local\config`; when mDNS blips and the hostname won't resolve, remap to the IP: `net use Z: \\192.168.0.176\config /persistent:yes`. Edit in the source tree, build the panel, then sync the component folder over. Never edit the deployed copy directly.

## Deploy workflow (high-frequency — get this right)

Build the panel first if it changed:

```
cd panel && npm install && npm run build   # outputs custom_components/price_watch/frontend/price-watch-panel.js
```

Then deploy with the repo's wrapper — never a hand-rolled robocopy:

```
.\deploy.ps1            # custom_components\price_watch → Z:\custom_components\price_watch
.\deploy.ps1 -DryRun    # show what would change (robocopy /L), write nothing
```

`deploy.ps1` is a thin wrapper over `E:\tools\deploy-to-ha.ps1`: `robocopy /E /R:2 /W:2` (`/E`, never `/MIR`) with `/XD __pycache__ .git .claude .venv tests` and `/XF *.pyc *.pyo settings.local.json test_*.py`. It refuses to run unless `Z:\configuration.yaml` exists, warns about files on `Z:` newer than their `E:` counterpart (hand edits about to be overwritten), lists files on `Z:` that the repo no longer has (`/E` never deletes — remove a stale module by hand), and verifies the deployed `manifest.json` version equals the source after copying. Robocopy exit codes 0–7 are success (1 = files copied); only ≥8 is a failure. `/R:2 /W:2` matters because robocopy's default is a million retries at 30 s, so a file HA holds open becomes a hang, not an error.

### If a copy fails on a file lock

Restart HA and re-run `.\deploy.ps1`. The old `FileShare::ReadWrite` PowerShell-stream workaround is superseded — don't reach for it. For targeted in-place edits in the source tree, prefer `Desktop Commander:edit_block` over rewriting whole files.

### After deploy: restart, then verify live (do not skip)

**Reloading the config entry does NOT re-import custom-component Python.** After changing *any* `.py`, you must **fully restart Home Assistant** (`ha_restart(confirm=true)`) for it to take effect. Reload-only is enough solely for options/data changes, never for code. A deploy that only changes `manifest.json`'s version needs no restart for behaviour — HA just keeps reporting the old version until one happens.

Since 2026-09-13 the suite does load the integration the way HA does (`tests/test_setup_entry.py` sets up real config entries and imports every module), so the old trap — a forgotten `from .const import X` passing `pytest` clean and then taking every sensor to `unknown` — is caught before a deploy. A mutation test confirmed it: a bad reference in `sensor.async_setup_entry` left the pre-2026-09-13 suite fully green. Still verify on the running instance, because the tests drive a faked page inside a mock HA:

1. Poll `http://<ha>/manifest.json` until it returns 200 (HA back up).
2. Check a product's price sensor and the error log (`ha_get_logs source=error_log search="price_watch"`).

A panel-only change (rebuilt bundle, no `.py`) needs no restart — but the browser must **hard-refresh (Ctrl+Shift+R)** to pick up the new bundle.

> The HA MCP `ha_call_service` has intermittently rejected nested `data` ("expected a JSON object… not a JSON-encoded string") after a server reconnect. Config-entry deletes via `ha_remove_helpers_integrations(target=<entry_id>, confirm=true)` are unaffected; for service calls, reload the tool or use an alternate path.

## Tests & CI

**Run the suite with `.\test.ps1`. Plain `pytest` cannot run on this machine at all** — `tests/conftest.py` loads `pytest_homeassistant_custom_component` → `homeassistant.runner` → `fcntl`, which is POSIX-only, so it dies at collection before a single test runs.

```powershell
.\test.ps1                                          # whole suite, quiet (~15 s)
.\test.ps1 tests\test_fx.py                         # one file
.\test.ps1 -k region -v                             # args pass through to pytest
.\test.ps1 --cov=custom_components.price_watch      # as CI runs it
.\test.ps1 -Reinstall                               # rebuild the test venv
ruff check custom_components/price_watch            # what CI lints (NOT tests/)
```

`test.ps1` runs pytest under WSL (Ubuntu, Python 3.12) against this same working tree via `/mnt/<drive>`, in a venv at `~/.venvs/price_watch` **inside** the WSL filesystem — not in the repo, where it would be slow to import from and one more thing for deploy and git to exclude. First run installs `requirements_test.txt` and touches `.requirements-installed`; that stamp, not `bin/python`, is the readiness check, so an install killed part-way retries instead of leaving a venv with a working python and no pytest. `pytest.ini` supplies `asyncio_mode=auto` and `pythonpath=.`.

**Never run `git` from WSL in this repo without `core.autocrlf=true`.** The Windows checkout is CRLF and WSL git defaults to `false`, so `git status` there reports ~17 unmodified files as wholly changed (~15k insertions / 15k deletions, pure line endings) and a commit from WSL would rewrite every line ending in them. `test.ps1` sets the flag on each run; commit from PowerShell regardless.

`ruff.toml` pins `select = ["E4","E7","E9","F"]` on purpose — Ruff's defaults drifted (0.16 turned on `I`) and reddened CI. Don't "modernise" it casually. A newer Ruff installed locally will report dozens of findings and "68 files would be reformatted" on a tree CI calls clean; that is version drift, not breakage — CI runs no `ruff format` check and lints only `custom_components/price_watch`.

### Test layout (14 files)

Most of the suite is unit-level, driving one mixin on a stand-in object (`test_transient_block.py`, `test_implicit_primary_listing.py`) — `UpdateMixin` and `StorageMixin` only declare their borrowed attributes under `TYPE_CHECKING`, so a small class with the right members is a faithful caller and needs no HA fixture. Three files work at the HA level instead:

- `test_setup_entry.py` — loads the settings entry (the zero-product install) and a by-URL product, asserts entities on all four platforms (`sensor`, `binary_sensor`, `button`, `image`) and a clean unload, walks a price from page to sensor state, and imports every module in the package.
- `test_coordinator_refresh.py` — whole polls through the real coordinator: history rows, extremes, each transition event with its payload, target-hit firing on the crossing only, and the `UNCHANGED` short-circuit. Its `_Page` fake reproduces `extract_product`'s protocol, **including raising `ExtractionError("UNCHANGED")` when the caller's `previous_hash` matches** — without that the short-circuit is invisible from this patch seam and the test passes for the wrong reason.
- `test_services_events_contract.py` — pins `services.yaml` against the registered services (both directions), the documented fields against the schemas, and the `EVENT_*` values against literals. **Adding a service or renaming an event fails this file on purpose**: those are identifiers other people's automations are built on. Update the test and `services.yaml` together.

Writing a new HA-level test here, two seams always need patching: `coordinator.async_get_clientsession` and `coordinator_update.async_get_clientsession` (the coordinator builds a real session in `__init__` for FX, and HA's shared session resolves through aiodns, whose pycares resolver leaves a thread the harness reports as a leak at teardown), plus `hass.http` stubbed with an `AsyncMock` `async_register_static_paths` so `async_register_panel` works. Do **not** set up the real `frontend` component — it imports the `hass_frontend` wheel, which is not a test dependency. A by-URL product fixture should carry **no** `listings` option: the implicit primary is materialized on load with an id derived from the URL, so a hand-picked id becomes a *second* listing.

CI (`.github/workflows/validate.yml`): hassfest, HACS validation, pytest on 3.12 and 3.13, ruff — on push to main, PRs, manual, weekly Sunday.

## Releasing (HACS users are on releases, not on main)

A fix merged to `main` reaches nobody: HACS installs from published releases. Issue #3's fix sat on main for a day with the issue still open because no tag carried it, and the reporter had to ask for a release.

`hacs.json` sets `zip_release` with `filename: price_watch.zip`, and `.github/workflows/release-asset.yml` attaches that asset on every publish. **This is load-bearing**: unlike a Lovelace plugin, whose missing asset makes HACS fall back to the repo tree, an *integration* release with no asset **fails to install**. The workflow checks out the tag (not main), verifies `hacs.json` and the component directory agree on the name, verifies the tag matches `manifest.json`'s version, and verifies `manifest.json` sits at the zip root (HACS extracts straight into `custom_components/<domain>/`, so a nested folder would install an empty component). Backfill a release published before the workflow existed with its `workflow_dispatch` (input: the tag).

To cut one:

1. Bump `version` in `custom_components/price_watch/manifest.json`.
2. Rename the CHANGELOG's `## [Unreleased]` heading to `## [x.y.z] - <date>`.
3. Update the version quoted in `CLAUDE.md` (`check_docs.py` enforces that one) and `OVERVIEW.md`'s `**Version:**` line. Leave historical mentions of older versions alone.
4. `python check_docs.py`, then `.\test.ps1`.
5. Commit, `git tag -a vx.y.z`, push main and the tag. **Wait for Validate to pass on the release commit** before publishing.
6. `gh release create vx.y.z --title "vx.y.z - public beta" --notes-file <file>`.
7. **Verify the asset attached**: `gh release view vx.y.z --json assets`. A release without `price_watch.zip` cannot be installed.
8. Close the issues it fixes, telling the reporter to redownload in HACS and restart. If the bug lost data, say plainly what does and does not come back.

## Known gaps

- None currently recorded. `edit_listing`'s `url`, `unit_quantity` and `unit_label` (switch the tracked page to a sibling size's URL; a manual price-per-unit figure for e.g. Bauhaus lumber) used to be accepted by the schema but missing from `services.yaml`; commit `ca7cb43` (13 Sep 2026) documented them and `test_services_events_contract.py` now fails if a service accepts an undocumented field. (The "Doc drift" bullet in `CLAUDE.md` still lists them as missing; `services.yaml` is correct.)

## Retailer constraints (Iceland) — hard rule

**Komplett does NOT ship to Iceland. Never recommend it.** It ranks well for Nordic price searches, which is the trap. Since 0.2.2 all three storefronts (`.no` / `.se` / `.dk`) are blocked for Icelandic users in `search/region_heuristic.py`'s `_REGION_BLOCKED_RETAILERS["IS"]`, and `_NORDIC_MAINLAND` (`NO SE DK FI`) deliberately excludes `IS`, so a mainland-Nordic TLD can no longer upgrade an Icelandic user's result. Add further verified retailer→region blocks to `_REGION_BLOCKED_RETAILERS`, not to the country groups. The integration flags and can hide listings that won't ship to the user's country (ISK → Iceland).

Recommend Icelandic retailers instead. **Verified working (free extraction):** `elko.is` ⚙️, `tolvutek.is` ⚙️, `rafland.is` ⚙️, `ormsson.is`, `husa.is` (Húsasmiðjan), `byko.is`, `jysk.is`, `bauhaus.is`, `coolshop.is`. (⚙️ = handled by a built-in preset — see `references/presets.md`.) The **living source of truth** for what works/doesn't is pinned GitHub **issue #1 "🏪 Retailer compatibility"** — check it before hardcoding a list. Don't recommend shops you haven't confirmed are still operating (e.g. the older "Tölvulistinn/Computer.is" names are unverified and possibly defunct).

## Where to look next

- **`references/services-events-entities.md`** — verified service calls, event types + payloads, and the per-product entities. Start here for anything touching the public API surface. Note there are **six** events, not four: `price_watch_price_drop`, `_target_hit`, `_new_low`, `_back_in_stock`, `_discount`, `_discontinued`, sharing a payload (`entry_id`, `title`, `url`, `retailer`, `price`, `currency`, `previous_price`, `target`, `image_url`, `in_stock`) plus `listing_id` on per-listing events (`_discontinued` and `_discount` add their own fields). There are **11** services; `services.yaml` is the list.
- **`references/architecture.md`** — extraction modes, the mixin-split coordinator, fetching/anti-bot behavior, FX, discovery, cookies, history model.
- **`references/presets.md`** — the per-retailer preset system (`presets/`): how to add a site so it "just works" out of the box (the elko/tolvutek/rafland pattern).
- **`references/config-and-panel.md`** — panel features (selector editor, cookie capture, variant picker, alert builder, AI settings, delete product with themed confirm dialogs) and the build.
- **`references/internals.md`** — verified function-level details with file locations: the unique-id/`parseUniqueId` scheme, `_ensure_primary_listing`, provider precedence (`AI_CONFIG_KEYS`), the two enrichment paths.
- **`references/public-product.md`** — the separate future public/SaaS concept.