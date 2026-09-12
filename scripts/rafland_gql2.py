import sys, json
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

QUERY = (
    'query($f:ProductAttributeFilterInput){products(filter:$f){items{'
    'name sku url_key '
    'price_range{minimum_price{final_price{value currency} regular_price{value currency}}}'
    'stock_status}}}'
)
ENDPOINT = "https://backend-v2-ht.roanuz.com/graphql"
variables = {"f": {"url_key": {"eq": "samsung-55-qled-uhd-4k-sjonvarp-2023"}}}

for store in ["rafland_store_view", "default"]:
    print(f"\n=== Store: {store} ===")
    body = json.dumps({"query": QUERY, "variables": variables})
    try:
        r = cr.Session(impersonate="chrome131").post(
            ENDPOINT, data=body,
            headers={"Content-Type": "application/json", "Store": store},
            timeout=30,
        )
        print("  status:", r.status_code, "len", len(r.text))
        d = r.json()
        if d.get("errors"):
            print("  errors:", json.dumps(d["errors"])[:200])
        items = (((d.get("data") or {}).get("products") or {}).get("items")) or []
        for it in items[:2]:
            fp = it.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
            print(f"  -> {it.get('name')[:45]!r} sku={it.get('sku')} price={fp.get('value')} {fp.get('currency')} stock={it.get('stock_status')}")
        if not items and not d.get("errors"):
            print("  (no items)", json.dumps(d)[:160])
    except Exception as e:
        print("  ERR", type(e).__name__, str(e)[:80])
