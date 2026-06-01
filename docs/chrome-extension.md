# Price Watch Companion — Chrome Extension Design Doc

**Status:** PROPOSED (not yet built). Target branch
`claude/price-watch-chrome-extension-qTO74`.

## Motivation

Several retailers (Amazon, Cloudflare-walled shops, anything that gates the
real product page behind a session) only serve usable HTML to a request that
carries the right cookies. Price Watch already supports this: every listing
has a `request_cookies` field that the extractor sends with each fetch
(`listings.py:78`, `extractor.py:630`). The cookies are also accepted as a
raw `Cookie:` header string and normalized server-side (`extractor.py:394`).

The problem is **getting the cookies in**. Today it's entirely manual:

1. Open the retailer page in a browser.
2. F12 → Network/Application → copy the `Cookie` header or session cookies.
3. Paste that string into the config-flow "cookies" field
   (`config_flow.py:743`) or the panel's per-listing options
   (`config_flow.py:1269`).

That's fiddly, error-prone, and the cookies expire — so it has to be
repeated. A browser extension can do the capture in one click, against the
tab the user is already looking at, and push it straight into the matching
listing.

This doc also covers a second, closely related convenience: a **"Track this
page"** button that creates a tracked product from the current tab via the
existing `price_watch.track_product` service.

## Decisions locked in

- **Cookie targeting: auto-match by domain.** The extension sends
  `{url, cookies}`; the backend finds the listing(s) whose URL host matches
  the tab's host and writes the cookies to them. The extension stays dumb —
  it never has to enumerate `entry_id` / `listing_id` (which is awkward for
  non-primary listings).
- **MVP scope: cookies + one-click track.** Both the cookie import and a
  "Track this page" button ship in v1.
- **Auth: Home Assistant long-lived access token + base URL.** A Chrome
  extension can't reuse the HA web session, so the user pastes an HA base URL
  and a long-lived token (created in HA → Profile → Security) into the
  extension's options once. The extension calls HA's REST API with
  `Authorization: Bearer <token>`.

## Architecture

```
Chrome extension (MV3)                  Home Assistant
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│ popup.html / popup.js        │        │ REST API  /api/services/...       │
│  • "Send cookies for this    │ POST   │                                   │
│     site"  ──────────────────┼───────▶│ price_watch.import_cookies (NEW)  │
│  • "Track this page"  ───────┼───────▶│   • host-match listings           │
│                              │ Bearer │   • set request_cookies           │
│ chrome.cookies.getAll()      │ token  │   • async_reload → next poll uses │
│ chrome.tabs (active tab URL) │        │                                   │
│                              │ POST   │ price_watch.track_product (exists)│
│ options.html (HA url+token)  │───────▶│   • create entry from URL         │
└─────────────────────────────┘        └──────────────────────────────────┘
```

Two deliverables:

1. **Backend:** one new service, `price_watch.import_cookies`. Everything
   else reuses what already exists.
2. **Extension:** a new top-level `chrome-extension/` directory (Manifest V3).

## Backend changes

### New service: `price_watch.import_cookies`

Registered in `__init__.py` alongside the existing services, documented in
`services.yaml`.

**Fields:**

| field     | type         | required | notes                                            |
|-----------|--------------|----------|--------------------------------------------------|
| `url`     | str          | yes      | The page URL whose host selects target listings. |
| `cookies` | str \| list  | yes      | `Cookie:` header string, OR a list of cookie dicts `{name, value, domain?, path?}`. |
| `entry_id`| str          | no       | Restrict matching to a single product entry.     |

**Behaviour:**

```
host = hostname(url), normalized (strip leading "www.")
matched = []
for entry in config_entries for DOMAIN that are product entries:
    if entry_id given and entry.entry_id != entry_id: continue
    for listing in entry.options["listings"]:
        if normalized host of listing["url"] == host:
            listing["request_cookies"] = normalized_cookies
            matched.append((entry, listing_id))
for each touched entry:
    async_update_entry(entry, options=...)
    async_reload(entry.entry_id)     # next poll picks up the cookies
raise HomeAssistantError if matched is empty
```

Notes:

- **Normalization mirrors the extractor.** `request_cookies` is stored as
  whatever shape the service receives; the extractor already accepts both a
  dict/list and a `Cookie:` header string (`extractor.py:_normalize_cookies`,
  `config_flow.py:_parser_with_cookies`). To stay consistent with the
  existing per-listing storage shape, the service will store the cookie
  **string** form (same as the config-flow "cookies" field persists into
  `custom_parser.request_cookies`). The exact persisted location —
  top-level `listing["request_cookies"]` vs `custom_parser.request_cookies`
  — must match what the extractor reads at poll time; the implementation
  will confirm against `coordinator` listing load before finalizing. *(Open
  item, see below.)*
- **Host match** uses `urllib.parse.urlsplit(...).hostname`, lower-cased,
  with a leading `www.` stripped on both sides so `www.amazon.com` and
  `amazon.com` match. Subdomain mismatches (`smile.amazon.com`) are treated
  as non-matching in v1 to avoid leaking session cookies to the wrong host.
