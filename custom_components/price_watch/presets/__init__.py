"""Retailer presets for Price Watch.

A preset is a small module that recognizes a retailer's URL pattern and
either:
- generates a custom_parser config (if the retailer needs API-style fetching), and/or
- normalizes the URL (e.g. strips tracking params, canonicalizes shape)

so users don't have to paste JSON for well-known sites.

Each preset module exports:
    NAME: str            - human-readable name ("Tölvutek")
    DOMAINS: tuple       - hostnames it handles (("tolvutek.is",))
    matches(url) -> bool - True if this preset can handle the URL
    build_parser(url)    - dict | None: the custom_parser config, or None
                           if the standard JSON-LD path will work fine
    normalize_url(url)   - str | None: canonical URL, or None to leave
                           the URL unchanged. Optional - presets that
                           don't define this will be treated as "no
                           normalization needed".

Adding a new retailer = one new file in this directory + an import below.
No changes to the integration core needed.
"""

from __future__ import annotations

import logging
from typing import Any

from . import amazon, tolvutek

_LOGGER = logging.getLogger(__name__)

# Order matters only for overlapping domains - more specific first
PRESETS = [tolvutek, amazon]


def find_preset(url: str) -> Any | None:
    """Return the first preset whose pattern matches this URL, or None."""
    for preset in PRESETS:
        try:
            if preset.matches(url):
                return preset
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Preset %s matches() raised", getattr(preset, "NAME", preset))
    return None


def all_presets() -> list[Any]:
    """Return the list of all registered presets."""
    return list(PRESETS)


def normalize_url(preset: Any, url: str) -> str:
    """Return the preset's normalized URL, or the input URL unchanged.

    Presets that don't implement normalize_url() — or that return None —
    pass through the original URL.
    """
    fn = getattr(preset, "normalize_url", None)
    if fn is None:
        return url
    try:
        result = fn(url)
        return result if result else url
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Preset %s normalize_url raised", getattr(preset, "NAME", preset))
        return url
