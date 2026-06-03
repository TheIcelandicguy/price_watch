"""Event-firing mixin for PriceWatchCoordinator.

Extracted from coordinator.py. These methods emit the Home Assistant bus
events (price drop, new low, back-in-stock, target hit, discontinued) with
a consistent payload shape so downstream automations get the same fields on
every event. They are self-contained: they only read coordinator identity
(entry, url, target) plus the current/previous ExtractionResult, then call
``hass.bus.async_fire``.

All attributes referenced via ``self`` are defined on the concrete
PriceWatchCoordinator. The TYPE_CHECKING block documents the contract
without creating an import cycle; at runtime they resolve through the
coordinator instance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import EVENT_TARGET_HIT

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .extractor import ExtractionResult


class EventsMixin:
    """HA bus event emission for PriceWatchCoordinator."""

    if TYPE_CHECKING:
        hass: HomeAssistant
        entry: ConfigEntry
        url: str
        _target_price: float | None

    def _fire_event(
        self, event_type: str, result: ExtractionResult, previous: ExtractionResult | None
    ) -> None:
        """Fire an HA event with consistent payload shape."""
        self.hass.bus.async_fire(
            event_type,
            {
                "entry_id": self.entry.entry_id,
                "title": result.title,
                "url": self.url,
                "retailer": result.retailer,
                "price": result.price,
                "currency": result.currency,
                "previous_price": previous.price if previous else None,
                "target": self._target_price,
                "image_url": result.image_url,
                "in_stock": result.in_stock,
            },
        )

    def _fire_event_with_extra(
        self,
        event_type: str,
        result: ExtractionResult,
        previous: ExtractionResult | None,
        extra: dict[str, Any],
    ) -> None:
        """Same as _fire_event but merges in event-type-specific fields.

        Used by EVENT_DISCONTINUED to attach last_known_price /
        discontinued_at / discontinued_reason that aren't present on
        regular price events.
        """
        payload = {
            "entry_id": self.entry.entry_id,
            "title": result.title,
            "url": self.url,
            "retailer": result.retailer,
            "price": result.price,
            "currency": result.currency,
            "previous_price": previous.price if previous else None,
            "target": self._target_price,
            "image_url": result.image_url,
            "in_stock": result.in_stock,
        }
        payload.update(extra)
        self.hass.bus.async_fire(event_type, payload)

    def _fire_target_hit(
        self, result: ExtractionResult, previous: ExtractionResult | None
    ) -> None:
        self._fire_event(EVENT_TARGET_HIT, result, previous)
