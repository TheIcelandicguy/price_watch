"""Sidebar panel registration for Price Watch.

Registers a `panel_custom` entry pointing at our bundled Lit element.
The bundle lives at `custom_components/price_watch/frontend/price-watch-panel.js`
and is served via a registered static path at `/price_watch_static/...`.

Single-shot setup: the panel is registered once on first product-entry
load and stays registered across entry adds/removes. We unregister it
only when the integration is fully uninstalled, which HA handles via
the standard async_unload_entry path (no-op for us — leaving the panel
registered until reboot is fine).

Why this approach over Lovelace dashboards:
- panel_custom is a stable, well-documented HA API (HACS, Music
  Assistant, Frigate all use it)
- Bundle + static path means our panel is fully self-contained — no
  user YAML, no .storage entries to manage, no Lovelace machinery
- Updates ship with the integration; no separate npm package to
  install
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Where the bundled Lit code lives on disk. The panel/ directory at
# the project root builds into this location — see panel/README.md.
_FRONTEND_DIR = Path(__file__).parent / "frontend"
_PANEL_BUNDLE_FILENAME = "price-watch-panel.js"

# What we mount the static directory as. Picking an obscure prefix
# (price_watch_static) avoids collisions with anything else that might
# register under /local or /static.
_STATIC_URL_BASE = f"/{DOMAIN}_static"
_PANEL_JS_URL = f"{_STATIC_URL_BASE}/{_PANEL_BUNDLE_FILENAME}"

# Sidebar entry config.
_PANEL_URL_PATH = "price-watch"
_PANEL_SIDEBAR_TITLE = "Price Watch"
_PANEL_SIDEBAR_ICON = "mdi:tag-search"

# Custom-element tag name that panel.ts defines. Must match the
# @customElement decorator in src/panel.ts.
_PANEL_ELEMENT_NAME = "price-watch-panel"

# Marker key in hass.data[DOMAIN] so we don't try to register twice
# (HA raises ValueError on duplicate panel registration).
_PANEL_READY_KEY = "_panel_ready"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the static path and sidebar panel.

    Idempotent — second and later calls return early. Safe to call
    from async_setup_entry on every product-entry load.

    The bundle file must exist before this is called. If it's missing
    (user didn't run `npm run build` yet) we log a warning and don't
    register the panel at all — the rest of the integration still
    works, just no sidebar entry.
    """
    if hass.data.setdefault(DOMAIN, {}).get(_PANEL_READY_KEY):
        return

    bundle_path = _FRONTEND_DIR / _PANEL_BUNDLE_FILENAME
    if not bundle_path.is_file():
        _LOGGER.warning(
            "Price Watch panel bundle not found at %s. "
            "Build it with: cd panel && npm install && npm run build. "
            "Skipping sidebar registration; the rest of the integration "
            "will work normally.",
            bundle_path,
        )
        return

    # Append the bundle's mtime as a cache buster query param. This
    # solves the "hard-refresh after every rebuild" problem — when the
    # file changes, the URL changes, and the browser fetches a fresh
    # copy. The URL is stable as long as the file is unchanged.
    #
    # We compute this here (synchronously, in the executor that runs
    # async_setup_entry) rather than per-request to keep the static
    # path handler unchanged. As a consequence, changing the bundle
    # without restarting HA means the cache-buster still points at the
    # old mtime — but `npm run watch` rebuilds during development are
    # the only scenario where that matters, and a dev would expect to
    # hard-refresh in that loop anyway.
    bundle_mtime = int(bundle_path.stat().st_mtime)
    panel_js_url = f"{_PANEL_JS_URL}?v={bundle_mtime}"

    # Step 1: serve the frontend directory at /price_watch_static/.
    # cache_headers=False so the browser refetches after every rebuild.
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=_STATIC_URL_BASE,
                path=str(_FRONTEND_DIR),
                cache_headers=False,
            )
        ]
    )

    # Step 2: register the sidebar entry.
    #
    # We use module_url (NOT js_url) because Rollup emits our bundle
    # in ES module format (`output.format: "es"`). HA's panel_custom
    # loader treats js_url as a classic <script src=...> tag — any
    # bundle with `export`/`import` statements silently fails to parse
    # in that context, which is what bit us originally: the element
    # was never registered and `document.querySelector('price-watch-panel')`
    # returned null even though the file was being fetched correctly.
    #
    # module_url loads the bundle as <script type="module">, which is
    # what an ES-format bundle needs. The HA docs say module_url is
    # served only to the "latest" build of the frontend; the ES5
    # build would need js_url with a classic-format bundle. Modern
    # HA defaults to "latest" so this is fine.
    #
    # embed_iframe=False: render the element directly in the main
    # document, no iframe sandbox. The element bootstraps its own
    # WebSocket connection via window.hassConnection rather than
    # relying on HA's `hass` property injection — see panel.ts.
    try:
        frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title=_PANEL_SIDEBAR_TITLE,
            sidebar_icon=_PANEL_SIDEBAR_ICON,
            frontend_url_path=_PANEL_URL_PATH,
            config={
                "_panel_custom": {
                    "name": _PANEL_ELEMENT_NAME,
                    "embed_iframe": False,
                    "trust_external": False,
                    "module_url": panel_js_url,
                }
            },
            require_admin=False,
        )
    except ValueError:
        # ValueError("Overwriting panel ...") means it's already
        # registered. Treat as success (idempotent semantics).
        _LOGGER.debug("Price Watch panel already registered; reusing")

    hass.data[DOMAIN][_PANEL_READY_KEY] = True
    _LOGGER.info(
        "Registered Price Watch sidebar panel at /%s (bundle: %s)",
        _PANEL_URL_PATH, panel_js_url,
    )


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel.

    Called when the integration is fully uninstalled. Safe even when
    the panel was never registered (e.g. bundle was missing).
    """
    if not hass.data.setdefault(DOMAIN, {}).get(_PANEL_READY_KEY):
        return
    try:
        frontend.async_remove_panel(hass, _PANEL_URL_PATH)
    except Exception:  # noqa: BLE001
        # async_remove_panel raises when the panel doesn't exist.
        # Either way, we want it gone — log at debug and move on.
        _LOGGER.debug(
            "Panel %r was not registered when we tried to remove it",
            _PANEL_URL_PATH,
        )
    hass.data[DOMAIN][_PANEL_READY_KEY] = False
