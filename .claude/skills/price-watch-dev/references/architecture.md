# Architecture (verified against repo)

Read this when changing extraction, the coordinator, fetching, FX, discovery, cookies, or history. Grounded in README + CHANGELOG (v0.2.0).

## Extraction modes

These are not a single "mode" setting: the setup flow only chooses the provider (free, Anthropic or OpenAI-compatible, changeable later in the panel's ⚙ settings or the options flow), a custom parser is per listing, and `extract_product` runs a cascade — custom parser, variant override, JSON-LD, then AI only if all produced nothing (no AI provider configured means a raise, not a guess):

1. **Free (default)** — reads Schema.org `Product` / Open Graph price+stock. No key, no cost. Works on most major retailers.
2. **Custom parser** — point it at the price with **CSS / regex / JSONPath / raw-JSON**. Also free. For sites that show a price but don't expose structured data, or hide it behind cookies. Supports per-listing currency / retailer / unit overrides and cookies, all editable from the panel.
3. **AI fallback** — Anthropic (Claude) or any OpenAI-compatible endpoint (Ollama, LM Studio, Groq, OpenRouter). Optional; can be set fallback-only so discovery stays free. A universal reader for pages the other modes can't parse, and smarter discovery.

A cookies-only parser fetches with its cookies and then falls through to the JSON-LD / AI pipeline, so cookie-walled sites no longer dead-end.

## Coordinator (split into mixins)

As of v0.2.0 the coordinator is **split into focused mixins**:

- events
- fx
- storage
- update
- alternatives

Cookie normalization is consolidated into a single `cookies` module. When touching coordinator behavior, find the right mixin rather than expecting one monolithic `coordinator.py`. (Verified function-level details — `_ensure_primary_listing`, provider precedence, the two enrichment paths — are in `internals.md`.)

## Fetching / anti-bot

- **browser TLS impersonation** via curl_cffi, pinned to **`_IMPERSONATE = "chrome131"`** (in `extractor.py`) — **not** the bare `"chrome"` alias. The alias tracks curl_cffi's newest fingerprint, which Best Buy / B&H 403 or reset; `chrome131` passes them *and* everything that already worked. Don't "upgrade" this without re-probing.
- **Automatic fresh-session retry** for sites that reject a reused session: an interstitial body (Amazon "continue shopping"), a **403/429 status** (Argos-style "Access Denied"), *or* a **connection/HTTP-2 stream-reset exception**. The retry runs on a throwaway cookie-free session and the host is remembered in a module-level `_FRESH_SESSION_HOSTS` set so later polls skip the shared jar.
- **Per-host politeness gap** + a **global concurrency cap** so a large fleet of products doesn't burst-hit a store.
- Where a page has no usable structured price, `find_meta_price` enriches from `<meta>`/microdata (OG `product:price:amount`, `itemprop=price`) — used in alternatives/"Search & add" enrichment after JSON-LD.

Known hard limits: some big retailers actively block bots (Amazon, Best Buy, Home Depot, Lowe's, MediaMarkt at times); "see price in cart" / MAP pricing genuinely isn't on the page and can't be read.

## FX conversion

Every price is also reported in the home currency via `sensor.<slug>_price_local`. Region resolution: ISK → Iceland.

## Discovery / alternatives

"Search & add" looks a product up across the web, prices results that expose a price (JSON-LD or `<meta>`/microdata), filters out review/category/search pages, sorts priced results first, and lets you add any with one click. **Region-aware:** flags and can hide listings that won't ship to the user. Search sources include DuckDuckGo (weaker for niche items), AI search (stronger), and **SearXNG** as an alternative; there's a global excluded-domains blocklist.

## History model

- Fine-grained **recent** history.
- **Daily-downsampled long-term** history alongside it (added in v0.2.0).
- (v0.1.0 stored last 30 entries + lifetime extremes; the downsampled long-term store is the newer addition.)

## Cost

Free mode and custom parsers cost nothing. With an Anthropic key, ~$0.50–$2/month for ~10 products (content-hash skip when the page is unchanged + prompt caching + daily/monthly budget caps). Local Ollama is free. An entered API key is stored in HA `.storage` in plain text, like other integrations.
