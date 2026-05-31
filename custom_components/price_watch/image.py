"""Image platform for Price Watch - one product photo per listing.

Uses bytes-mode (not URL-mode) because many e-commerce CDNs are
Cloudflare-protected and block plain HTTP clients including HA's image
proxy. The coordinator fetches bytes via curl_cffi (Chrome TLS
impersonation) and we serve them directly.

Phase 3c: one image entity per tracked listing. The primary listing
keeps the legacy unique_id `{entry_id}_photo` (so existing registry
entries and the panel's product-level image keep working); secondary
listings use `{entry_id}_{listing_id}_photo`, mirroring the per-listing
sensor naming so the panel can route each listing row to its own photo.
"""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import ENTRY_TYPE_PRODUCT
from .const import DOMAIN
from .coordinator import PriceWatchCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one image entity per listing."""
    if entry.data.get("entry_type") != ENTRY_TYPE_PRODUCT:
        return

    coordinator: PriceWatchCoordinator = hass.data[DOMAIN][entry.entry_id]
    primary_id = coordinator.primary_listing_id

    entities = [
        ListingImage(hass, coordinator, listing_id, listing_id == primary_id)
        for listing_id in coordinator.listing_ids
    ]
    async_add_entities(entities)


class ListingImage(CoordinatorEntity[PriceWatchCoordinator], ImageEntity):
    """One listing's photo, served as bytes from the coordinator's cache.

    Why bytes-mode instead of URL-mode: many e-commerce image CDNs
    (Komplett's product-media subdomain, NetOnNet, etc.) are
    Cloudflare-protected and block plain HTTP clients via TLS
    fingerprinting. HA's URL-mode image fetcher uses aiohttp and gets
    silently blocked. By fetching the image during our coordinator update
    (which uses curl_cffi with Chrome TLS impersonation, the same path
    that gets us through for the product page itself), we sidestep the
    problem entirely.

    The primary listing keeps unique_id `{entry_id}_photo` and is named
    "Photo"; secondary listings use `{entry_id}_{listing_id}_photo` and
    are named "<Retailer> Photo" for clarity in the entity list.
    """

    _attr_has_entity_name = True
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PriceWatchCoordinator,
        listing_id: str,
        is_primary: bool,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._listing_id = listing_id
        self._is_primary = is_primary

        entry_id = coordinator.entry.entry_id
        if is_primary:
            # Legacy form — matches existing entity registry entries and
            # the panel's product-level image lookup.
            self._attr_unique_id = f"{entry_id}_photo"
            self._attr_translation_key = "photo"
            self._attr_name = "Photo"
        else:
            self._attr_unique_id = f"{entry_id}_{listing_id}_photo"
            config = coordinator.get_listing_config(listing_id) or {}
            retailer = config.get("retailer")
            self._attr_name = f"{retailer} Photo" if retailer else "Photo"

        self._sync_from_coordinator()

    @property
    def device_info(self) -> dict:
        return self.coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Pull the current image state from the coordinator into our attrs."""
        self._sync_from_coordinator()
        super()._handle_coordinator_update()

    def _sync_from_coordinator(self) -> None:
        """Update content_type + last_updated whenever the image changes."""
        bytes_ = self.coordinator.image_bytes_for(self._listing_id)
        ct = self.coordinator.image_content_type_for(self._listing_id)
        if ct:
            self._attr_content_type = ct
        # Bump last_updated whenever we have fresh bytes; HA uses this to
        # decide whether the cached frontend copy needs to be refetched.
        if bytes_ is not None:
            self._attr_image_last_updated = datetime.now(timezone.utc)

    async def async_image(self) -> bytes | None:
        """Return this listing's image bytes, or None if we have nothing yet."""
        return self.coordinator.image_bytes_for(self._listing_id)

    @property
    def available(self) -> bool:
        """Hide entity until we have actual image bytes."""
        if not super().available:
            return False
        return self.coordinator.image_bytes_for(self._listing_id) is not None
