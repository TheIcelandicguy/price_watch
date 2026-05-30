"""AI provider abstraction.

Defines the interface every AI backend implements (Anthropic, OpenAI-
compatible, Gemini, etc.). The rest of the integration only talks to
this interface — swapping providers does not require touching the
extractor, coordinator, or config flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# Shared extraction prompt. Lives here (not in any one provider) because
# all AI backends produce better results from the same instruction.
EXTRACTION_SYSTEM_PROMPT = """You are a product page extractor. Given the cleaned HTML of an e-commerce product page, return a JSON object with these fields:

- title: string — full product name
- price: number — current price as a number (no currency symbols, no thousands separators)
- currency: string — ISO 4217 code (e.g. "NOK", "ISK", "EUR", "USD") or symbol if code not detectable
- in_stock: boolean — whether the product is currently purchasable
- image_url: string or null — absolute URL to the main product image
- sku: string or null — SKU, model number, or product identifier
- retailer: string — display name of the retailer (e.g. "Komplett", "Proshop", "Amazon")
- stock_count: number or null — number of units in stock if shown. Null if only "in stock"/"out of stock" without a number.

CRITICAL: If the HTML does NOT contain an actual product (e.g. it's a CAPTCHA page, a "Continue shopping" interstitial, an error page, a blank page, a search-results listing, or a notice that the product is discontinued/no longer sold), DO NOT fabricate data. Instead:
- Set title to the literal string "NO_PRODUCT_FOUND"
- Set price to 0
- Set not_found_reason to a SHORT (≤ 15 word) phrase that says WHY the page is not a product page. Examples:
  - "Page says product is discontinued / no longer sold"
  - "Page is a CAPTCHA / bot-check"
  - "Page is a 'Continue shopping' interstitial"
  - "Page is a category or search-results listing, not a single product"
  - "Page is an error / 404 / empty"
  - "Page redirected to the homepage"
- Set is_discontinued to TRUE ONLY when the page clearly says the product is no longer sold (phrases like "discontinued", "no longer available", "ikke lenger i vårt sortiment", "no longer in our range", "permanently out of stock", "this item has been removed", "не выпускается"). Set FALSE for bot-checks, interstitials, errors, or any other "no product" reason where the product itself might still exist elsewhere.
- If the page still shows the product title clearly (e.g. on a "this product is discontinued" notice that still names the product), you MAY put the real title in the title field INSTEAD of "NO_PRODUCT_FOUND" — but ONLY when is_discontinued is true. This preserves the historical record.

The not_found_reason is shown directly to the user in the Home Assistant UI. Be specific about which condition you observed so they know what to do next (delete the entry, paste cookies, try again later, etc.).

Do not return placeholder values like "<UNKNOWN>" or "Unknown product" - that misleads users into thinking extraction worked."""


# JSON schema for the extraction tool/structured-output call.
# Each provider translates this into its native shape (Anthropic tool_use,
# OpenAI function calling, Gemini function declarations).
EXTRACTION_TOOL_SCHEMA: dict[str, Any] = {
    "name": "report_product",
    "description": "Report extracted product information.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "price": {"type": "number"},
            "currency": {"type": "string"},
            "in_stock": {"type": "boolean"},
            "stock_count": {"type": ["integer", "null"]},
            "image_url": {"type": ["string", "null"]},
            "sku": {"type": ["string", "null"]},
            "retailer": {"type": ["string", "null"]},
            "not_found_reason": {
                "type": ["string", "null"],
                "description": (
                    "When title is 'NO_PRODUCT_FOUND' or is_discontinued is "
                    "true, a short (≤15 word) phrase explaining why the "
                    "page is not a normal product page. Null otherwise."
                ),
            },
            "is_discontinued": {
                "type": "boolean",
                "description": (
                    "True ONLY when the page explicitly indicates the "
                    "product has been permanently removed from the "
                    "retailer's catalog (e.g. 'discontinued', 'no longer "
                    "in our range', 'this product has been removed'). "
                    "False for temporary stock issues, bot-checks, or "
                    "any condition where the product might still be sold."
                ),
            },
        },
        "required": ["title", "price", "currency", "in_stock"],
    },
}


class AIProviderError(Exception):
    """Raised by a provider when it can't satisfy the request.

    Distinct from ExtractionError because the extractor needs to tell
    "AI said nothing useful" apart from "AI itself failed" (network,
    auth, quota). Callers may catch this to surface provider-specific
    diagnostics or to fall back to a different provider.
    """


class AIAuthenticationError(AIProviderError):
    """Raised when credentials are rejected by the provider."""


@dataclass
class AIExtractionResult:
    """Provider-agnostic result of an extraction call.

    `data` carries the raw JSON the model returned; `cost_usd` is the
    provider's own cost estimate for the call (0.0 if the provider runs
    locally or doesn't bill per call); `model` is the actual model used
    (providers may have a default different from what was requested).
    """

    data: dict[str, Any]
    cost_usd: float = 0.0
    model: str = ""
    raw_usage: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AIProvider(Protocol):
    """Interface every AI backend implements.

    Implementations live in sibling modules. New providers added here are
    picked up by `get_provider()` automatically once registered.
    """

    name: str
    """Stable identifier for the provider type, e.g. "anthropic"."""

    model: str
    """Model identifier this provider instance is configured to use."""

    async def extract_product(
        self, cleaned_html: str
    ) -> AIExtractionResult:
        """Extract product info from cleaned HTML.

        Implementations should:
        - Send EXTRACTION_SYSTEM_PROMPT as the system message
        - Constrain output via tool use / function calling / JSON mode
        - Trim input HTML if the model's context window is small
        - Raise AIAuthenticationError on auth failure
        - Raise AIProviderError on any other failure
        - Never raise raw SDK exceptions (always wrap)
        """
        ...

    async def validate_credentials(self) -> None:
        """Ping the provider to confirm credentials work.

        Called from the config flow when the user enters/changes a key.
        Raises AIAuthenticationError on bad credentials, AIProviderError
        on other failures.
        """
        ...
