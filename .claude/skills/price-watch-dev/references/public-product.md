# Public / SaaS Price Watch concept

A separate, larger concept from the personal HA integration: a public price-tracking product with a thin HA surface. Read this when discussing the public product direction, affiliate integration, or data sourcing.

## Architecture outline

- **Docker-based backend:** Postgres (storage), Typesense or Meilisearch (search), a feed-ingest worker.
- **API:** REST/GraphQL.
- **Web frontend** for the public-facing product.
- **Thin HA HACS integration** that surfaces price-drop sensors from the backend — the heavy lifting moves server-side, the HA piece stays light.

## Affiliate / data sourcing landscape

- **Amazon PA-API deprecated April 2026.** The **Creators API** requires qualifying sales first, so it's not a clean drop-in replacement.
- **Nordic affiliate entry:** Adtraction (which acquired Adrecord / Adservice / Affiliate Future) and Tradedoubler.
- **Iceland is a gap in every affiliate network.** There's no affiliate feed coverage for Icelandic retailers, so the **curl_cffi scraper is a permanent fixture** for Icelandic retailers — it can't be replaced by an affiliate feed the way other markets could.
