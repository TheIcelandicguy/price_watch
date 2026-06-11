"""Tests for diagnostics — especially that secrets are redacted."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.price_watch import diagnostics
from custom_components.price_watch.const import DOMAIN, ENTRY_TYPE_SETTINGS

REDACTED = "**REDACTED**"


def test_summarize_parser_drops_cookies():
    p = {
        "type": "css",
        "selectors": {"price": "span.price"},
        "transforms": {"price": "price_clean"},
        "request_cookies": "session=secret",
    }
    s = diagnostics._summarize_parser(p)
    assert "request_cookies" not in s
    assert s["has_cookies"] is True
    assert s["type"] == "css"
    assert s["selectors"] == {"price": "span.price"}
    assert diagnostics._summarize_parser(None) is None


@pytest.mark.asyncio
async def test_settings_diagnostics_redacts_api_key(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"entry_type": ENTRY_TYPE_SETTINGS},
        options={
            "ai_provider": "anthropic",
            "api_key": "sk-ant-SUPERSECRET",
            "model": "claude-haiku-4-5",
        },
    )
    entry.add_to_hass(hass)
    out = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
    assert out["entry"]["type"] == ENTRY_TYPE_SETTINGS
    assert out["options"]["api_key"] == REDACTED
    assert out["options"]["model"] == "claude-haiku-4-5"  # non-secret preserved


@pytest.mark.asyncio
async def test_product_diagnostics_redacts_nested_cookies(hass):
    """request_cookies buried in options.listings[].custom_parser is redacted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"entry_type": "product", "url": "https://shop.example/p"},
        options={
            "listings": [
                {
                    "id": "l_abc",
                    "url": "https://shop.example/p",
                    "custom_parser": {
                        "type": "css",
                        "selectors": {"price": "span.price"},
                        "request_cookies": "session=topsecret",
                    },
                }
            ]
        },
    )
    entry.add_to_hass(hass)
    out = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
    # No coordinator in this lightweight test, but options redaction still runs.
    assert out["coordinator"] == "not loaded"
    parser = out["options"]["listings"][0]["custom_parser"]
    assert parser["request_cookies"] == REDACTED
    assert parser["selectors"] == {"price": "span.price"}
