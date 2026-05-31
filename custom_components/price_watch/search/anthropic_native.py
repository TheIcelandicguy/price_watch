"""Anthropic native web-search search provider.

Uses Claude's built-in `web_search_20250305` tool. One API call, one
round trip: we send the alternatives prompt + the product details +
the `web_search` tool definition, Anthropic's servers execute the
search internally, Claude synthesizes structured results, returns to
us.

Cost model (as of 2026-01):
- Web search: $10 per 1000 searches (Anthropic-side billing)
- Tokens: standard model rate (input + output)
- Typical alternatives call: 1 search + ~3-5k tokens
  → ~$0.01 + ~$0.005 = ~$0.015 per call with Haiku
  → ~$0.01 + ~$0.045 = ~$0.055 per call with Sonnet

Implementation notes:
- We use a function-calling tool (report_alternatives) alongside
  web_search. Claude is instructed to use web_search to find matches
  AND THEN use report_alternatives to return them in our schema.
- max_uses=3 caps how many search rounds Claude can do — usually 1-2
  is plenty for "find alternatives to <product>".
- We DON'T use Anthropic's `extended_thinking` block — adds cost
  without measurable benefit for this task.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic, AuthenticationError, BadRequestError

from ..const import DEFAULT_MODEL
from .base import (
    ALTERNATIVES_SYSTEM_PROMPT,
    ALTERNATIVES_TOOL_SCHEMA,
    DISCOVERY_SYSTEM_PROMPT,
    Alternative,
    SearchProviderAuthError,
    SearchProviderError,
    SearchProviderUnavailable,
    SearchQuery,
)

_LOGGER = logging.getLogger(__name__)

# Anthropic's web_search tool identifier. Update when Anthropic ships
# a newer version of the tool (they version their server-side tools
# with date-coded type names, e.g. web_search_20250305).
WEB_SEARCH_TOOL_TYPE = "web_search_20250305"

# Cap on how many separate search rounds Claude can make per call.
# 1-2 is enough for the alternatives task; 3 is a safety upper bound.
WEB_SEARCH_MAX_USES = 3


class AnthropicNativeSearchProvider:
    """Search provider using Anthropic's native web_search tool."""

    name = "anthropic_native"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("AnthropicNativeSearchProvider requires an api_key")
        self._api_key = api_key
        self.model = model
        # Lazy-init the SDK client. AsyncAnthropic() loads SSL CA certs
        # synchronously in __init__ which HA's event-loop guard flags.
        # Defer to first use inside async_find_alternatives, where we
        # can use hass.async_add_executor_job if needed.
        self._client: AsyncAnthropic | None = None

    async def _ensure_client(self) -> AsyncAnthropic:
        if self._client is None:
            # AsyncAnthropic() does blocking file I/O during __init__
            # (cert load). Build it inline and accept the one-time
            # warning — subsequent calls are non-blocking. If this
            # becomes a problem we can wrap in run_in_executor.
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def find_alternatives(self, query: SearchQuery) -> list[Alternative]:
        """Run Claude with web_search + report_alternatives tools."""
        client = await self._ensure_client()

        user_prompt = self._build_user_prompt(query)

        # Anthropic's tool config is a list of two distinct tool types:
        # the server-side web_search tool and our function-calling tool
        # for structured output. Claude is expected to call web_search
        # first (Anthropic executes it server-side, returns results),
        # then call report_alternatives with the synthesized matches.
        tools: list[dict[str, Any]] = [
            {
                "type": WEB_SEARCH_TOOL_TYPE,
                "name": "web_search",
                "max_uses": WEB_SEARCH_MAX_USES,
            },
            {
                "name": ALTERNATIVES_TOOL_SCHEMA["name"],
                "description": ALTERNATIVES_TOOL_SCHEMA["description"],
                "input_schema": ALTERNATIVES_TOOL_SCHEMA["parameters"],
            },
        ]

        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=(
                    DISCOVERY_SYSTEM_PROMPT
                    if query.discovery
                    else ALTERNATIVES_SYSTEM_PROMPT
                ),
                tools=tools,
                # tool_choice forces Claude to actually use a tool. We
                # don't pin it to a specific tool because Claude needs
                # to use web_search FIRST and then report_alternatives.
                # Letting tool_choice="any" means Claude orchestrates
                # the two-step itself.
                tool_choice={"type": "any"},
                messages=[{"role": "user", "content": user_prompt}],
            )
        except AuthenticationError as err:
            raise SearchProviderAuthError(
                f"Anthropic auth rejected: {err}"
            ) from err
        except BadRequestError as err:
            # Most common BadRequest here is "credit balance too low"
            # — we want callers to recognize this as recoverable
            # (user tops up, retries) rather than a logic bug.
            msg = str(err).lower()
            if "credit balance" in msg or "billing" in msg:
                raise SearchProviderUnavailable(
                    "Anthropic credit balance too low — top up at "
                    "https://console.anthropic.com/billing"
                ) from err
            raise SearchProviderError(f"Anthropic bad request: {err}") from err
        except Exception as err:  # noqa: BLE001
            # Network errors, timeouts, anything unexpected. Surface
            # as generic provider error.
            raise SearchProviderError(f"Anthropic call failed: {err}") from err

        # Pull the report_alternatives tool_use block out of the
        # response content. Claude's response contains a mix of text,
        # tool_use, and server_tool_use blocks; we only care about the
        # report_alternatives tool call.
        for block in response.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == ALTERNATIVES_TOOL_SCHEMA["name"]
            ):
                payload = getattr(block, "input", {}) or {}
                alternatives = self._parse_alternatives(payload, query.max_results)
                # Apply the region heuristic last (overrides AI's guess
                # for known retailer/region pairs). No-op when
                # query.user_region is empty.
                if query.user_region:
                    from .region_heuristic import apply_to_alternative
                    for alt in alternatives:
                        apply_to_alternative(alt, query.user_region)
                return alternatives

        # No tool_use block found — log everything we got for debugging.
        block_types = [getattr(b, "type", "?") for b in response.content]
        _LOGGER.warning(
            "Anthropic returned no report_alternatives tool call. "
            "Blocks: %s. Stop reason: %s",
            block_types,
            response.stop_reason,
        )
        return []

    @staticmethod
    def _build_user_prompt(query: SearchQuery) -> str:
        """Compose the user message from the SearchQuery.

        Stays a string (not a structured message) so Claude treats
        the product description as a search target rather than as
        instructions. Includes the price/currency context so Claude
        can prefer cheaper alternatives.

        In discovery mode (`query.discovery`), `title` is a free-text
        search query rather than a known product, so the prompt is
        framed as an open shopping search.
        """
        if query.discovery:
            bits = [f"Search query: {query.title}"]
            if query.region and query.region != "worldwide":
                bits.append(f"Regional preference: {query.region}")
            if query.user_region:
                bits.append(
                    f"User's country code (ISO 3166-1 alpha-2): {query.user_region}. "
                    "For each result, set ships_to_user_region based on whether the "
                    "retailer ships physical goods to this country. Use null when "
                    "genuinely uncertain - do not guess."
                )
            bits.append(
                f"\nUse web_search to find up to {query.max_results} real, "
                "currently-purchasable product listings matching this search. "
                "Then call report_alternatives with your findings."
            )
            return "\n".join(bits)

        bits = [f"Product: {query.title}"]
        if query.current_price is not None and query.currency:
            bits.append(
                f"Currently tracked at: {query.current_price} {query.currency} "
                f"({query.retailer or 'unknown retailer'})"
            )
        elif query.current_price is not None:
            bits.append(f"Currently tracked at: {query.current_price}")

        if query.region and query.region != "worldwide":
            bits.append(f"Regional preference: {query.region}")

        if query.user_region:
            bits.append(
                f"User's country code (ISO 3166-1 alpha-2): {query.user_region}. "
                "For each alternative, set ships_to_user_region based on whether "
                "the retailer ships physical goods to this country. Use null when "
                "genuinely uncertain - do not guess."
            )

        bits.append(
            f"\nUse web_search to find up to {query.max_results} alternative "
            "listings for this exact product. Prefer matches at lower "
            "prices than the current tracked price. Then call "
            "report_alternatives with your findings."
        )
        return "\n".join(bits)

    @staticmethod
    def _parse_alternatives(
        payload: dict[str, Any], max_results: int
    ) -> list[Alternative]:
        """Convert the tool_use input dict into Alternative objects.

        Defensive against the AI returning extra fields, missing
        fields, or values of the wrong type. We accept anything that
        has title+url and skip rows that don't.
        """
        items_raw = payload.get("alternatives", [])
        if not isinstance(items_raw, list):
            _LOGGER.warning(
                "Anthropic returned non-list for alternatives: %r",
                type(items_raw),
            )
            return []

        out: list[Alternative] = []
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue

            # Coerce numeric fields carefully. The AI sometimes returns
            # price as a string with a currency symbol; ignore those.
            price_raw = item.get("price")
            price: float | None
            if price_raw is None:
                price = None
            else:
                try:
                    price = float(price_raw)
                except (TypeError, ValueError):
                    price = None

            conf_raw = item.get("confidence", 0.0)
            try:
                confidence = max(0.0, min(1.0, float(conf_raw)))
            except (TypeError, ValueError):
                confidence = 0.0

            ships_raw = item.get("ships_to_user_region")
            ships: bool | None
            if ships_raw is None:
                ships = None
            elif isinstance(ships_raw, bool):
                ships = ships_raw
            elif isinstance(ships_raw, str):
                s = ships_raw.strip().lower()
                if s in ("true", "yes", "1"):
                    ships = True
                elif s in ("false", "no", "0"):
                    ships = False
                else:
                    ships = None
            else:
                ships = None

            out.append(
                Alternative(
                    title=title,
                    url=url,
                    price=price,
                    currency=str(item.get("currency", "") or ""),
                    retailer=str(item.get("retailer", "") or ""),
                    image_url=item.get("image_url"),
                    confidence=confidence,
                    notes=str(item.get("notes", "") or ""),
                    ships_to_user_region=ships,
                )
            )
            if len(out) >= max_results:
                break

        # Sort by confidence DESC then price ASC. The coordinator and
        # panel can re-sort but this is the sensible default.
        out.sort(
            key=lambda a: (
                -a.confidence,
                a.price if a.price is not None else float("inf"),
            )
        )
        return out

    async def aclose(self) -> None:
        """Close the underlying AsyncAnthropic client, if built."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error closing AsyncAnthropic client", exc_info=True)
            self._client = None
