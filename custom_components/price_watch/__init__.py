"""The Price Watch integration."""

from __future__ import annotations

import logging
import secrets
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .config_flow import ENTRY_TYPE_PRODUCT, ENTRY_TYPE_SETTINGS
from .migration import migrate_entry_v1_to_v2
from .const import (
    CONF_FORCE_DISCONTINUED,
    CONF_PAUSED,
    CONF_TARGET_PRICE,
    DOMAIN,
    STORAGE_VERSION,
)
from .coordinator import PriceWatchCoordinator
from .extractor import shutdown_persistent_session
from .panel import async_register_panel
from .websocket import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.IMAGE]


def _cookies_to_header_str(value: Any) -> str:
    """Normalize a cookies value to a single Cookie-header string.

    Accepts the shapes callers actually send:
      - a header string ("a=1; b=2") — returned trimmed,
      - a {name: value} dict,
      - a list of cookie dicts ({"name": .., "value": ..}) as documented in
        services.yaml and as produced by browser cookie APIs.
    Returns "" for empty / unrecognized input (which clears the cookies).

    Cookies are stored as a header string inside custom_parser.request_cookies
    because that's the ONLY place the extractor reads them (see
    extractor.extract_product) and the shape the config flow already
    persists / _normalize_cookies parses back.
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items() if v is not None)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                val = item.get("value")
                if name is not None and val is not None:
                    parts.append(f"{name}={val}")
        return "; ".join(parts)
    return ""

# Option keys the running coordinator reads LIVE on every tick (see the
# "Pause / force-discontinued overrides" note in coordinator.py). When ONLY
# these change, the coordinator already applies them itself, so the update
# listener skips the full entry reload. That reload was bouncing the entry
# and wiping the coordinator's in-memory data — which made a *paused* product
# go "unavailable" instead of holding its last-known price (contradicting the
# set_paused service's documented behavior). Skipping it keeps the last price
# visible and avoids a needless re-fetch on a target-price/discontinued edit.
_LIVE_OPTION_KEYS = frozenset(
    {CONF_PAUSED, CONF_FORCE_DISCONTINUED, CONF_TARGET_PRICE}
)


def _reload_signature(entry: ConfigEntry) -> dict[str, Any]:
    """Options subset whose change requires a structural entry reload.

    Excludes the live-read flags above. Two option sets with the same
    signature differ only in live flags, so the listener can apply them
    in place instead of reloading.
    """
    return {
        k: v for k, v in entry.options.items() if k not in _LIVE_OPTION_KEYS
    }


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a v1 config entry to v2 shape.

    Called by HA automatically when entry.version < ConfigFlow.VERSION.
    Returns True on success, False to mark the entry as failed-migration.

    v1: data has url + AI snapshot, options has flat custom_parser/cookies/
        target_price/scan_interval/etc.
    v2: data is minimal metadata + v2_schema marker; options has nested
        {product: {...}, listings: [{id, url, retailer, ...}]}.

    The settings entry has no URL and no listings, so it's a no-op for it:
    we let HA bump its version (returning True) without mutating its shape.
    """
    _LOGGER.info("Migrating entry %s from version %s", entry.entry_id, entry.version)

    # Settings entries don't have listings — skip the transformation entirely.
    # Returning True here lets HA bump its version marker without rewriting
    # data/options. WITHOUT this skip, migrate_entry_v1_to_v2 would produce
    # a corrupted v2 entry with an empty-URL listing (caught in pre-flight
    # audit, see search-first-refactor.md).
    if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
        _LOGGER.info("Settings entry %s — version bump only, no shape change",
                     entry.entry_id)
        # HA doesn't auto-bump version on async_migrate_entry returning
        # True; we must explicitly update it. Without this, every restart
        # would re-trigger migration on the settings entry (harmless but
        # noisy, and confusing for a hypothetical future v2→v3 migration
        # that would mistake it for a v1 entry needing two-step migration).
        hass.config_entries.async_update_entry(entry, version=2)
        return True

    # Product entry: full migration.
    # Listing id is derived deterministically from the entry_id so the
    # storage migration callback (running independently inside the
    # coordinator's Store load) produces the same id and the data lines up.
    # 12 chars from the ULID's random suffix gives plenty of entropy.
    listing_id = f"l_{entry.entry_id[-12:].lower()}"

    try:
        new_data, new_options = migrate_entry_v1_to_v2(
            entry.data,
            entry.options,
            listing_id=listing_id,
            entry_title=entry.title or "",
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception(
            "Migration of entry %s failed: %s", entry.entry_id, err
        )
        return False

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options=new_options,
        version=2,
    )
    _LOGGER.info(
        "Migrated %s -> v2 (listing %s, product short_name=%r)",
        entry.entry_id, listing_id,
        new_options.get("product", {}).get("short_name"),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Price Watch from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Settings entry has nothing to set up - just stores API key
    if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
        hass.data[DOMAIN]["settings"] = entry.entry_id
        return True

    # Product entry
    coordinator = PriceWatchCoordinator(hass, entry)
    # Snapshot the reload-significant options so the update listener can tell
    # a structural change (needs reload) from a live-flag toggle (apply in
    # place — see _async_update_listener / _LIVE_OPTION_KEYS).
    coordinator.reload_signature = _reload_signature(entry)

    # If this entry was previously marked discontinued, restore that
    # state from the persistent store and skip the initial refresh.
    # This prevents:
    #   - racking up API cost on a product that won't come back
    #   - the entry going into setup_retry on every restart because
    #     the discontinued-product page returns NO_PRODUCT_FOUND
    if await coordinator.async_restore_if_discontinued():
        _LOGGER.info(
            "%s: skipping initial refresh, product is discontinued",
            entry.entry_id,
        )
    elif coordinator.paused:
        # User paused this product. Skip the initial fetch and leave the
        # coordinator in its empty data state — sensors will be
        # "unavailable" until the user unpauses. The pre-pause state in
        # the HA Store still survives, but coordinator.data only
        # rehydrates from a successful refresh, so this is a deliberate
        # tradeoff: pausing during quiet times costs you the in-memory
        # state, but you can resume any time and pick up where you left
        # off (history is preserved on disk).
        _LOGGER.info(
            "%s: skipping initial refresh, product is paused",
            entry.entry_id,
        )
        # Stop the polling loop so the coordinator doesn't tick.
        coordinator.update_interval = None
    else:
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception as err:  # noqa: BLE001
            raise ConfigEntryNotReady(f"Initial fetch failed: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services on first product entry
    if not hass.services.has_service(DOMAIN, "refresh_now"):
        await _register_services(hass)

    # Register the panel's WebSocket commands (live product search).
    # Idempotent — HA's command registry replaces a same-typed handler,
    # so calling this on every product entry is harmless.
    async_register_websocket_api(hass)

    # Register the sidebar panel. Idempotent — second and later calls
    # return early. Doing this here (rather than in async_setup) means
    # the panel only appears once a product entry exists. If the bundle
    # JS hasn't been built yet, the function logs a warning and returns
    # without registering — the rest of the integration still works.
    await async_register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
        hass.data.get(DOMAIN, {}).pop("settings", None)
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # If no products are left, close the persistent fetch session.
        # Settings entry doesn't count - it doesn't fetch anything.
        product_coords = [
            c for c in hass.data.get(DOMAIN, {}).values()
            if isinstance(c, PriceWatchCoordinator)
        ]
        if not product_coords:
            await shutdown_persistent_session()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up persistent storage when a config entry is removed.

    Called by HA after the entry is unloaded and being deleted. Without
    this hook, the per-entry storage file at
    .storage/price_watch.{entry_id} would be orphaned on disk forever —
    harmless (HA ignores storage files without a matching entry) but
    noise that accumulates over years of add/remove cycles.

    Settings entries have no per-entry store, so they're a no-op.
    Storage key shape matches what the coordinator constructs in its
    PriceWatchStore (f"{DOMAIN}.{entry.entry_id}", from store.py), so
    async_remove targets the right file. A plain Store is used here
    instead of PriceWatchStore — we don't need migration logic to
    delete a file.
    """
    if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
        return
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    await store.async_remove()
    _LOGGER.info(
        "Removed persistent storage for entry %s", entry.entry_id,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change.

    EXCEPT when only the live-read flags changed (pause / force-discontinued
    / target price). The running coordinator already reads those fresh on
    every tick and the set_* methods update its in-memory state, so a reload
    is not only unnecessary but harmful: it rebuilds the coordinator with
    empty data, which made a paused product drop to "unavailable" instead of
    holding its last-known price. In that case we just push the new state to
    the entities and leave the coordinator (and its last price) intact.
    """
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if isinstance(coordinator, PriceWatchCoordinator):
        new_sig = _reload_signature(entry)
        if new_sig == getattr(coordinator, "reload_signature", None):
            # Only live flags toggled — apply in place, no reload.
            coordinator.reload_signature = new_sig
            coordinator.async_update_listeners()
            return
        coordinator.reload_signature = new_sig
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_services(hass: HomeAssistant) -> None:
    """Register integration-wide services."""

    def _coordinators_for(call: ServiceCall) -> list[PriceWatchCoordinator]:
        """Resolve target coordinators from a service call.

        Resolves by entry_id, device_id, or — if neither given — all products.
        """
        entry_ids: set[str] = set()
        if entry_id := call.data.get("entry_id"):
            entry_ids.add(entry_id)
        if device_ids := call.data.get("device_id"):
            registry = dr.async_get(hass)
            for did in (device_ids if isinstance(device_ids, list) else [device_ids]):
                device = registry.async_get(did)
                if device:
                    for cid in device.config_entries:
                        entry_ids.add(cid)

        results: list[PriceWatchCoordinator] = []
        for eid, coord in hass.data.get(DOMAIN, {}).items():
            if not isinstance(coord, PriceWatchCoordinator):
                continue
            if not entry_ids or eid in entry_ids:
                results.append(coord)
        return results

    async def refresh_now(call: ServiceCall) -> None:
        """Force immediate refresh of one or all products."""
        for coord in _coordinators_for(call):
            await coord.async_request_refresh()

    async def set_target(call: ServiceCall) -> None:
        """Update target price for one product."""
        target_raw = call.data.get(CONF_TARGET_PRICE)
        target = float(target_raw) if target_raw is not None else None
        for coord in _coordinators_for(call):
            await coord.async_set_target(target)

    async def reset_history(call: ServiceCall) -> None:
        """Wipe price history."""
        for coord in _coordinators_for(call):
            await coord.async_reset_history()

    async def set_paused(call: ServiceCall) -> None:
        """Pause or resume polling for one or all products.

        Thin wrapper over the coordinator's async_set_paused, which
        persists the flag on entry.options and stops/restarts the
        polling interval immediately. Lets the panel offer a per-card
        pause toggle without opening the options dialog.
        """
        paused = bool(call.data.get("paused", True))
        for coord in _coordinators_for(call):
            await coord.async_set_paused(paused)

    async def find_alternatives(call: ServiceCall) -> None:
        """Run an alternatives search for one or all products.

        Reads optional `max_results` from the call data (1-20, default
        is the product's configured max). Sequential per-product
        (not parallel) so we don't overwhelm a single Anthropic key
        or local Ollama with simultaneous requests.
        """
        max_raw = call.data.get("max_results")
        max_results: int | None = None
        if max_raw is not None:
            try:
                max_results = max(1, min(20, int(max_raw)))
            except (TypeError, ValueError):
                max_results = None
        for coord in _coordinators_for(call):
            try:
                await coord.async_find_alternatives(max_results=max_results)
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "find_alternatives failed for %s", coord.entry.entry_id
                )

    def _resolve_entry(call: ServiceCall):
        """Resolve a service call's entry_id to a (config_entry, coordinator)
        tuple, raising HomeAssistantError on misuse.

        add_listing / remove_listing both target ONE entry, unlike the
        broadcast services above. We don't iterate; we want a single
        explicit entry_id to act on.
        """
        entry_id = call.data.get("entry_id")
        if not entry_id:
            raise HomeAssistantError(
                "entry_id is required for add_listing / remove_listing"
            )
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError(f"No price_watch entry with id {entry_id!r}")
        if entry.data.get("entry_type") != ENTRY_TYPE_PRODUCT:
            raise HomeAssistantError(
                f"Entry {entry_id!r} is not a product entry (cannot have listings)"
            )
        return entry

    def _new_listing_id() -> str:
        """Generate a stable unique listing_id for newly-added listings.

        Format: `l_<12 hex chars>` — same length and prefix as migration-
        generated primary IDs (`l_<last 12 of entry_id>`) but with
        random entropy so collisions across listings of the same product
        are vanishingly unlikely. The leading `l_` makes them visually
        identifiable as listing IDs.
        """
        return f"l_{secrets.token_hex(6)}"

    async def add_listing(call: ServiceCall) -> None:
        """Add a new listing to an existing product entry.

        Args:
            entry_id: the product entry to add the listing to
            url: the listing's URL (required)
            retailer: display name of the retailer (optional, defaults to
                the URL's host)
            currency: ISO currency code for the listing (optional;
                extractor will populate it from JSON-LD if absent)
            custom_parser: JSON string with the parser config (optional;
                JSON-LD fallback handles most retailers without one)
            request_cookies: cookies for anti-bot bypass (optional). Accepts
                a Cookie-header string, a {name: value} dict, or a list of
                {name, value, ...} dicts. Stored inside custom_parser, the
                only place the extractor reads cookies.

        After modifying entry.options, reloads the entry so the
        coordinator picks up the new listing and sensor.py creates
        the per-listing entities.
        """
        entry = _resolve_entry(call)
        url = (call.data.get("url") or "").strip()
        if not url:
            raise HomeAssistantError("url is required")

        listing_id = _new_listing_id()
        retailer = call.data.get("retailer")
        if not retailer:
            # Derive a reasonable default from URL host
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower().lstrip("www.")
            retailer = host.split(".")[0].title() if host else "Unknown"

        # Optional fields
        currency = call.data.get("currency") or ""
        custom_parser_raw = call.data.get("custom_parser")
        custom_parser = None
        if custom_parser_raw:
            try:
                import json as _json
                custom_parser = (
                    _json.loads(custom_parser_raw)
                    if isinstance(custom_parser_raw, str)
                    else custom_parser_raw
                )
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(
                    f"custom_parser is not valid JSON: {err}"
                ) from err

        # Cookies live inside custom_parser.request_cookies (the only place
        # the extractor reads them). Build a cookies-only parser if none was
        # supplied — the cookie path runs regardless of parser type, and
        # extraction falls through to JSON-LD / AI, which is the whole point.
        cookie_str = _cookies_to_header_str(call.data.get("request_cookies"))
        if cookie_str:
            if not isinstance(custom_parser, dict):
                custom_parser = {}
            custom_parser["request_cookies"] = cookie_str

        new_listing = {
            "id": listing_id,
            "url": url,
            "retailer": retailer,
            "currency": currency,
            "custom_parser": custom_parser,
            "min_price": None,
            "max_price": None,
            "paused": False,
        }

        # Mutate entry.options.listings — async_update_entry handles
        # the immutable-options copy-and-replace correctly.
        existing = list(entry.options.get("listings") or [])
        # Defensive: refuse to add a duplicate URL (avoids silent
        # double-polling of the same retailer)
        for existing_listing in existing:
            if isinstance(existing_listing, dict) and existing_listing.get("url") == url:
                raise HomeAssistantError(
                    f"Listing with URL {url!r} already exists "
                    f"(id={existing_listing.get('id')!r})"
                )
        existing.append(new_listing)
        new_options = dict(entry.options)
        new_options["listings"] = existing
        hass.config_entries.async_update_entry(entry, options=new_options)

        _LOGGER.info(
            "add_listing: added %s (%s) to entry %s; reloading",
            listing_id, retailer, entry.entry_id,
        )
        # Reload picks up the new listing — coordinator re-instantiates,
        # _load_v2_storage reads any existing per-listing state (none
        # for a newly-added listing), sensor.async_setup_entry iterates
        # listing_ids and creates per-listing entities.
        await hass.config_entries.async_reload(entry.entry_id)

    async def remove_listing(call: ServiceCall) -> None:
        """Remove a listing from an existing product entry.

        Args:
            entry_id: the product entry
            listing_id: the listing to remove

        Refuses to remove the PRIMARY listing — primary identity is tied
        to the entry creation (sensor unique_ids, panel entity grouping
        all key off the primary). If the user wants a different primary,
        they should delete the entire entry and re-create.

        Cleans up:
            - entry.options.listings (removes the dict)
            - storage.data.listings[listing_id] (removes runtime state
              via the coordinator's next save)
            - the per-listing sensor entities (reload removes them)
        """
        entry = _resolve_entry(call)
        listing_id = (call.data.get("listing_id") or "").strip()
        if not listing_id:
            raise HomeAssistantError("listing_id is required")

        coord = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if coord is not None and listing_id == coord.primary_listing_id:
            raise HomeAssistantError(
                f"Cannot remove primary listing {listing_id!r}. "
                "Delete the entire entry instead."
            )

        existing = list(entry.options.get("listings") or [])
        new_listings = [
            l for l in existing
            if not (isinstance(l, dict) and l.get("id") == listing_id)
        ]
        if len(new_listings) == len(existing):
            raise HomeAssistantError(
                f"Listing {listing_id!r} not found on entry {entry.entry_id}"
            )

        new_options = dict(entry.options)
        new_options["listings"] = new_listings
        hass.config_entries.async_update_entry(entry, options=new_options)

        # Drop the listing from storage too. The coordinator's
        # _build_v2_storage only emits listings present in self._listings;
        # after the reload, the new coordinator instance loads from disk
        # and won't see this listing. But we should proactively clear
        # the stale entry from disk so a reload-failure doesn't leave it.
        # Simplest: clear from coord.in-memory state if coord exists.
        if coord is not None:
            coord._listings.pop(listing_id, None)
            coord._listing_results.pop(listing_id, None)
            try:
                await coord._async_save()
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "remove_listing: failed to save after dropping %s",
                    listing_id,
                )

        # Remove the listing's entities from the registry. Reloading the
        # entry stops the platforms from RE-creating these sensors, but HA
        # does NOT auto-delete the now-unproduced entities — they linger as
        # orphaned "unavailable" registry entries. The panel builds its
        # listing rows from the entity registry, so an orphaned price
        # sensor renders as a ghost "Unknown / never / —" row that can't
        # be dismissed. Delete them explicitly here.
        #
        # Secondary-listing sensors use unique_id `{entry_id}_{listing_id}_{key}`
        # (see sensor._BasePriceWatchSensor / binary_sensor). The primary
        # listing uses the legacy `{entry_id}_{key}` form with no listing_id
        # segment, so this prefix never matches primary entities.
        ent_reg = er.async_get(hass)
        prefix = f"{entry.entry_id}_{listing_id}_"
        removed_entities = [
            ent.entity_id
            for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            if ent.unique_id and ent.unique_id.startswith(prefix)
        ]
        for entity_id in removed_entities:
            ent_reg.async_remove(entity_id)
        if removed_entities:
            _LOGGER.debug(
                "remove_listing: removed %d orphaned entities for %s: %s",
                len(removed_entities), listing_id, removed_entities,
            )

        _LOGGER.info(
            "remove_listing: removed %s from entry %s; reloading",
            listing_id, entry.entry_id,
        )
        await hass.config_entries.async_reload(entry.entry_id)

    async def edit_listing(call: ServiceCall) -> None:
        """Update an existing listing's parser / metadata in place.

        Args:
            entry_id: the product entry
            listing_id: the listing to edit
            custom_parser: JSON string (or dict) with the parser config.
                An explicit empty string / null CLEARS the parser (reverts
                the listing to the default JSON-LD + AI pipeline).
            currency: ISO currency override (optional)
            retailer: display name override (optional)
            request_cookies: cookies for anti-bot bypass (optional). Accepts
                a Cookie-header string, a {name: value} dict, or a list of
                {name, value, ...} dicts. Stored inside custom_parser and
                kept independent of the parser's selectors — setting one
                doesn't clobber the other. An empty value clears cookies.

        Only the fields present in the call are touched; everything else on
        the listing is preserved. Reloads the entry so the coordinator
        re-reads the parser and the next poll uses it. Unlike remove_listing
        this is allowed on the PRIMARY listing — a custom price selector is
        exactly as useful there.
        """
        entry = _resolve_entry(call)
        listing_id = (call.data.get("listing_id") or "").strip()
        if not listing_id:
            raise HomeAssistantError("listing_id is required")

        existing = list(entry.options.get("listings") or [])
        target = None
        for listing in existing:
            if isinstance(listing, dict) and listing.get("id") == listing_id:
                target = listing
                break
        if target is None:
            raise HomeAssistantError(
                f"Listing {listing_id!r} not found on entry {entry.entry_id}"
            )

        # Cookies are stored INSIDE custom_parser.request_cookies (the only
        # place the extractor reads them) but are treated as ORTHOGONAL to
        # the rest of the parser, so the two can be edited independently:
        #   - Setting a new custom_parser preserves existing cookies. The
        #     panel rewrites custom_parser wholesale and can't see the cookie
        #     value (cookies are never surfaced to the frontend), so without
        #     this a selector edit would silently drop the cookies.
        #   - Setting request_cookies updates/clears cookies in place without
        #     disturbing the rest of the parser.
        prior_parser = target.get("custom_parser")
        prior_cookies = (
            prior_parser.get("request_cookies")
            if isinstance(prior_parser, dict)
            else None
        )

        # custom_parser: present-and-empty clears it; present-and-set parses
        # it; absent leaves it untouched.
        if "custom_parser" in call.data:
            raw = call.data.get("custom_parser")
            if not raw:
                target["custom_parser"] = None
            elif isinstance(raw, dict):
                target["custom_parser"] = dict(raw)
            else:
                try:
                    import json as _json
                    target["custom_parser"] = _json.loads(raw)
                except Exception as err:  # noqa: BLE001
                    raise HomeAssistantError(
                        f"custom_parser is not valid JSON: {err}"
                    ) from err
            # Carry existing cookies across the replacement unless the new
            # parser brought its own, or request_cookies is being set below
            # (which is authoritative). A cleared parser keeps cookies alive
            # on their own — clearing a selector shouldn't drop a session.
            if "request_cookies" not in call.data and prior_cookies:
                new_parser = target["custom_parser"]
                if isinstance(new_parser, dict):
                    new_parser.setdefault("request_cookies", prior_cookies)
                else:
                    target["custom_parser"] = {"request_cookies": prior_cookies}

        if "currency" in call.data:
            target["currency"] = call.data.get("currency") or ""
        if "retailer" in call.data and call.data.get("retailer"):
            target["retailer"] = call.data["retailer"]

        if "request_cookies" in call.data:
            cookie_str = _cookies_to_header_str(call.data.get("request_cookies"))
            base = target.get("custom_parser")
            parser = dict(base) if isinstance(base, dict) else {}
            if cookie_str:
                parser["request_cookies"] = cookie_str
            else:
                parser.pop("request_cookies", None)
            target["custom_parser"] = parser or None

        # Drop the legacy top-level field if a prior version wrote it; the
        # extractor never read it, so leaving it would be a silent no-op.
        target.pop("request_cookies", None)

        new_options = dict(entry.options)
        new_options["listings"] = existing
        hass.config_entries.async_update_entry(entry, options=new_options)

        _LOGGER.info(
            "edit_listing: updated listing %s on entry %s; reloading",
            listing_id, entry.entry_id,
        )
        await hass.config_entries.async_reload(entry.entry_id)

    async def track_product(call: ServiceCall) -> None:
        """Create a tracked product from an in-panel search pick.

        Drives the config flow's `panel_track` source step, which creates
        the product entry in one shot (no extraction preview). Used by the
        panel's live-search "Track" dialog. The new entry's entities then
        surface in the panel via its entity_registry_updated subscription,
        so this is effectively fire-and-forget from the caller's side —
        but we raise on a flow abort so the panel can show a clear message
        (e.g. the product is already tracked).
        """
        url = (call.data.get("url") or "").strip()
        if not url:
            raise HomeAssistantError("url is required")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "panel_track"},
            data={
                "url": url,
                "name": (call.data.get("name") or "").strip(),
                "target_price": call.data.get("target_price"),
            },
        )

        if result.get("type") == "abort":
            reason = result.get("reason", "unknown")
            if reason == "already_configured":
                raise HomeAssistantError(
                    "This product is already being tracked."
                )
            raise HomeAssistantError(f"Could not add product: {reason}")

        _LOGGER.info("track_product: created entry for %s", url)

    target_schema = vol.Schema(
        {
            vol.Optional("entry_id"): str,
            vol.Optional("device_id"): vol.Any(str, [str]),
        }
    )

    hass.services.async_register(DOMAIN, "refresh_now", refresh_now, schema=target_schema)
    hass.services.async_register(
        DOMAIN,
        "set_target",
        set_target,
        schema=target_schema.extend(
            {vol.Optional(CONF_TARGET_PRICE): vol.Any(None, vol.Coerce(float))}
        ),
    )
    hass.services.async_register(DOMAIN, "reset_history", reset_history, schema=target_schema)
    hass.services.async_register(
        DOMAIN,
        "set_paused",
        set_paused,
        schema=target_schema.extend(
            {vol.Optional("paused", default=True): vol.Coerce(bool)}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "find_alternatives",
        find_alternatives,
        schema=target_schema.extend(
            {
                vol.Optional("max_results"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=20)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "add_listing",
        add_listing,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("url"): str,
                vol.Optional("retailer"): str,
                vol.Optional("currency"): str,
                vol.Optional("custom_parser"): vol.Any(str, dict),
                vol.Optional("request_cookies"): vol.Any(str, dict, list),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "remove_listing",
        remove_listing,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("listing_id"): str,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "edit_listing",
        edit_listing,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("listing_id"): str,
                vol.Optional("custom_parser"): vol.Any(None, str, dict),
                vol.Optional("currency"): str,
                vol.Optional("retailer"): str,
                vol.Optional("request_cookies"): vol.Any(str, dict, list),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "track_product",
        track_product,
        schema=vol.Schema(
            {
                vol.Required("url"): str,
                vol.Optional("name"): str,
                vol.Optional("target_price"): vol.Any(None, vol.Coerce(float)),
            }
        ),
    )
