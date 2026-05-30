"""Button platform for Price Watch - one-click refresh per product."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up the per-product refresh button."""
    if entry.data.get("entry_type") != ENTRY_TYPE_PRODUCT:
        return

    coordinator: PriceWatchCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RefreshNowButton(coordinator)])


class RefreshNowButton(CoordinatorEntity[PriceWatchCoordinator], ButtonEntity):
    """Button that triggers an immediate price re-check.

    Bypasses the normal scan interval. Useful for testing target prices,
    confirming a sale ended, or just impatient checking.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_now"
    _attr_name = "Refresh now"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: PriceWatchCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_refresh_now"

    @property
    def device_info(self) -> dict:
        return self.coordinator.device_info

    async def async_press(self) -> None:
        """Trigger a refresh."""
        await self.coordinator.async_request_refresh()
