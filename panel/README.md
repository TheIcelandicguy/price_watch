# Price Watch panel

Lit + TypeScript source for the sidebar panel.

## Build

From this directory:

```bash
npm install
npm run build
```

The build emits `../custom_components/price_watch/frontend/price-watch-panel.js`,
which is the file the integration serves via the registered static path. After
building, restart Home Assistant to pick up the new bundle.

For iterative development:

```bash
npm run watch
```

Rebuilds on every save. You'll still need to hard-refresh the panel in
the browser (the bundle URL is unversioned right now — we can add a
cache buster later).

## Layout

- `src/panel.ts` — root `<price-watch-panel>` custom element. HA
  passes `hass`, `narrow`, and `panel` properties. Element fetches the
  entity registry once via `hass.callWS({type: 'config/entity_registry/list'})`,
  then derives `TrackedProduct[]` from `hass.states` on every push.
- `src/card.ts` — `<price-watch-card>`, one per tracked product.
  Stateless: re-renders from its `product` property.
- `src/utils.ts` — `buildProducts()`, price/date formatters,
  `sparklinePath()` SVG generator.
- `src/types.ts` — shared types (`HomeAssistant` subset, `TrackedProduct`).

## What ships

A single minified ES module at
`custom_components/price_watch/frontend/price-watch-panel.js`. The
integration registers this at `/price_watch_static/price-watch-panel.js`
via `hass.http.register_static_path()` (see `panel.py`) and references
it from the sidebar entry via `panel_custom`.

Lit is bundled. No external dependencies at runtime.

## When to rebuild

Whenever you change anything in `src/`. The integration's Python code
doesn't bundle — only this frontend.
