# Custom parsers

By default, Price Watch tries multiple extraction strategies (JSON-LD → og:image → Claude AI fallback if a key is set). For sites that don't ship structured data — particularly JS-rendered SPAs — a **custom parser** lets you fetch and extract from a different endpoint, usually the retailer's internal API.

Custom parsers run BEFORE everything else. You enter the parser as a JSON object in the integration's options (Settings → Devices & Services → Price Watch → device → Configure → custom_parser).

## Four parser types

### `raw_json` — POST to a JSON API

Best for SPAs whose backend exposes a JSON product endpoint. This is the path for Tölvutek, Komplett's mobile API, Origo, Konakart-based stores, BT Iceland, and similar.

```json
{
  "type": "raw_json",
  "url": "https://tolvutek.is/api//FetchProduct",
  "request_method": "POST",
  "request_body": "{\"prodId\": 39910, \"displayPricesWithTax\": true}",
  "request_headers": {"Content-Type": "application/json"},
  "selectors": {
    "title": "r.name",
    "price": "r.specialPriceIncTax",
    "stock_count": "r.quantity",
    "image_url": "r.image",
    "sku": "r.sku",
    "retailer": "r.manufacturerName"
  },
  "transforms": {
    "price": "coalesce:_priceFallback|float",
    "stock_count": "int",
    "image_url": "prefix:https://tolvutek.is"
  },
  "default_currency": "ISK",
  "default_retailer": "Tölvutek"
}
```

The `selectors` are dotted paths through the JSON tree (`r.specialPriceIncTax` → `data["r"]["specialPriceIncTax"]`).

### `css` — CSS selectors against HTML

```json
{
  "type": "css",
  "selectors": {
    "title": "h1.product-title",
    "price": ".price-current",
    "image_url": "img.product-hero@src"
  },
  "transforms": {"price": "regex:[^0-9.,]|replace:,:.|float"},
  "default_currency": "NOK"
}
```

Append `@attrname` to a CSS selector to extract an attribute instead of text content (e.g. `img@src`).

### `regex` — pattern with one capture group

```json
{
  "type": "regex",
  "selectors": {
    "title": "<meta property=\"og:title\" content=\"([^\"]+)\"",
    "price": "\"price\":\\s*([0-9.]+)"
  },
  "transforms": {"price": "float"}
}
```

### `jsonpath` — extract from `__NEXT_DATA__`-style JSON state

For Next.js / Nuxt / similar frameworks that embed initial state as JSON in a `<script>` tag.

```json
{
  "type": "jsonpath",
  "selectors": {
    "title": "__NEXT_DATA__:props.pageProps.product.name",
    "price": "__NEXT_DATA__:props.pageProps.product.price.amount"
  },
  "transforms": {"price": "float"}
}
```

## Request control (any parser type)

| Field | Purpose |
|---|---|
| `url` | Override the fetched URL. The product entry's URL stays as the user-facing link (shown in `product_url` attribute), but the integration fetches this instead. Useful for retailer APIs. |
| `request_method` | `GET` (default) or `POST`. |
| `request_body` | String body to send (POST only). For JSON APIs, set `Content-Type: application/json` in headers and the body to a JSON string. |
| `request_headers` | Dict of extra headers to merge with the default browser headers. |
| `request_cookies` | Cookie data: either a dict `{"name": "value"}` or a raw cookie-header string `"name1=val1; name2=val2"`. Useful for sites with hostile bot detection (Amazon) where you need to copy a real browser session's cookies. |

## Cookie injection workflow (Amazon and similar)

Some sites (most notably Amazon) bot-detect aggressively and serve a "Continue shopping" interstitial to fresh sessions, even with TLS impersonation. The workaround is to copy your real browser's cookies once, paste them into the parser config, and the integration will fetch as a "returning visitor".

**How to extract cookies from your browser:**

1. Open the product page in your normal browser, signed in if you usually are
2. Open DevTools (F12) → **Network** tab → reload the page
3. Click the first request (the document request, e.g. `/dp/B0CHSGDFN4`)
4. Headers tab → scroll to **Request Headers** → find `Cookie:`
5. Copy the entire value after `Cookie: ` (will be a long string of `name=value;` pairs)

