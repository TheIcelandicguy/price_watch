"""Contract tests for the public surface: services and event names.

Everything in here is something outside code depends on — a user's
automation, a script, the panel's own service calls — so it breaks
differently from ordinary logic. A renamed event fires into the void and
nothing in the log says so; a service documented in services.yaml but
never registered shows up in the UI's service picker and then fails when
called; a field renamed in code but not in the YAML (or the reverse)
gives the caller a validation error for a key the docs told them to use.

None of that is visible to a unit test of the logic underneath, and none
of it is visible to check_docs.py either, which checks CLAUDE.md rather
than services.yaml. So these tests pin the surface itself:

  names     services.yaml and the registered services match, both ways
  fields    every field services.yaml documents is one the schema accepts
  events    the event identifiers are spelled price_watch_* and are pinned
            to their current values, because renaming one silently breaks
            every automation already built on it

The event names are deliberately written out as literals here rather than
imported and compared to themselves — a test that reads the constant it
is checking would pass through any rename.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import voluptuous as vol
import yaml
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import price_watch as pw
from custom_components.price_watch import const
from custom_components.price_watch.const import DOMAIN, ENTRY_TYPE_SETTINGS

# The identifiers automations are built on. Spelled out, not imported.
EXPECTED_EVENTS = {
    "price_watch_price_drop",
    "price_watch_target_hit",
    "price_watch_new_low",
    "price_watch_back_in_stock",
    "price_watch_discount",
    "price_watch_discontinued",
}


def _documented_services() -> dict[str, dict[str, Any]]:
    """services.yaml, as the service picker in the UI reads it."""
    path = Path(pw.__file__).parent / "services.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict) and loaded, "services.yaml is empty or not a map"
    return loaded


async def _register_all(hass) -> dict[str, Any]:
    """Register every service the way a loaded install does.

    The settings entry is the one that always exists, and it registers the
    full set on its own — that is what makes a zero-product install usable
    — so loading it is enough, with no coordinator and no network.
    """
    await pw._register_services(hass)
    services = hass.services.async_services().get(DOMAIN, {})
    assert services, "no price_watch services were registered"
    return services


def _schema_field_names(service) -> set[str]:
    """The top-level keys a registered service's schema accepts.

    Returns an empty set for a service with no schema (it takes anything),
    so the caller can skip it rather than assert against nothing.
    """
    schema = getattr(service, "schema", None)
    if schema is None:
        return set()
    inner = getattr(schema, "schema", None)
    if not isinstance(inner, dict):
        return set()
    names: set[str] = set()
    for key in inner:
        if isinstance(key, (vol.Required, vol.Optional, vol.Marker)):
            names.add(str(key.schema))
        else:
            names.add(str(key))
    return names


# --- names ---------------------------------------------------------------


async def test_every_documented_service_is_registered(hass):
    """A service in the YAML but not in the code appears in the UI picker
    and fails only when somebody calls it."""
    registered = await _register_all(hass)
    documented = _documented_services()

    missing = sorted(set(documented) - set(registered))
    assert not missing, f"documented in services.yaml but never registered: {missing}"


async def test_every_registered_service_is_documented(hass):
    """The other direction: a service with no YAML entry has no
    description, no field hints, and is invisible in the UI."""
    registered = await _register_all(hass)
    documented = _documented_services()

    undocumented = sorted(set(registered) - set(documented))
    assert not undocumented, f"registered but missing from services.yaml: {undocumented}"


# --- fields --------------------------------------------------------------


async def test_documented_fields_are_accepted_by_the_schema(hass):
    """Every field the YAML advertises has to be one the schema allows.

    This is the drift that produces the worst error message in practice:
    the UI offers a field, the user fills it in, and the call fails
    validation on a key the docs told them to use.
    """
    registered = await _register_all(hass)
    documented = _documented_services()

    problems: list[str] = []
    checked = 0
    for name, spec in documented.items():
        service = registered.get(name)
        if service is None:
            continue  # covered by the names test above
        accepted = _schema_field_names(service)
        if not accepted:
            continue  # no schema: takes anything
        for field in (spec or {}).get("fields", {}) or {}:
            checked += 1
            if field not in accepted:
                problems.append(f"{name}.{field}")
    assert not problems, (
        "services.yaml documents fields the schema rejects: " f"{sorted(problems)}"
    )
    # Without this the test would pass silently if schema introspection
    # ever stopped returning keys — a green test that compares nothing.
    assert checked > 20, f"only {checked} fields compared; introspection broke"


async def test_a_service_call_rejects_an_unknown_field(hass):
    """The schemas are strict, so a typo in an automation is a loud error
    rather than a silently ignored key."""
    await _register_all(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"entry_type": ENTRY_TYPE_SETTINGS},
        options={"ai_provider": "none"},
    )
    entry.add_to_hass(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_target",
            {"entry_id": entry.entry_id, "not_a_real_field": 1},
            blocking=True,
        )


# --- events --------------------------------------------------------------


def test_event_names_are_pinned():
    """Renaming an event is a breaking change for every automation built
    on it, so the literals are the contract."""
    actual = {
        value
        for name, value in vars(const).items()
        if name.startswith("EVENT_") and isinstance(value, str)
    }
    assert actual == EXPECTED_EVENTS


def test_event_names_are_namespaced():
    """An event without the domain prefix can collide with another
    integration's bus traffic."""
    for name, value in vars(const).items():
        if name.startswith("EVENT_") and isinstance(value, str):
            assert value.startswith(f"{DOMAIN}_"), f"{name} = {value!r}"
