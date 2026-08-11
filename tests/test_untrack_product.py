"""Tests for the untrack_product service — deletes a whole product.

untrack_product backs the panel's per-card delete button. It resolves the
target entry through the shared _resolve_entry guard (product entries only)
and removes the config entry, so HA unloads it and runs async_remove_entry to
drop the per-entry store.

These register the services directly via _register_services — no coordinator,
no network — then exercise the happy path plus both guard rejections (the
settings entry and an unknown id), asserting the wrong targets are left
untouched.
"""
from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.price_watch import _register_services
from custom_components.price_watch.const import (
    DOMAIN,
    ENTRY_TYPE_PRODUCT,
    ENTRY_TYPE_SETTINGS,
)


async def _register(hass) -> None:
    """Register the price_watch services and confirm untrack is present."""
    await _register_services(hass)
    assert hass.services.has_service(DOMAIN, "untrack_product")


def _product_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={"entry_type": ENTRY_TYPE_PRODUCT, "url": "https://shop.example/p"},
        options={"listings": [{"id": "l_abc", "url": "https://shop.example/p"}]},
    )


async def test_untrack_removes_product_entry(hass):
    """The happy path: the product's config entry is gone afterwards."""
    await _register(hass)
    entry = _product_entry()
    entry.add_to_hass(hass)
    assert hass.config_entries.async_get_entry(entry.entry_id) is not None

    await hass.services.async_call(
        DOMAIN, "untrack_product", {"entry_id": entry.entry_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(entry.entry_id) is None


async def test_untrack_rejects_settings_entry(hass):
    """The settings entry is not a product — untrack must refuse and leave it."""
    await _register(hass)
    settings = MockConfigEntry(
        domain=DOMAIN,
        data={"entry_type": ENTRY_TYPE_SETTINGS},
        options={"ai_provider": "none"},
    )
    settings.add_to_hass(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "untrack_product",
            {"entry_id": settings.entry_id},
            blocking=True,
        )

    assert hass.config_entries.async_get_entry(settings.entry_id) is not None


async def test_untrack_rejects_unknown_entry(hass):
    """An entry_id that doesn't exist raises rather than silently no-op'ing."""
    await _register(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "untrack_product",
            {"entry_id": "does-not-exist"},
            blocking=True,
        )
