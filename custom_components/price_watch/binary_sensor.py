"""Binary sensor platform for Price Watch — in-stock + discontinued status.

Phase 2.3+: per-listing binary sensors. Each listing gets its own
in_stock and discontinued sensors. The primary listing keeps legacy
unique_ids ({entry}_in_stock, {entry}_discontinued) for back-compat;
secondary listings use {entry}_{listing}_in_stock / _{listing}_discontinued.

When a product has multi-listing, stock status is naturally per-listing
(Newegg might be out while Komplett is in stock), and discontinuation is
also per-listing (one retailer can delist while another keeps selling).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Set up binary sensors for a product entry.

    Iterates coordinator.listing_ids and creates an InStockSensor +
    DiscontinuedSensor per listing. Mirrors sensor.async_setup_entry.
    """
    if entry.data.get("entry_type") != ENTRY_TYPE_PRODUCT:
        return

    coordinator: PriceWatchCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []
    for listing_id in coordinator.listing_ids:
        entities.append(InStockSensor(coordinator, listing_id))
        entities.append(DiscontinuedSensor(coordinator, listing_id))
    async_add_entities(entities)


class _BasePriceWatchBinarySensor(
    CoordinatorEntity[PriceWatchCoordinator], BinarySensorEntity
):
    """Common per-listing plumbing shared by InStock + Discontinued.

    Mirrors _BasePriceWatchSensor in sensor.py: primary listing keeps
    legacy unique_id; secondary listings get listing-prefixed unique_ids
    and retailer-prefixed entity names.
    """

    _attr_has_entity_name = True
    # Subclass sets _key and _label for unique_id + name disambiguation
    _key: str = ""
    _label: str = ""

    def __init__(
        self,
        coordinator: PriceWatchCoordinator,
        listing_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._listing_id = listing_id

        entry_id = coordinator.entry.entry_id
        if listing_id == coordinator.primary_listing_id:
            # Legacy unique_id — matches pre-Phase-2.3+ entity registry
            self._attr_unique_id = f"{entry_id}_{self._key}"
        else:
            # Per-listing unique_id for secondary listings
            self._attr_unique_id = f"{entry_id}_{listing_id}_{self._key}"
            # Retailer-prefixed name for entity-list disambiguation
            config = coordinator.get_listing_config(listing_id) or {}
            retailer = config.get("retailer")
            if retailer:
                self._attr_name = f"{retailer} {self._label}"

    @property
    def device_info(self) -> dict:
        return self.coordinator.device_info

    @property
    def _result(self):
        """Latest ExtractionResult for THIS sensor's listing (or None)."""
        return self.coordinator.get_listing_result(self._listing_id)

    @property
    def _listing_state(self) -> dict[str, Any]:
        """Runtime state dict for THIS sensor's listing (or empty)."""
        return self.coordinator.get_listing_state(self._listing_id) or {}


class InStockSensor(_BasePriceWatchBinarySensor):
    """Binary sensor for in-stock status of a specific listing."""

    _attr_translation_key = "in_stock"
    _key = "in_stock"
    _label = "In stock"

    @property
    def is_on(self) -> bool | None:
        """Return True if in stock.

        Prefer the numeric stock_count when available — "0" decisively
        means out of stock and "1+" decisively in stock, regardless of
        what the source's availability flag claimed (which sometimes
        lags reality on retailer pages). Falls back to the source's
        boolean when no count is available.

        Discontinued listings are always reported as out-of-stock
        (False), not unknown, so dashboards don't flicker between
        unknown/off.
        """
        result = self._result
        if result is None:
            return None
        if result.discontinued:
            return False
        if result.stock_count is not None:
            return result.stock_count > 0
        return result.in_stock

    @property
    def icon(self) -> str:
        """Mirror current in-stock state in the icon."""
        if self.is_on is True:
            return "mdi:package-variant"
        if self.is_on is False:
            return "mdi:package-variant-closed"
        return "mdi:package-variant-closed-remove"


class DiscontinuedSensor(_BasePriceWatchBinarySensor):
    """Binary sensor that turns on when a listing is permanently delisted.

    Distinct from InStock — a temporarily out-of-stock listing flips
    in_stock off but stays available for re-checking; a discontinued
    listing flips this sensor on and (if it's the primary listing) the
    coordinator stops polling the whole product.
    """

    _attr_translation_key = "discontinued"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:archive-remove"
    _key = "discontinued"
    _label = "Discontinued"

    @property
    def is_on(self) -> bool | None:
        result = self._result
        if result is None:
            return None
        return result.discontinued

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose discontinuation context for automations and the panel.

        Only present when the LISTING is actually discontinued; on a
        normal listing we return None so the entity stays uncluttered.
        Reads from per-listing state — discontinuation is independent
        across listings (one retailer can delist while another doesn't).
        """
        result = self._result
        if result is None or not result.discontinued:
            return None
        state = self._listing_state
        return {
            "listing_id": self._listing_id,
            "discontinued_reason": result.discontinued_reason,
            "discontinued_at": state.get("discontinued_at"),
            "last_known_price": state.get("lkg_price"),
            "last_known_currency": state.get("lkg_currency"),
            "last_known_observed_at": state.get("lkg_observed_at"),
        }