**Then in HA:**
- Settings → Devices & Services → Price Watch → click the product → Configure
- Paste the cookie string into the `custom_parser` JSON's `request_cookies` field

**Cookies expire.** Amazon rotates session cookies every few days. When extraction starts failing again, repeat the steps above. There's no clean automation for this — it's the trade-off for accessing aggressively-protected sites.

**Privacy note:** session cookies grant access to your browser session. Don't share parser configs publicly with `request_cookies` populated. The cookies you'd typically need are:
- `session-id`, `session-token` — basic session identity
- `ubid-acbuk` (or similar regional variants) — anonymous browsing ID
- `i18n-prefs`, `lc-acbuk` — region/language prefs

You don't need login cookies (`at-acbuk`, `sst-acbuk`) — those grant account access and you should NOT include them.

**Example: Amazon UK custom parser with cookies (override the preset)**

```json
{
  "type": "css",
  "url": "https://www.amazon.co.uk/dp/B0CHSGDFN4",
  "request_cookies": "session-id=259-1234567-1234567; ubid-acbuk=257-1234567-1234567; i18n-prefs=GBP",
  "selectors": {
    "title": "#productTitle",
    "price": "#corePrice_feature_div .a-price .a-offscreen, #apex_desktop .a-price .a-offscreen",
    "image_url": "#landingImage@src",
    "in_stock": "#availability span"
  },
  "transforms": {
    "price": "price_clean",
    "in_stock": "contains:in stock"
  },
  "default_currency": "GBP",
  "default_retailer": "Amazon"
}
```

## Available transforms

Chain with `|`. Applied left to right.

| Transform | Effect |
|---|---|
| `regex:<pattern>` | Removes everything matching the pattern |
| `replace:<from>:<to>` | String replace |
| `prefix:<str>` | Prepends `<str>` to the value (skipped if value already starts with `http://` or `https://`) |
| `coalesce:<key>` | If the field is empty/null, fall back to another extracted field |
| `float` | Cast to float |
| `int` | Cast to int (via float, so "12.0" works) |
| `strip` | Trim whitespace |
| `lower` | Lowercase |

Example pipeline for Norwegian prices like "kr 4 999,00":
`regex:[^0-9., ]|replace: :|replace:,:.|float` → `4999.0`

## Tips

1. **Use Claude AI mode first to validate the URL works**, then add a parser to make tracking free.
2. **Use the page source view** in your browser (Ctrl+U) — JS-rendered content may not appear, so make sure the field exists in raw source if using `css`/`regex`.
3. **JSON-LD often works for free** without a parser — Price Watch tries it automatically. If a site has Schema.org Product markup, you'll see `"extraction_method": "jsonld"` in the price sensor's attributes.
4. **For SPAs**, open DevTools → Network → Fetch/XHR while reloading the page. The product API call usually returns JSON containing the price; that's your `url` for a `raw_json` parser.

## Worked example: Tölvutek

The product page URL is the human-friendly one — but the data is fetched from `/api//FetchProduct` (yes, double slash) via POST with `prodId`. We use that as the override URL:

```json
{
  "type": "raw_json",
  "url": "https://tolvutek.is/api//FetchProduct",
  "request_method": "POST",
  "request_body": "{\"prodId\": 39910, \"displayPricesWithTax\": true, \"includeCardLoan\": false}",
  "request_headers": {"Content-Type": "application/json"},
  "selectors": {
    "title": "r.name",
    "price": "r.specialPriceIncTax",
    "_price_fallback": "r.priceIncTax",
    "stock_count": "r.quantity",
    "image_url": "r.image",
    "sku": "r.sku",
    "retailer": "r.manufacturerName"
  },
  "transforms": {
    "price": "coalesce:_price_fallback|float",
    "stock_count": "int",
    "image_url": "prefix:https://tolvutek.is"
  },
  "default_currency": "ISK"
}
```

Tölvutek returns both `priceIncTax` (regular) and `specialPriceIncTax` (sale price). We extract both and `coalesce` falls back when the special price is missing.

Replace `39910` in the body with whatever appears at the end of the product page URL (e.g. `2_39910.action`). That's the unique product ID.