- **No silent no-op.** If nothing matches, the service raises so the
  extension popup can tell the user "no tracked listing for this site"
  (and offer the Track button instead).
- Reuses the existing `_resolve_entry` / listing-lookup patterns from
  `add_listing` / `edit_listing` for consistency.

### One-click track

No backend change needed — `price_watch.track_product` already takes a
`url` (and optional `name`, `target_price`) and drives the `panel_track`
config-flow source (`__init__.py:track_product`). It already raises a
friendly error when the product is already tracked, which the popup
surfaces.

## Extension layout (Manifest V3)

```
chrome-extension/
├── manifest.json        # MV3, permissions: cookies, activeTab, storage; host_permissions
├── popup.html           # the two buttons + status line
├── popup.js             # read active tab + cookies, POST to HA
├── options.html         # HA base URL + long-lived token entry
├── options.js           # persist config to chrome.storage.local
├── background.js         # (optional) shared fetch helper / token storage
├── icons/               # 16/48/128 px, reuse brand assets
└── README.md            # install (load unpacked), token setup, usage
```

### Permissions

- `cookies` — read cookies for the active tab's domain.
- `activeTab` + `tabs` — get the current tab's URL.
- `storage` — persist HA base URL + token.
- `host_permissions` — the user's HA base URL (for the REST calls) plus
  `<all_urls>` is **avoided**; instead cookie reads use the active tab's
  domain only, requested at click time.

### Cookie capture

```js
const { url } = await activeTab();
const u = new URL(url);
const cookies = await chrome.cookies.getAll({ domain: u.hostname });
const header = cookies.map(c => `${c.name}=${c.value}`).join("; ");
await haCall("price_watch/import_cookies", { url, cookies: header });
```

`chrome.cookies.getAll({ domain })` returns `httpOnly` cookies too (the
session cookies that matter for anti-bot), which DevTools copy-paste also
gets but which page JS / a bookmarklet cannot read — a concrete advantage
of the extension over the existing bookmarklet flow.

### HA call helper

```js
async function haCall(service, data) {
  const { haUrl, token } = await chrome.storage.local.get(["haUrl", "token"]);
  const domain = "price_watch", srv = service.split("/")[1];
  const res = await fetch(`${haUrl}/api/services/${domain}/${srv}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`,
               "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
}
```

## Security considerations

This is the part that deserves care — both the token and the cookies are
sensitive.

- **The long-lived token grants full HA API access**, not just Price Watch.
  The README will state this plainly and recommend a dedicated token the
  user can revoke. Stored in `chrome.storage.local` (origin-isolated, not
  synced).
- **Cookies are live session credentials.** They travel: browser →
  extension → HA REST (HTTPS if the user's HA is TLS) → stored in the entry
  options → sent to the retailer on each poll. The README will note they're
  stored in plaintext in HA's config entry (same as the existing manual
  paste flow — no new exposure, but worth stating).
- **HTTP vs HTTPS:** if the user's HA base URL is plain `http://`, the token
  and cookies cross the LAN in cleartext. The options page will warn when a
  non-HTTPS URL is entered.
- **Host-match guard:** the backend only writes cookies to listings whose
  host equals the source host, so a captured Amazon cookie can never land on
  a different retailer's listing.
- **No telemetry, no external calls.** The extension talks only to the
  user's configured HA instance.

## Open items to resolve during implementation

1. **Exact persisted cookie location.** Confirm whether the poll path reads
   `listing["request_cookies"]` (top-level, per `listings.py:78`) or
   `custom_parser.request_cookies` (per `extractor.py:630` /
   `config_flow.py`). The config-flow UI writes into the parser; the
   `edit_listing` service writes top-level. The new service must write
   wherever the coordinator actually reads at poll time — verify against
   `coordinator`/`listings.py` load before shipping, and prefer reusing the
   same merge helper the config flow uses (`_parser_with_cookies`) if that's
   the canonical path.
2. **Cookie value shape:** store as `Cookie:` header string (simplest, the
   extractor normalizes it) vs list of dicts (matches `services.yaml`
   `request_cookies` docs). Header string is the leaner choice and what the
   manual flow already persists.
3. **Subdomain policy:** v1 exact-host match only. Revisit if real listings
   span subdomains.
4. **Multiple matches:** if several listings share a host (e.g. two Amazon
   products), update all of them. Confirm that's the desired behavior (it
   is, for shared session cookies) and report the count back to the popup.

## Implementation plan

- **Phase 1 — backend.** Add `import_cookies` service + `services.yaml`
  entry + a unit test (host matching, no-match raises, cookie persisted
  where the extractor reads it). Resolve open item #1 here.
- **Phase 2 — extension.** Scaffold `chrome-extension/` (manifest, popup,
  options, background, icons, README). Wire the two buttons.
- **Phase 3 — docs.** Link the extension from the main README and note the
  manual paste flow still works.

## Future work (out of scope for MVP)

- Auto-refresh cookies on a schedule / on expiry detection.
- Firefox (WebExtensions) port — the code is MV3-portable.
- Capture the live CSS price selector from the page (fold in the existing
  bookmarklet picker, `panel.ts:164`) so "tune this listing" is also
  one-click.
- OAuth/IndieAuth instead of a long-lived token.
