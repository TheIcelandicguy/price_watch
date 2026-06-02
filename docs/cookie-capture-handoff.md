# Cookie capture — handoff / re-apply checklist

**Purpose:** the cookie-capture work lives on branch
`claude/price-watch-chrome-extension-qTO74` (base commit `028919e`). The live
codebase on `main` has since diverged (Wix-variant extraction, a larger
`extractor.py`), so this work must be **re-applied / merged** rather than
installed as-is. This doc is the checklist for doing that against the real
files. The branch diff is the source of truth for exact text:

```
git diff 028919e..origin/claude/price-watch-chrome-extension-qTO74
```

## Mental model (the one rule)

The extractor reads cookies from **exactly one place**: `custom_parser.request_cookies`.
Everything below is about getting cookies into that location from every entry
point (panel, add-product form, services) and making a selector-less parser
still extract. Cookies are stored as a **header string** (`"a=1; b=2"`) and
converted to a `{name: value}` dict only at fetch time.

## Checklist

| File | Change | Merge difficulty |
|------|--------|------------------|
| `cookies.py` (NEW) | shared `to_header_str` / `to_dict` | drops in clean |
| `extractor.py` | cookies-only → JSON-LD passthrough; `_normalize_cookies` → re-export | **needs care** (Wix touched this file) |
| `__init__.py` | route `request_cookies` into `custom_parser`; guards | needs care |
| `coordinator.py` | `effective_custom_parser()` + use it in poll | needs care |
| `sensor.py` | `has_cookies` boolean attribute | easy |
| `config_flow.py` | non-preset cookies fix; `_parser_get_cookies` delegates | easy |
| `websocket.py` | widen `test_selector` `request_cookies` schema | trivial |
| `panel/src/{panel,types,utils}.ts` | cookie box, save/clear, test-with-cookies, hint | easy (then rebuild) |
| `services.yaml` | `request_cookies` docs | trivial |
| `tests/test_extractor.py` | normalization + passthrough tests | easy |

## 1. `cookies.py` (NEW — drops in clean)

Copy the file verbatim from the branch. Two functions:
- `to_header_str(value)` — str/dict/list-of-dicts → `"a=1; b=2"` (stored shape)
- `to_dict(value)` — str/dict/list-of-dicts → `{name: value}` or `None` (fetch shape)

## 2. `extractor.py` — THE CRITICAL FIX ⚠️

Without this, a cookies-only parser is forced down the empty-CSS path, raises
`"did not extract a title"`, and **hard-fails on the free/no-AI tier** (never
reaches JSON-LD). Re-apply against the Wix version of `extract_product`:

At the **top of `extract_product`**, before the `if custom_parser:` block:
```python
if custom_parser and not custom_parser.get("selectors"):
    # Cookies-only / selector-less parser: lift its cookies and fall through
    # to the standard JSON-LD → AI pipeline instead of the (empty) CSS path.
    passthrough_cookies = _normalize_cookies(custom_parser.get("request_cookies"))
    custom_parser = None
else:
    passthrough_cookies = None
```
In the **no-custom-parser branch**, pass those cookies to the fetch:
```python
html = await fetch_html(url, session=session, cookies=passthrough_cookies)
```
And replace the old `_normalize_cookies` body with a re-export (top imports):
```python
from .cookies import to_dict as _normalize_cookies
```
> ⚠️ Verify the Wix version doesn't add another `selectors`-less-but-valid
> parser kind. The guard is "no `selectors` → not extraction-capable → fetch
> with cookies, use JSON-LD". If Wix introduces a parser type that extracts
> without `selectors`, refine the condition.

## 3. `__init__.py` — services route cookies into the parser

Add near the top:
```python
from .cookies import to_header_str as _cookies_to_header_str

_COOKIE_PARSE_ERR = (
    "request_cookies could not be parsed; expected a 'name=value; ...' header "
    "string, a {name: value} dict, or a list of {name, value} dicts"
)
```

**`add_listing`** — after parsing `custom_parser` (add a dict guard), instead
of storing a top-level `request_cookies`:
```python
if not isinstance(custom_parser, dict) and custom_parser is not None:
    raise HomeAssistantError("custom_parser must be a JSON object")
raw_cookies = call.data.get("request_cookies")
cookie_str = _cookies_to_header_str(raw_cookies)
if raw_cookies and not cookie_str:
    raise HomeAssistantError(_COOKIE_PARSE_ERR)
if cookie_str:
    if not isinstance(custom_parser, dict):
        custom_parser = {}
    custom_parser["request_cookies"] = cookie_str
# do NOT add a top-level "request_cookies" key to the listing dict
```

