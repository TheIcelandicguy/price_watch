"""Home-currency (FX) conversion mixin for PriceWatchCoordinator.

Extracted from coordinator.py. Computes ``price_local`` — the tracked
price converted into the user's configured home currency — using the
shared FxRates cache (fx.py). Self-contained: reads the current
ExtractionResult's price/currency and the home currency from the settings
entry, writes ``self._price_local`` (consumed by the price_local sensor).

Failure is always non-fatal: price_local stays None and the sensor reports
unavailable rather than blocking the rest of the price fetch.

All attributes referenced via ``self`` (hass, _fx, _price_local) are
defined on the concrete PriceWatchCoordinator; the TYPE_CHECKING block
documents the contract without creating an import cycle.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import CONF_HOME_CURRENCY, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .extractor import ExtractionResult
    from .fx import FxRates

_LOGGER = logging.getLogger(__name__)


class FxMixin:
    """price_local / home-currency conversion for PriceWatchCoordinator."""

    if TYPE_CHECKING:
        hass: HomeAssistant
        _fx: FxRates
        _price_local: float | None

    async def _update_price_local(self, result: ExtractionResult) -> None:
        """Compute price_local from the current result, if home_currency is set.

        Failure is non-fatal: price_local stays None, sensor reports unavailable.
        Called both on a fresh fetch AND on the UNCHANGED short-circuit so that
        adding/changing home_currency in settings options takes effect on the
        next coordinator tick without needing the source page to change.
        """
        home = self.home_currency
        if not home:
            _LOGGER.info(
                "price_local: no home_currency configured (set one in "
                "Settings -> Devices & Services -> Price Watch -> Configure)"
            )
            self._price_local = None
            return
        if not result or not result.currency:
            _LOGGER.warning(
                "price_local: no source currency available on result, skipping"
            )
            self._price_local = None
            return
        src = result.currency.upper()
        dst = home.upper()
        if src == dst:
            _LOGGER.debug("price_local: %s == %s, no conversion needed", src, dst)
            self._price_local = result.price
            return
        try:
            converted = await self._fx.convert(result.price, src, dst)
            if converted is None:
                _LOGGER.warning(
                    "price_local: FX conversion %s->%s returned None "
                    "(see earlier FX log lines for the cause)",
                    src, dst,
                )
            else:
                _LOGGER.debug(
                    "price_local: %s %s -> %s %s", result.price, src, converted, dst
                )
            self._price_local = converted
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("price_local: FX conversion threw: %s", err)
            self._price_local = None

    @property
    def home_currency(self) -> str | None:
        """User's home currency from settings entry, if configured.

        Looked up fresh on every access so changing it in settings options
        takes effect on next update without reload.
        """
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == "settings":
                value = entry.options.get(
                    CONF_HOME_CURRENCY, entry.data.get(CONF_HOME_CURRENCY)
                )
                return (value or "").upper() or None
        return None

    @property
    def price_local(self) -> float | None:
        """Price in user's home currency, if conversion succeeded."""
        return self._price_local
