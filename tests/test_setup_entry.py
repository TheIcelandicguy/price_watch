"""Tests that the integration actually loads inside Home Assistant.

Every other test here drives a mixin or a helper on a stand-in object,
which is fast and focused but shares one blind spot: nothing imports the
package the way HA does. A module that references a name it forgot to
import — a `from .const import X` dropped by a refactor — collects and
passes clean, then fails at runtime on the real instance. The symptom
there is every sensor going unknown after a restart, with nothing in the
test output to explain it.

So this module covers what the rest cannot:

  imports     every module in the component is imported, including the
              ones setup never reaches (migration, diagnostics,
              websocket), so a missing name fails a test
  settings    the settings entry sets up alone and registers the
              services, panel and WS API — the from-scratch install with
              zero products
  product     a product entry reaches LOADED, builds its coordinator and
              entities on all four platforms, then unloads clean
  values      a product whose page returns a price ends up with that
              price on its sensor: setup -> coordinator -> store ->
              entity, the whole chain

The network is never touched. `paused` short-circuits the fetch for the
structural tests; the one test that wants data patches extract_product.
"""

from __future__ import annotations

import contextlib
import importlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import price_watch as pw
from custom_components.price_watch import coordinator as coordinator_mod
from custom_components.price_watch import coordinator_update as cu
from custom_components.price_watch.const import (
    CONF_PAUSED,
    CONF_URL,
    DOMAIN,
    ENTRY_TYPE_PRODUCT,
    ENTRY_TYPE_SETTINGS,
)
from custom_components.price_watch.extractor import ExtractionResult

URL = "https://www.tolvutek.is/vara/rtx-5080"


def _result(price: float = 129900.0) -> ExtractionResult:
    return ExtractionResult(
        title="RTX 5080",
        price=price,
        currency="ISK",
        in_stock=True,
        stock_count=None,
        image_url=None,
        sku=None,
        retailer="Tolvutek",
        content_hash="abc",
        cost_usd=0.0,
        method="jsonld",
        raw={},
    )


def _product_entry(*, paused: bool) -> MockConfigEntry:
    """A product tracked by URL — the shape the config flow creates.

    Deliberately no `listings` option: a by-URL product has an implicit
    primary that the integration materializes on load, with an id derived
    from the URL rather than one a caller picks. That is the shape issue #3
    was about, so it is the one worth loading here.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="RTX 5080",
        data={"entry_type": ENTRY_TYPE_PRODUCT, CONF_URL: URL},
        options={CONF_PAUSED: paused},
    )


def _settings_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Price Watch settings",
        data={"entry_type": ENTRY_TYPE_SETTINGS},
        options={"ai_provider": "none"},
    )


def _stub_http(hass) -> None:
    """Stand in for the one http API the panel uses.

    async_register_panel serves its bundle through
    hass.http.async_register_static_paths, so without `hass.http` every
    setup below fails for a reason unrelated to the code under test.

    Neither real component is set up, deliberately: `frontend` imports the
    hass_frontend wheel, which is not a test dependency, and `http` starts
    a shutdown-loop thread that the HA harness flags as a leak at
    teardown. Stubbing the single call keeps all of panel.py running — the
    bundle-exists check, the mtime cache-buster, the sidebar registration,
    which only writes to hass.data — while leaving the static-file
    plumbing, which is HA's code and not ours, out of it.
    """
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()


@contextlib.contextmanager
def _offline():
    """No real aiohttp session for the duration of a setup.

    The coordinator builds one in __init__ for FX, and HA's shared session
    resolves through aiodns, whose pycares resolver starts a shutdown-loop
    thread — which the HA harness then reports as a leaked thread at
    teardown. Handing out None matches what test_transient_block.py does
    and keeps these tests off the network besides.
    """
    with patch.object(
        coordinator_mod, "async_get_clientsession", lambda hass: None
    ), patch.object(cu, "async_get_clientsession", lambda hass: None):
        yield


# --- imports -------------------------------------------------------------


def test_every_module_imports():
    """Import every module in the package, not just the ones setup loads.

    The cheap guard for the whole class of NameError-at-runtime bugs: a
    module that only blows up when HA first calls into it.
    """
    root = Path(pw.__file__).parent
    modules = sorted(
        ".".join(p.relative_to(root).with_suffix("").parts)
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts and p.stem != "__init__"
    )
    assert modules, "found no modules to import — did the package move?"
    for name in modules:
        importlib.import_module(f"custom_components.price_watch.{name}")


# --- the settings entry stands alone -------------------------------------


async def test_settings_entry_sets_up_with_no_products(hass):
    """A fresh install has only the settings entry, and it must still
    register the services and panel — otherwise there is no way to add a
    first product."""
    _stub_http(hass)
    entry = _settings_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN]["settings"] == entry.entry_id
    # track_product is what the panel's search-and-add calls.
    assert hass.services.has_service(DOMAIN, "track_product")
    assert hass.services.has_service(DOMAIN, "refresh_now")


# --- a product entry loads, creates entities, unloads --------------------


async def test_product_entry_loads_and_creates_entities(hass):
    """Paused so nothing is fetched: this is purely about setup reaching
    the end and the platforms producing entities."""
    _stub_http(hass)
    entry = _product_entry(paused=True)
    entry.add_to_hass(hass)

    with _offline():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # The implicit primary was materialized, and nothing else came with it.
    assert coordinator.listing_ids == [coordinator.primary_listing_id]
    # Paused stops the polling loop, rather than skipping one fetch.
    assert coordinator.update_interval is None

    entities = er.async_get(hass).entities.get_entries_for_config_entry_id(
        entry.entry_id
    )
    assert entities, "the entry loaded but produced no entities"
    domains = {e.domain for e in entities}
    for platform in (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.IMAGE,
    ):
        assert platform.value in domains, f"no {platform.value} entity was created"


async def test_product_entry_unloads_clean(hass):
    """Unload has to drop the coordinator, or a reload leaks the old one."""
    _stub_http(hass)
    entry = _product_entry(paused=True)
    entry.add_to_hass(hass)
    with _offline():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


# --- the whole chain, with a price ---------------------------------------


async def test_price_from_the_page_reaches_a_sensor(hass):
    """setup -> background refresh -> store -> entity state.

    The initial fetch is a jittered background task, so the jitter is
    zeroed rather than slept through.
    """
    _stub_http(hass)
    entry = _product_entry(paused=False)
    entry.add_to_hass(hass)

    async def _extract(*args: Any, **kwargs: Any) -> ExtractionResult:
        return _result()

    with _offline(), patch.object(cu, "extract_product", _extract), patch.object(
        pw.random, "uniform", lambda a, b: 0
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.last_update_success, coordinator.last_exception
    assert coordinator.get_listing_result(coordinator.primary_listing_id).price == 129900.0

    prices = [
        hass.states.get(e.entity_id)
        for e in er.async_get(hass).entities.get_entries_for_config_entry_id(
            entry.entry_id
        )
        if e.domain == Platform.SENSOR.value and e.unique_id.endswith("_price")
    ]
    assert prices, "no price sensor was registered"
    assert any(s is not None and s.state == "129900.0" for s in prices), [
        s.state for s in prices if s
    ]
