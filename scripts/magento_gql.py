"""Try Magento GraphQL for rafland.is / sindri.is product price."""
import sys, json
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

QUERY = (
    'query($f:ProductAttributeFilterInput){products(filter:$f){items{'
    'name sku url_key '
    'price_range{minimum_price{final_price{value currency} regular_price{value currency}}}'
    'stock_status}}}'
)

TESTS = [
    ("rafland.is url_key", "https://rafland.is/graphql",
     {"f": {"url_key": {"eq": "samsung-55-qled-uhd-4k-sjonvarp-2023"}}}),
    ("sindri.is sku",      "https://sindri.is/graphql",
     {"f": {"sku": {"eq": "ibtgcbz186a"}}}),
    ("sindri.is url_key",  "https://sindri.is/graphql",
     {"f": {"url_key": {"eq": "verkfærakassi-186-verkfæri-ibtgcbz186a"}}}),
]

for label, endpoint, variables in TESTS:
    print(f"\n===== {label} =====")
    body = json.dumps({"query": QUERY, "variables": variables})
    try:
        r = cr.Session(impersonate="chrome131").post(
            endpoint, data=body,
            headers={"Content-Type": "application/json", "Store": "default"},
            timeout=30,
        )
        print("  status:", r.status_code, "len", len(r.text))
        try:
            d = r.json()
        except Exception:
            print("  non-JSON:", r.text[:160]); continue
        items = (((d.get("data") or {}).get("products") or {}).get("items")) or []
        if not items:
            print("  no items. errors:", json.dumps(d.get("errors"))[:200] if d.get("errors") else d)
        for it in items[:2]:
            fp = it.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
            print(f"  -> {it.get('name')[:45]!r} sku={it.get('sku')} price={fp.get('value')} {fp.get('currency')} stock={it.get('stock_status')}")
    except Exception as e:
        print("  ERR", type(e).__name__, str(e)[:70])
