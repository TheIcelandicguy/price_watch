"""Anthropic (Claude) AI provider.

Lifts the previous `extract_with_claude` logic out of `extractor.py` and
behind the AIProvider interface. Behavior should be byte-for-byte
identical to the pre-refactor code: same model, same prompt, same tool
schema, same trimming threshold, same cost math.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from anthropic import AsyncAnthropic, AuthenticationError

from ..const import DEFAULT_MODEL
from .base import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_TOOL_SCHEMA,
    AIAuthenticationError,
    AIExtractionResult,
    AIProviderError,
)

_LOGGER = logging.getLogger(__name__)


# Per-million-token pricing. Kept here (not in const.py) so each provider
# owns its own cost table — when Anthropic prices change, only this file
# needs touching.
PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25,
    },
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75,
    },
    "claude-opus-4-7": {
        "input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25,
    },
}

# Max HTML chars before trimming. ~100K chars ≈ 25K tokens, leaving plenty
# of headroom under Claude's 200K context window for the system prompt
# and tool schema. Empirically, product page essentials fit in ~80K chars.
_MAX_HTML_FOR_CLAUDE = 100_000


def _trim_html(cleaned_html: str) -> str:
    """Trim HTML aggressively, keeping head + start of body.

    Big e-commerce pages ship ~1MB of HTML. Most of it is reviews,
    related products, navigation, footer chrome. Product title and price
    sit near the top of the body (above-the-fold content). Reviews,
    "you might also like", and footer come later.
    """
    if len(cleaned_html) <= _MAX_HTML_FOR_CLAUDE:
        return cleaned_html

    head_end_marker = "</head>"
    head_end = cleaned_html.find(head_end_marker)
    if head_end > 0:
        head_end += len(head_end_marker)
        head = cleaned_html[:head_end]
        body_budget = _MAX_HTML_FOR_CLAUDE - len(head) - 100  # safety margin
        if body_budget > 5000:
            body = cleaned_html[head_end : head_end + body_budget]
            return head + body
    return cleaned_html[:_MAX_HTML_FOR_CLAUDE]


def _calc_cost(model: str, usage: Any) -> float:
    """Calculate USD cost from an Anthropic usage object."""
    rates = PRICING_PER_MTOK.get(model, PRICING_PER_MTOK[DEFAULT_MODEL])
    cost = 0.0
    cost += (getattr(usage, "input_tokens", 0) / 1_000_000) * rates["input"]
    cost += (getattr(usage, "output_tokens", 0) / 1_000_000) * rates["output"]
    cost += (getattr(usage, "cache_read_input_tokens", 0) / 1_000_000) * rates["cache_read"]
    cost += (getattr(usage, "cache_creation_input_tokens", 0) / 1_000_000) * rates["cache_write"]
    return cost


class AnthropicProvider:
    """Claude implementation of AIProvider."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            # An AnthropicProvider with no key is useless; callers should
            # construct it conditionally rather than passing empty.
            raise ValueError("AnthropicProvider requires an api_key")
        self._api_key = api_key
        self.model = model
        # Lazy-init the SDK client. AsyncAnthropic(...) loads SSL CA
        # certs from disk in __init__, which is a blocking call. HA's
        # event-loop guard flags that with a "Detected blocking call"
        # warning if we do it during coordinator setup. Deferring to
        # first use means we can run the construction inside an
        # executor thread — the SSL load no longer blocks the loop.
        self._client: AsyncAnthropic | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> AsyncAnthropic:
        """Return the AsyncAnthropic client, lazily constructed in a
        thread so HA's event loop doesn't see the SSL cert load."""
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                loop = asyncio.get_running_loop()
                self._client = await loop.run_in_executor(
                    None, lambda: AsyncAnthropic(api_key=self._api_key)
                )
        return self._client

    async def extract_product(self, cleaned_html: str) -> AIExtractionResult:
        trimmed = _trim_html(cleaned_html)
        if len(trimmed) < len(cleaned_html):
            _LOGGER.debug(
                "Trimmed HTML for Claude: %d -> %d chars",
                len(cleaned_html), len(trimmed),
            )

        # Translate the shared tool schema into Anthropic's tool-use shape.
        # OpenAI uses `parameters`; Anthropic uses `input_schema`.
        anthropic_tool = {
            "name": EXTRACTION_TOOL_SCHEMA["name"],
            "description": EXTRACTION_TOOL_SCHEMA["description"],
            "input_schema": EXTRACTION_TOOL_SCHEMA["parameters"],
        }

        try:
            client = await self._get_client()
            response = await client.messages.create(
                model=self.model,
                max_tokens=512,
                system=[
                    {
                        "type": "text",
                        "text": EXTRACTION_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f"Extract product info from this HTML:\n\n{trimmed}",
                    }
                ],
                tools=[anthropic_tool],
                tool_choice={"type": "tool", "name": "report_product"},
            )
        except AuthenticationError as err:
            raise AIAuthenticationError(
                f"Anthropic rejected the API key: {err}"
            ) from err
        except Exception as err:
            raise AIProviderError(
                f"Anthropic call failed: {type(err).__name__}: {err}"
            ) from err

        cost = _calc_cost(self.model, response.usage)

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "report_product":
                return AIExtractionResult(
                    data=dict(block.input),
                    cost_usd=cost,
                    model=self.model,
                    raw_usage={
                        "input_tokens": getattr(response.usage, "input_tokens", 0),
                        "output_tokens": getattr(response.usage, "output_tokens", 0),
                        "cache_read_input_tokens": getattr(
                            response.usage, "cache_read_input_tokens", 0
                        ),
                        "cache_creation_input_tokens": getattr(
                            response.usage, "cache_creation_input_tokens", 0
                        ),
                    },
                )

        raise AIProviderError("Claude did not return structured product data")

    async def validate_credentials(self) -> None:
        """Send a 1-token ping to confirm the key works."""
        try:
            client = await self._get_client()
            await client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
        except AuthenticationError as err:
            raise AIAuthenticationError(str(err)) from err
        except Exception as err:
            raise AIProviderError(
                f"Validation request to Anthropic failed: "
                f"{type(err).__name__}: {err}"
            ) from err

    async def call_with_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Generic one-shot tool call. Returns the tool input dict.

        Used by the search/alternatives subsystem to invoke Claude
        with a custom prompt + tool, separate from the extraction
        path. The tool_schema is the shared OpenAI-style schema
        (with `parameters`); we translate to Anthropic's
        `input_schema` here just like extract_product does.

        No HTML trimming — caller is responsible for keeping the
        user_prompt within context window. No cost tracking here
        either; the alternatives subsystem doesn't currently bill
        per-call (rolled into lifetime_cost_usd via a separate
        update if we add that later).

        Raises AIProviderError / AIAuthenticationError just like
        extract_product.
        """
        anthropic_tool = {
            "name": tool_schema["name"],
            "description": tool_schema.get("description", ""),
            "input_schema": tool_schema["parameters"],
        }

        try:
            client = await self._get_client()
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[anthropic_tool],
                tool_choice={"type": "tool", "name": tool_schema["name"]},
            )
        except AuthenticationError as err:
            raise AIAuthenticationError(
                f"Anthropic rejected the API key: {err}"
            ) from err
        except Exception as err:  # noqa: BLE001
            raise AIProviderError(
                f"Anthropic call_with_tool failed: "
                f"{type(err).__name__}: {err}"
            ) from err

        for block in response.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == tool_schema["name"]
            ):
                return dict(block.input)

        raise AIProviderError(
            f"Claude did not return the {tool_schema['name']!r} tool call"
        )
