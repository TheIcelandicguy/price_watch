"""Cookie normalization shared across the integration.

Cookies for anti-bot bypass are accepted in three shapes everywhere they're
entered (config flow, services, panel, websocket test):

  - a Cookie-header string: ``"a=1; b=2"`` (what DevTools copy-paste / the
    panel produce),
  - a ``{name: value}`` mapping,
  - a list of cookie dicts ``[{"name": .., "value": ..}, ...]`` (the shape
    documented in services.yaml and produced by browser cookie APIs).

They are stored canonically as a header string inside
``custom_parser.request_cookies`` — the one place the extractor reads them —
and converted to a ``{name: value}`` dict for the HTTP client at fetch time.

Both directions live here so the str/dict/list handling has a single home;
previously the same logic was reimplemented in ``__init__``, ``extractor``
and ``config_flow`` and drifted independently.
"""

from __future__ import annotations

from typing import Any


def to_header_str(value: Any) -> str:
    """Normalize any accepted cookie shape to a ``"a=1; b=2"`` header string.

    Returns ``""`` for empty or unrecognized input (which callers treat as
    "no cookies" / "clear cookies").
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items() if v is not None)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                val = item.get("value")
                if name is not None and val is not None:
                    parts.append(f"{name}={val}")
        return "; ".join(parts)
    return ""


def to_dict(value: Any) -> dict[str, str] | None:
    """Normalize any accepted cookie shape to a ``{name: value}`` dict for the
    HTTP client, or ``None`` when empty / unrecognized.

    Supports the DevTools copy-paste header form, a JSON dict form, and the
    list-of-cookie-dicts form.
    """
    if not value:
        return None
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                val = item.get("value")
                if name is not None and val is not None:
                    result[str(name)] = str(val)
        return result or None
    if isinstance(value, str):
        result = {}
        for pair in value.split(";"):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            name, _, val = pair.partition("=")
            name = name.strip()
            if name:
                result[name] = val.strip()
        return result or None
    return None
