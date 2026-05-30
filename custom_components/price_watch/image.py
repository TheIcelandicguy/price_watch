"""Image platform for Price Watch - product photo per device.

Uses bytes-mode (not URL-mode) because many e-commerce CDNs are
Cloudflare-protected and block plain HTTP clients including HA's image
proxy. The coordinator fetches bytes via curl_cffi (Chrome TLS
impersonation) and we serve them directly.
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
    """Set up the per-product image."""
    if entry.data.get("entry_type") != ENTRY_TYPE_PRODUCT:
        return

    coordinator: PriceWatchCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ProductImage(hass, coordinator)])


class ProductImage(CoordinatorEntity[PriceWatchCoordinator], ImageEntity):
    """Product photo, served as bytes from the coordinator's cache.

    Why bytes-mode instead of URL-mode: many e-commerce image CDNs
    (Komplett's product-media subdomain, NetOnNet, etc.) are
    Cloudflare-protected and block plain HTTP clients via TLS
    fingerprinting. HA's URL-mode image fetcher uses aiohttp and gets
    silently blocked. By fetching the image during our coordinator update
    (which uses curl_cffi with Chrome TLS impersonation, the same path
    that gets us through for the product page itself), we sidestep the
    problem entirely.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "photo"
    _attr_name = "Photo"
    _attr_content_type = "image/jpeg"

    def __init__(
        self, hass: HomeAssistant, coordinator: PriceWatchCoordinator
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_photo"
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
        bytes_ = self.coordinator.image_bytes
        ct = self.coordinator.image_content_type
        if ct:
            self._attr_content_type = ct
        # Bump last_updated whenever we have fresh bytes; HA uses this to
        # decide whether the cached frontend copy needs to be refetched.
        if bytes_ is not None:
            self._attr_image_last_updated = datetime.now(timezone.utc)

    async def async_image(self) -> bytes | None:
        """Return the current image bytes, or None if we have nothing yet."""
        return self.coordinator.image_bytes

    @property
    def available(self) -> bool:
        """Hide entity until we have actual image bytes."""
        if not super().available:
            return False
        return self.coordinator.image_bytes is not None
