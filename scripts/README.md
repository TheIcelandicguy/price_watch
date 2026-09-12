# scripts/

Ad-hoc probes written while working out whether a retailer can be read for
free, and what a preset for it needs to do. They are development aids, not part
of the integration: nothing in `custom_components/price_watch/` imports them and
they are not covered by the test suite.

Most of them follow the same shape — fetch a product page through the real
extractor path (`curl_cffi` with Chrome impersonation, fresh session), then
report which of three outcomes you get:

- a bot wall, so the site needs cookies or is not worth supporting;
- a usable Schema.org `Product` / Open Graph price, so the free path works and
  no preset is needed;
- neither, so the site needs a selector or an API preset.

That last case is what produced the presets in
`custom_components/price_watch/presets/`. `rafland_gql*.py` and `magento_gql.py`
are the ones that found Rafland's headless Magento GraphQL endpoint;
`elko_biltema.py`, `jysk_*.py`, `bauhaus_probe.py` and `is_*_probe.py` cover the
Icelandic shops; `amazon_*.py`, `bestbuy_*.py` and `target_mm_*.py` were the
US/EU comparison set.

Two things to know before running one:

- Several hardcode an absolute path in `sys.path.insert(...)` so they can import
  the extractor. Fix the path for your checkout.
- They hit live retailer sites. Keep the request rate low, and expect a script
  to rot the moment a shop changes its markup — that is the nature of the job,
  not a bug to fix here.
