"""OpenAI-compatible AI provider.

Single implementation that covers any service speaking OpenAI's API:
- OpenAI itself (https://api.openai.com/v1)
- Ollama with OpenAI compat shim (http://localhost:11434/v1)
- Groq (https://api.groq.com/openai/v1)
- OpenRouter (https://openrouter.ai/api/v1)
- LM Studio (http://localhost:1234/v1)
- Together, Fireworks, Anyscale, Mistral, DeepInfra, and many more

Function calling (tools) is the primary extraction path. If a particular
endpoint doesn't support it — most modern ones do, but older Ollama
versions and some open-weight servers don't — pass force_json_mode=True
and we'll fall back to `response_format: {"type": "json_object"}`.
That's less reliable (the model may produce extra prose or omit
required fields) but is supported almost everywhere.

Pricing is user-supplied at construction time because there's no way
for us to know what an OpenRouter `qwen-3:235b` call costs without a
database we'd have to keep up to date. Pass input_cost_per_mtok and
output_cost_per_mtok in dollars per million tokens; leave at 0.0 for
local / free services like Ollama. We report whatever you tell us.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

# openai package is loaded via manifest.json requirements
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError as OpenAIAuthenticationError,
)

from .base import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_TOOL_SCHEMA,
    AIAuthenticationError,
    AIExtractionResult,
    AIProviderError,
)

_LOGGER = logging.getLogger(__name__)


# Default character budget for HTML sent to the model. Sized to fit in
# ~25K tokens, which is comfortable for 32K-context models and trivial
# for the 128K+ models. Users with smaller-context local models can
# override via max_html_chars.
DEFAULT_MAX_HTML_CHARS = 100_000

# A "no key" sentinel for local servers (Ollama, LM Studio) that don't
# care about auth but openai SDK requires *something* non-empty for the
# api_key parameter. The string itself is meaningless.
LOCAL_NO_KEY_SENTINEL = "ollama"


def _trim_html(cleaned_html: str, max_chars: int) -> str:
    """Trim HTML aggressively, keeping head + start of body.

    Identical strategy to the Anthropic provider's _trim_html. Kept as
    a separate function (not shared) because if/when providers want
    different trimming heuristics, they shouldn't have to refactor a
    shared helper.
    """
    if len(cleaned_html) <= max_chars:
        return cleaned_html

    head_end_marker = "</head>"
    head_end = cleaned_html.find(head_end_marker)
    if head_end > 0:
        head_end += len(head_end_marker)
        head = cleaned_html[:head_end]
        body_budget = max_chars - len(head) - 100  # safety margin
        if body_budget > 5000:
            body = cleaned_html[head_end : head_end + body_budget]
            return head + body
    return cleaned_html[:max_chars]


def _calc_cost(
    usage: Any, input_cost_per_mtok: float, output_cost_per_mtok: float
) -> float:
    """Compute USD cost from usage object + user-supplied rates.

    OpenAI's `usage` shape: usage.prompt_tokens, usage.completion_tokens
    (also usage.total_tokens but we don't need it). All compatible
    servers should return this shape; if a server omits usage entirely
    we return 0.0 rather than crashing.
    """
    if usage is None:
        return 0.0
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    return (
        (prompt / 1_000_000) * input_cost_per_mtok
        + (completion / 1_000_000) * output_cost_per_mtok
    )


class OpenAICompatProvider:
    """Generic OpenAI-API-compatible AI provider."""

    name = "openai_compatible"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str,
        input_cost_per_mtok: float = 0.0,
        output_cost_per_mtok: float = 0.0,
        max_html_chars: int = DEFAULT_MAX_HTML_CHARS,
        force_json_mode: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not model:
            raise ValueError("OpenAICompatProvider requires a model name")
        if not base_url:
            raise ValueError(
                "OpenAICompatProvider requires a base_url "
                "(e.g. https://api.openai.com/v1)"
            )

        self.model = model
        self._base_url = base_url.rstrip("/")
        # Local servers like Ollama don't require auth but the OpenAI SDK
        # asserts on empty api_key. Fall back to a harmless sentinel.
        self._api_key = api_key or LOCAL_NO_KEY_SENTINEL
        self._input_cost = float(input_cost_per_mtok)
        self._output_cost = float(output_cost_per_mtok)
        self._max_html_chars = int(max_html_chars or DEFAULT_MAX_HTML_CHARS)
        self._force_json_mode = bool(force_json_mode)
        self._extra_headers = dict(extra_headers) if extra_headers else None

        # Lazy-init the client to avoid blocking the event loop on SSL
        # cert load during coordinator setup. Same pattern as the
        # Anthropic provider.
        self._client: AsyncOpenAI | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                loop = asyncio.get_running_loop()
                kwargs: dict[str, Any] = {
                    "api_key": self._api_key,
                    "base_url": self._base_url,
                }
                if self._extra_headers:
                    kwargs["default_headers"] = self._extra_headers
                self._client = await loop.run_in_executor(
                    None, lambda: AsyncOpenAI(**kwargs)
                )
        return self._client

    def _build_messages(self, cleaned_html: str) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract product info from this HTML:\n\n{cleaned_html}"
                ),
            },
        ]

    def _openai_tool_def(self) -> dict[str, Any]:
        """Translate the shared tool schema into OpenAI's `tools` shape."""
        return {
            "type": "function",
            "function": {
                "name": EXTRACTION_TOOL_SCHEMA["name"],
                "description": EXTRACTION_TOOL_SCHEMA["description"],
                "parameters": EXTRACTION_TOOL_SCHEMA["parameters"],
            },
        }

    async def extract_product(self, cleaned_html: str) -> AIExtractionResult:
        trimmed = _trim_html(cleaned_html, self._max_html_chars)
        if len(trimmed) < len(cleaned_html):
            _LOGGER.debug(
                "Trimmed HTML for %s: %d -> %d chars",
                self.model, len(cleaned_html), len(trimmed),
            )

        client = await self._get_client()
        messages = self._build_messages(trimmed)

        try:
            if self._force_json_mode:
                # JSON-mode path: less reliable than tool calls but
                # universally supported. The model returns a JSON object
                # we parse out of `message.content`.
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                EXTRACTION_SYSTEM_PROMPT
                                + "\n\nRespond with a JSON object matching this "
                                + "schema (top-level keys, no wrapper): "
                                + json.dumps(EXTRACTION_TOOL_SCHEMA["parameters"])
                            ),
                        },
                        messages[1],
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=512,
                )
                data = self._extract_from_json_mode(response)
            else:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=[self._openai_tool_def()],
                    tool_choice={
                        "type": "function",
                        "function": {"name": EXTRACTION_TOOL_SCHEMA["name"]},
                    },
                    max_tokens=512,
                )
                data = self._extract_from_tool_call(response)
        except OpenAIAuthenticationError as err:
            raise AIAuthenticationError(
                f"{self._base_url} rejected the API key: {err}"
            ) from err
        except APIConnectionError as err:
            raise AIProviderError(
                f"Could not reach {self._base_url}: {err}"
            ) from err
        except APIStatusError as err:
            # 4xx/5xx that aren't auth: rate limits, model not found,
            # context overflow, server errors, etc. Surface the status
            # code and any message so the user can diagnose.
            raise AIProviderError(
                f"{self._base_url} returned HTTP {err.status_code}: "
                f"{err.message or str(err)}"
            ) from err
        except APIError as err:
            raise AIProviderError(
                f"OpenAI-compat call failed: {type(err).__name__}: {err}"
            ) from err
        except Exception as err:
            raise AIProviderError(
                f"Unexpected error from {self._base_url}: "
                f"{type(err).__name__}: {err}"
            ) from err

        cost = _calc_cost(
            getattr(response, "usage", None),
            self._input_cost,
            self._output_cost,
        )

        usage = getattr(response, "usage", None)
        raw_usage = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
        }

        return AIExtractionResult(
            data=data,
            cost_usd=cost,
            model=self.model,
            raw_usage=raw_usage,
        )

    @staticmethod
    def _extract_from_tool_call(response: Any) -> dict[str, Any]:
        """Pull the tool-call arguments out of an OpenAI response.

        Shape:
          response.choices[0].message.tool_calls[0].function.arguments
        where `arguments` is a JSON string we need to parse.
        """
        try:
            choice = response.choices[0]
            tool_calls = choice.message.tool_calls or []
            if not tool_calls:
                raise AIProviderError(
                    "Model did not call the report_product tool "
                    "(empty tool_calls list)"
                )
            call = tool_calls[0]
            args = call.function.arguments
            if isinstance(args, str):
                return json.loads(args)
            if isinstance(args, dict):
                return args
            raise AIProviderError(
                f"Tool call arguments had unexpected type: {type(args).__name__}"
            )
        except (AttributeError, IndexError, json.JSONDecodeError) as err:
            raise AIProviderError(
                f"Could not parse tool call from response: "
                f"{type(err).__name__}: {err}"
            ) from err

    @staticmethod
    def _extract_from_json_mode(response: Any) -> dict[str, Any]:
        """Pull JSON out of a JSON-mode response (when tools aren't
        used).

        Shape:
          response.choices[0].message.content
        which should be a valid JSON object string.
        """
        try:
            content = response.choices[0].message.content or ""
            # Strip code fences in case the model wrapped JSON anyway.
            content = content.strip()
            if content.startswith("```"):
                content = content.lstrip("`")
                if content.lower().startswith("json"):
                    content = content[4:]
                content = content.strip("` \n")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise AIProviderError(
                    f"JSON-mode response was not an object "
                    f"(got {type(parsed).__name__})"
                )
            return parsed
        except (AttributeError, IndexError, json.JSONDecodeError) as err:
            raise AIProviderError(
                f"Could not parse JSON-mode response: "
                f"{type(err).__name__}: {err}"
            ) from err

    async def validate_credentials(self) -> None:
        """Send a tiny ping to confirm endpoint+key+model are valid.

        Uses the cheapest possible call: max_tokens=1, no tools, no
        JSON mode. Local servers like Ollama return immediately; hosted
        services charge for ~1 token of input + 1 of output (fractions
        of a cent).
        """
        try:
            client = await self._get_client()
            await client.chat.completions.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
        except OpenAIAuthenticationError as err:
            raise AIAuthenticationError(str(err)) from err
        except APIConnectionError as err:
            raise AIProviderError(
                f"Could not reach {self._base_url}: {err}"
            ) from err
        except APIStatusError as err:
            raise AIProviderError(
                f"{self._base_url} returned HTTP {err.status_code}: "
                f"{err.message or str(err)}"
            ) from err
        except Exception as err:
            raise AIProviderError(
                f"Validation request failed: {type(err).__name__}: {err}"
            ) from err

    async def call_with_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Generic one-shot tool/function call. Returns the tool input dict.

        Used by the search/alternatives subsystem to invoke any
        OpenAI-compatible endpoint (Ollama, OpenAI, OpenRouter, etc.)
        with a custom prompt + tool, separate from the extraction
        path.

        Honors self._force_json_mode: when True, falls back to JSON
        mode (response_format) instead of native function calling.
        Many older Ollama versions and some open-weight servers
        don't support OpenAI tool calling but do support
        response_format={"type":"json_object"}.

        Raises AIProviderError / AIAuthenticationError on failure.
        Caller should treat these as recoverable (try a different
        provider) rather than logic bugs.
        """
        client = await self._get_client()

        try:
            if self._force_json_mode:
                # JSON-mode fallback: ask for JSON and parse from
                # message.content. The schema goes into the system
                # prompt as documentation; we can't enforce it
                # server-side without function calling.
                system_with_schema = (
                    system_prompt
                    + "\n\nRespond with a JSON object matching this "
                    + "schema (top-level keys, no wrapper): "
                    + json.dumps(tool_schema["parameters"])
                )
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_with_schema},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                )
                content = (
                    response.choices[0].message.content
                    if response.choices
                    else ""
                ) or ""
                try:
                    return json.loads(content)
                except json.JSONDecodeError as err:
                    raise AIProviderError(
                        f"JSON-mode response was not valid JSON: {err}. "
                        f"Body preview: {content[:200]!r}"
                    ) from err
            else:
                # Native function-calling path.
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool_schema["name"],
                        "description": tool_schema.get("description", ""),
                        "parameters": tool_schema["parameters"],
                    },
                }
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[openai_tool],
                    tool_choice={
                        "type": "function",
                        "function": {"name": tool_schema["name"]},
                    },
                    max_tokens=4096,
                )
                # Extract from the tool call arguments.
                if not response.choices:
                    raise AIProviderError("No choices in response")
                message = response.choices[0].message
                tool_calls = getattr(message, "tool_calls", None) or []
                for call in tool_calls:
                    fn = getattr(call, "function", None)
                    if (
                        fn
                        and getattr(fn, "name", None) == tool_schema["name"]
                    ):
                        try:
                            return json.loads(fn.arguments or "{}")
                        except json.JSONDecodeError as err:
                            raise AIProviderError(
                                f"Tool arguments not valid JSON: {err}"
                            ) from err
                raise AIProviderError(
                    f"Model did not return the {tool_schema['name']!r} tool call"
                )
        except OpenAIAuthenticationError as err:
            raise AIAuthenticationError(str(err)) from err
        except APIConnectionError as err:
            raise AIProviderError(
                f"Could not reach {self._base_url}: {err}"
            ) from err
        except APIStatusError as err:
            raise AIProviderError(
                f"{self._base_url} returned HTTP {err.status_code}: "
                f"{err.message or str(err)}"
            ) from err
        except AIProviderError:
            raise
        except Exception as err:  # noqa: BLE001
            raise AIProviderError(
                f"call_with_tool failed: {type(err).__name__}: {err}"
            ) from err
