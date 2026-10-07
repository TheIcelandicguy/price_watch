# Panel and configuration (verified against repo)

Everything is driven from the **sidebar panel** — no YAML, no dashboard wiring. Read this for panel features and the build.

## Panel features (v0.2.1)

- Add, search, sort, filter, compare, and manage all products from one screen.
- **Custom price-selector editor** with a **"Test on live page"** button and an **element-picker bookmarklet**.
- **Cookie capture** for cookie-walled sites.
- **Variant / size picker** (e.g. lumber length, sizes) on supported pages.
- **Alert-builder dialog** (🔔) that writes the event automations for you.
- **AI-provider settings editor** (choose Anthropic or an OpenAI-compatible endpoint; set fallback-only).
- **Per-store stock** display (e.g. Húsasmiðjan, JYSK).
- **Delete a product from the panel**, with **themed in-panel confirm dialogs** replacing browser `confirm()` (0.2.1; the `price_watch.untrack_product` service landed with it).

## Initial setup

1. HACS → custom repository `https://github.com/TheIcelandicguy/price_watch`, category Integration → install → restart HA.
2. Settings → Devices & Services → Add Integration → Price Watch → choose a mode (Free is fine) → finish.
3. A **Price Watch** item appears in the sidebar.
4. Add product → paste URL (or Search & add) → confirm preview → set a target price.

## Panel build

Source in `panel/` (Lit + Rollup):

```
cd panel && npm install && npm run build
# outputs custom_components/price_watch/frontend/price-watch-panel.js
```

Rebuild the panel whenever panel source changed, then run `.\deploy.ps1` from the repo root (wrapper over `E:\tools\deploy-to-ha.ps1`) to sync the component to `Z:`. A panel-only change needs no HA restart, only a hard refresh.
