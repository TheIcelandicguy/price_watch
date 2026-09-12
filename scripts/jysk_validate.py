import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.extractor import (
    _parse_store_availability,
    try_jsonld,
)

url = "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x3x2-78-m-gratt/?PathId=71af1d46-8786-4886-b15d-07ca0126860c"
html = cr.get(url, impersonate="chrome", timeout=30).text

ld = try_jsonld(html)
print("JSON-LD price:", ld and ld.get("price"), ld and ld.get("currency"), "| title:", ld and ld.get("title"))

sa = _parse_store_availability(html)
print("store_availability rows:", len(sa) if sa else None)
for s in sa or []:
    print("  ", s)
warehouse_only = bool(sa) and all(
    s.get("from_warehouse") for s in sa if s["status"] in ("in_stock", "limited")
)
print("stock_from_warehouse:", warehouse_only)
