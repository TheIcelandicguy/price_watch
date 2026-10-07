# Retailer presets (verified against repo)

A **preset** makes a specific retailer "just work" out of the box — no AI, no manual selector — for sites the free JSON-LD path can't read (client-side prices, API-backed SPAs, cookie walls). Read this when adding coverage for a new shop, especially an Icelandic one.

Location: `custom_components/price_watch/presets/`. **Adding a retailer = one new file + one import line.** No changes to the integration core.

## How a preset is applied

The add path (`config_flow.py`, both the by-URL and by-name steps) calls `find_preset(url)` → `preset.build_parser(url)` and attaches the returned dict as the listing's `custom_parser`. So once a preset matches, adding that retailer's URL stores the right parser automatically. `find_preset` returns the first preset whose `matches(url)` is true (order in `PRESETS` matters only for overlapping domains — more specific first). Currently `PRESETS = [tolvutek, elko, rafland, amazon]`.

## Module interface

Each preset module in `presets/` exports:

```python
NAME: str                  # human-readable, e.g. "ELKO"
DOMAINS: tuple             # ("elko.is",) — informational
def matches(url) -> bool   # True if this preset handles the URL
def build_parser(url)      # dict (a custom_parser config) | None
def normalize_url(url)     # str | None — optional, canonicalize/strip tracking
```

Register it in `presets/__init__.py`: add to the `from . import …` line and the `PRESETS = [...]` list (specific before generic).

`build_parser` returns a normal `custom_parser` dict — same shape the panel's selector editor produces — so a preset is just a pre-baked parser keyed to a URL pattern. Supported `type`s: `css`, `regex`, `jsonpath`, `raw_json`. Useful keys: `selectors` (per field; a value may be a **list of patterns tried in priority order**), `transforms` (e.g. `price_clean`, `coalesce:_x|float`, `int`, `prefix:…`), `default_currency`, `default_retailer`, `min_price`/`max_price` (a match outside the bound raises `ParserError` → drops to AI fallback rather than committing a bad number), and for raw_json: `url`, `request_method`, `request_body`, `request_headers`.

`apply_custom_parser` (`parsers.py`) applies `default_currency`/`default_retailer` via `setdefault`, so a regex/css preset can stamp the currency even when the page markup omits it.

## The four existing presets

- **`tolvutek.py` (Tölvutek)** — `raw_json`. The product page is a Konakart SPA; the preset POSTs `{"prodId": …}` to `https://tolvutek.is/api//FetchProduct` (yes, the double slash is real) and reads `r.specialPriceIncTax` (falling back to `r.priceIncTax`), `r.name`, `r.quantity`, etc. `default_currency: ISK`.
- **`elko.py` (ELKO)** — `regex`. elko.is renders client-side with no Schema.org Product, but the current price sits in embedded page state as `"price": <n>`. The preset reads it with a regex (`"price"\s*:\s*"?([0-9]+(?:[.,][0-9]+)?)"?`) plus `og:title`/`og:image`, `default_currency: ISK`, `default_retailer: ELKO`, `min_price: 100` guard. Matches `elko.is/vorur/`.
- **`rafland.py` (Rafland)** — rafland.is is a headless Magento storefront; the preset queries its Roanuz GraphQL endpoint, filtered by the product's `url_key`. Tested in `tests/test_presets_rafland.py`.
- **`amazon.py`** — cookie/anti-bot handling for Amazon URLs.

## Adding a new preset (recipe)

1. Probe the page (curl_cffi `impersonate="chrome131"`): is the price in JSON-LD? a `<meta>` tag? embedded JSON (`"price":…`)? an XHR/API call? (If it's clean JSON-LD, you don't need a preset at all.)
2. Pick the parser `type` that targets it (regex for embedded JSON, raw_json for an API, css for a stable element).
3. Write `presets/<name>.py` with `matches`/`build_parser`; set `default_currency`/`default_retailer` and a `min_price` guard.
4. Register in `presets/__init__.py`.
5. Add a unit test (see `tests/test_presets_elko.py` or `tests/test_presets_rafland.py` — assert `matches()`, `find_preset()` picks it, and `apply_custom_parser()` on a small HTML fixture yields the price/title/currency).
6. `.\deploy.ps1` + **restart HA**, then add the URL and verify the price live.
