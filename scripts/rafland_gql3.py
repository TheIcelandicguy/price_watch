import sys, json
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

ENDPOINT = "https://backend-v2-ht.roanuz.com/graphql"
S = cr.Session(impersonate="chrome131")
H = {"Content-Type": "application/json", "Store": "rafland_store_view"}


def gql(q, v=None):
    r = S.post(ENDPOINT, data=json.dumps({"query": q, "variables": v or {}}), headers=H, timeout=30)
    return r.json()

# 1) Resolve the URL path -> entity
print("=== urlResolver ===")
r = gql('query($u:String!){urlResolver(url:$u){id uid type relative_url canonical_url sku}}',
        {"u": "samsung-55-qled-uhd-4k-sjonvarp-2023.html"})
print(" ", json.dumps(r)[:300])

# 2) Try a name search to learn url_key/sku shape
print("=== search 'samsung' (1) ===")
r = gql('query($s:String!){products(search:$s,pageSize:2){items{name sku url_key '
        'price_range{minimum_price{final_price{value currency}}}}}}', {"s": "samsung qled"})
items = (((r.get("data") or {}).get("products") or {}).get("items")) or []
if r.get("errors"):
    print("  errors:", json.dumps(r["errors"])[:200])
for it in items:
    fp = it.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
    print(f"  url_key={it.get('url_key')!r} sku={it.get('sku')} price={fp.get('value')} {fp.get('currency')} | {it.get('name')[:40]!r}")
if not items:
    print("  (no items)", json.dumps(r)[:160])
