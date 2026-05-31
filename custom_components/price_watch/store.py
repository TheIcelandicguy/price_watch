"""Per-product persistence helpers for Price Watch.

Extracted from coordinator.py. Holds:
- `derive_listing_id`: the deterministic listing-id formula that ties a
  migrated entry's options to its migrated storage data.
- `PriceWatchStore`: the HA Store subclass with built-in v1 → v2 storage
  migration.
- `empty_listing_state`: the default runtime-state dict for a fresh listing.

These are kept together because they all concern the on-disk / runtime
state shape, independent of the coordinator's update loop.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_VERSION
from .migration import migrate_storage_v1_to_v2

_LOGGER = logging.getLogger(__name__)


def derive_listing_id(entry: ConfigEntry) -> str:
    """Deterministic listing-id derivation from entry_id.

    Must produce the same id as async_migrate_entry's derivation —
    that's the contract that ties migrated entry options to migrated
    storage data. ULID suffix gives plenty of entropy.
    """
    return f"l_{entry.entry_id[-12:].lower()}"


def empty_listing_state() -> dict[str, Any]:
    """Default runtime-state dict for a fresh listing.

    Used to initialize new listings and as the fallback when the
    primary listing is missing from storage (defensive — shouldn't
    happen). Keys here match what _async_update_one_listing
    reads/writes.
    """
    return {
        "history": [],
        "lowest": None,
        "highest": None,
        "last_hash": None,
        "last_result": None,
        "last_check": None,
        "lifetime_cost_usd": 0.0,
        "discontinued": False,
        "discontinued_at": None,
        "discontinued_reason": None,
        "discontinued_title": None,
        "lkg_price": None,
        "lkg_currency": None,
        "lkg_observed_at": None,
    }


class PriceWatchStore(Store[dict[str, Any]]):
    """Per-product Store with built-in v1 → v2 migration.

    HA calls _async_migrate_func when the on-disk version is older
    than the requested STORAGE_VERSION. We use the listing-id captured
    at construction time to nest v1's flat history under the right
    listings[id] key in v2.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        key: str,
        *,
        listing_id: str,
    ) -> None:
        super().__init__(hass, STORAGE_VERSION, key)
        self._listing_id = listing_id

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: Any,
    ) -> dict[str, Any]:
        """Migrate v1 storage to v2 shape.

        Called by HA's Store load path when the persisted version is
        below STORAGE_VERSION. Returns the new shape, which HA then
        persists (so future loads bypass migration).
        """
        if old_major_version < 2:
            _LOGGER.info(
                "Storage migration v%s → v2 for listing %s",
                old_major_version, self._listing_id,
            )
            return migrate_storage_v1_to_v2(
                old_data or {}, listing_id=self._listing_id,
            )
        # Future version we don't know about — return as-is. HA will
        # log a warning.
        return old_data
