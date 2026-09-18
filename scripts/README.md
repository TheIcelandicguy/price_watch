# scripts/

Development aids, not part of the integration: nothing in
`custom_components/price_watch/` imports them, the test suite does not cover
them, and neither ships in a release. Run them from the repo root.

## retailer_probe.py

Fetches a list of product pages through the real extractor path (`curl_cffi`
with Chrome impersonation, a fresh session each) and reports one of three
outcomes per shop:

- **bot wall** - the site needs cookies, or is not worth supporting;
- **JSON-LD price** - the free Schema.org / Open Graph path works, no preset
  needed;
- **needs a selector** - the page loaded but carries no usable price, so the
  site needs a selector or an API preset (see `docs/custom_parsers.md` and
  `custom_components/price_watch/presets/`).

Edit `URLS` for the shops you want to test. It hits live retailer sites: keep
the rate low, and expect results to change when a shop changes its markup.

```
python scripts/retailer_probe.py
```

## convert_brand.py

Re-renders the PNGs in `custom_components/price_watch/brand/` from their SVGs
with `resvg_py` (`pip install resvg_py`). Run it after editing a brand SVG.

```
python scripts/convert_brand.py
```
