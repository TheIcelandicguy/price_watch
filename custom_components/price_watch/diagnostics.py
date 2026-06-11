"""Diagnostics for Price Watch.

Gives testers a one-click "Download diagnostics" on the integration entry that
produces a redacted JSON snapshot — the config, the resolved mode, and the last
extraction result/error per listing — to attach to a bug report. Secrets (API
key, request cookies, auth headers) are stripped automatically.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ENTRY_TYPE_SETTINGS

# Keys redacted anywhere they appear (async_redact_data recurses dicts + lists,
# so this also covers cookies/keys nested inside options.listings[].custom_parser).
TO_REDACT = {
    "api_key",
    "request_cookies",
    "extra_headers",
    "cookie",
    "Cookie",
}


def _safe_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _summarize_parser(parser: Any) -> dict[str, Any] | None:
    """A debuggable view of a custom_parser with cookies stripped.

    Selectors/transforms/type/url/min_price are kept (they're useful and not
    secret); request_cookies is dropped and reduced to a boolean flag.
    """
    if not isinstance(parser, dict):
        return None
    safe = {k: v for k, v in parser.items() if k != "request_cookies"}
    safe["has_cookies"] = bool(parser.get("request_cookies"))
    return safe


def _result_summary(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "price": getattr(result, "price", None),
        "currency": getattr(result, "currency", None),
        "method": getattr(result, "method", None),
        "in_stock": getattr(result, "in_stock", None),
        "stock_count": getattr(result, "stock_count", None),
        "retailer": getattr(result, "retailer", None),
        "title": getattr(result, "title", None),
        "discontinued": getattr(result, "discontinued", None),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a Price Watch config entry."""
    out: dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "type": entry.data.get("entry_type"),
            "version": entry.version,
            "source": entry.source,
        },
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
    }

    # The settings entry has no coordinator — its config (provider, excluded
    # domains, offer links) is already in data/options above.
    if entry.data.get("entry_type") == ENTRY_TYPE_SETTINGS:
        return out

    coord = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coord is None or not hasattr(coord, "listing_ids"):
        out["coordinator"] = "not loaded"
        return out

    out["coordinator"] = {
        "last_update_success": getattr(coord, "last_update_success", None),
        "last_exception": _safe_str(getattr(coord, "last_exception", None)),
        "home_currency": getattr(coord, "home_currency", None),
        "primary_listing_id": getattr(coord, "primary_listing_id", None),
    }

    listings: list[dict[str, Any]] = []
    for lid in coord.listing_ids:
        cfg = coord.get_listing_config(lid) or {}
        state = coord.get_listing_state(lid) or {}
        listings.append(
            {
                "listing_id": lid,
                "is_primary": lid == coord.primary_listing_id,
                "config": {
                    "url": cfg.get("url"),
                    "retailer": cfg.get("retailer"),
                    "currency": cfg.get("currency"),
                    "variant_options": cfg.get("variant_options"),
                    "unit_quantity": cfg.get("unit_quantity"),
                    "unit_label": cfg.get("unit_label"),
                    "custom_parser": _summarize_parser(cfg.get("custom_parser")),
                },
                "last_check": state.get("last_check"),
                "lowest": state.get("lowest"),
                "history_points": len(state.get("history") or []),
                "result": _result_summary(coord.get_listing_result(lid)),
            }
        )
    out["listings"] = listings
    return out
