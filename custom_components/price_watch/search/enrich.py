"""Price/image backfill for search results via JSON-LD and meta tags.

Split out of coordinator_alternatives.py so the panel's live "Search &
add" websocket path can price its candidates the same way the
coordinator prices tracked products' alternatives.

Imports the extractor at module level. That is safe in this direction —
extractor.py imports nothing from the search package.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..extractor import fetch_html, find_meta_image, find_meta_price, try_jsonld
from .base import Alternative

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Max concurrent listing fetches when enriching DDG hits with prices via
# JSON-LD. Bounded so a search doesn't open a dozen sockets at once.
_ENRICH_CONCURRENCY = 4


async def enrich_alternatives_via_jsonld(
    hass: HomeAssistant, alternatives: list[Alternative]
) -> None:
    """Backfill price/currency/image on alternatives via JSON-LD + meta tags.

    For each listing missing a price or image, fetch the page (curl_cffi Chrome
    impersonation, same as the tracker) and read a price from JSON-LD first,
    then Open Graph / microdata meta tags. Listings that already have both a
    price and an image are skipped (no fetch). A page that fails to fetch or has
    no usable price simply keeps price=None. Never overrides a price the AI
    already supplied. Fetches run concurrently under a small semaphore.

    Module-level (not just a coordinator method) so the live "Search & add"
    websocket path can price its candidates too, not only tracked products.
    """
    if not alternatives:
        return

    session = async_get_clientsession(hass)
    sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def _enrich_one(alt: Alternative) -> None:
        if alt.price is not None and alt.image_url:
            return
        async with sem:
            try:
                html = await fetch_html(alt.url, session=session)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("alt enrich: fetch failed for %s: %s", alt.url, err)
                return
            try:
                jsonld = try_jsonld(html, url=alt.url)
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "alt enrich: JSON-LD parse failed for %s", alt.url, exc_info=True
                )
                jsonld = None

            if alt.price is None and jsonld and jsonld.get("price"):
                alt.price = jsonld["price"]
                if jsonld.get("currency"):
                    alt.currency = jsonld["currency"]
                if jsonld.get("title"):
                    alt.title = jsonld["title"]
            # Meta/microdata fallback when JSON-LD has no price.
            if alt.price is None:
                meta_price, meta_currency = find_meta_price(html)
                if meta_price is not None:
                    alt.price = meta_price
                    if meta_currency and not alt.currency:
                        alt.currency = meta_currency
            image = (jsonld or {}).get("image_url") or find_meta_image(html)
            if image and not alt.image_url:
                alt.image_url = image

    await asyncio.gather(
        *(_enrich_one(alt) for alt in alternatives),
        return_exceptions=True,
    )