**`edit_listing`** — cookies are **orthogonal** to the rest of the parser:
```python
prior_parser = target.get("custom_parser")
prior_cookies = (
    prior_parser.get("request_cookies") if isinstance(prior_parser, dict) else None
)
# ... in the custom_parser branch, after setting target["custom_parser"]:
#   - reject non-dict JSON: if not isinstance(parsed, dict): raise
#   - carry cookies forward when request_cookies NOT also in the call:
if "request_cookies" not in call.data and prior_cookies:
    np = target["custom_parser"]
    if isinstance(np, dict):
        np.setdefault("request_cookies", prior_cookies)
    else:
        target["custom_parser"] = {"request_cookies": prior_cookies}

# request_cookies branch:
if "request_cookies" in call.data:
    raw_cookies = call.data.get("request_cookies")
    cookie_str = _cookies_to_header_str(raw_cookies)
    if raw_cookies and not cookie_str:       # unparseable ≠ clear
        raise HomeAssistantError(_COOKIE_PARSE_ERR)
    base = target.get("custom_parser")
    parser = dict(base) if isinstance(base, dict) else {}
    if cookie_str:
        parser["request_cookies"] = cookie_str
    else:
        parser.pop("request_cookies", None)
    target["custom_parser"] = parser or None
target.pop("request_cookies", None)          # drop the dead top-level field
```
Why orthogonal: the panel rewrites `custom_parser` wholesale and never sees the
cookie value (it's a secret), so a selector edit must not wipe cookies.

Also widen both service schemas: `request_cookies: vol.Any(str, dict, list)`.

## 4. `coordinator.py` — one tolerant read boundary

```python
def effective_custom_parser(self, listing_id: str) -> dict[str, Any] | None:
    config = self._get_listing_config(listing_id) or {}
    parser = self._parse_custom_parser(config.get("custom_parser"))
    if parser is None and listing_id == self._primary_listing_id:
        parser = self._custom_parser
    return parser
```
Use it in the poll path: `custom_parser = self.effective_custom_parser(listing_id)`
(replacing the raw `config.get("custom_parser")` + primary fallback).

## 5. `sensor.py` — the panel "cookies set" hint

```python
from .cookies import to_header_str as _cookies_to_header_str
# in the price sensor's extra_state_attributes dict:
"has_cookies": bool(
    (parser := self.coordinator.effective_custom_parser(self._listing_id))
    and _cookies_to_header_str(parser.get("request_cookies"))
),
```
Only the boolean is exposed — never the cookie value.

## 6. `config_flow.py` — cookies on non-preset adds

In `async_step_product`, replace the "no preset → warn and drop cookies" branch:
```python
if cookies_raw:
    if preset_parser is None:
        preset_parser = {}
    preset_parser["request_cookies"] = cookies_raw
```
And make `_parser_get_cookies` delegate its value→string conversion to
`cookies.to_header_str` (so str/dict/list all round-trip).

## 7. `websocket.py` — let Test send cookies

```python
vol.Optional("request_cookies"): vol.Any(None, str, dict, list),
```
The handler already does `_normalize_cookies(msg.get("request_cookies"))` and
`fetch_html(..., cookies=cookies)` — just the schema was too narrow.

## 8. Panel (`panel/src/`)

- `types.ts`: add `hasCookies: boolean` to `Listing`.
- `utils.ts`: `hasCookies: attrs.has_cookies === true` in `buildListing`.
- `panel.ts`: add `_selCookies` state; a **Request cookies** `<textarea>` in the
  selector editor; in `_saveSelector` send `custom_parser` only when a selector
  is present and `request_cookies` only when the box is non-empty (error if both
  empty); `_clearSelector` ("Reset to automatic") sends `custom_parser: ""` AND
  `request_cookies: ""`; `_runSelectorTest` includes `request_cookies` when set;
  render "✓ cookies currently set" when `listing.hasCookies`.
- Rebuild: `cd panel && npm install && npm run build` (regenerates
  `frontend/price-watch-panel.js`).

## Gotchas when merging with the Wix code
- **Don't reintroduce a top-level `listing["request_cookies"]`** — the extractor
  only reads `custom_parser.request_cookies`. (Migration mirrors it; that's fine
  and harmless, but new writes go into the parser.)
- The passthrough guard hinges on `selectors` being the extraction signal. If
  the Wix work changed how parsers are dispatched, re-check that a cookies-only
  parser still routes to JSON-LD, not to a Wix/variant path.
- Storage shape is mixed on disk (config flow = JSON string; services = dict).
  `effective_custom_parser` / `_parse_custom_parser` tolerate both — keep that.

## Verify
- `pytest tests/test_extractor.py` — cookie normalization + the cookies-only→
  JSON-LD passthrough (with and without an AI provider).
- Free-mode smoke: add an Amazon product → first poll fails (cookie wall) →
  paste cookies in the panel → next poll succeeds via JSON-LD; editor shows
  "✓ cookies currently set"; "Test on live page" works with cookies.
