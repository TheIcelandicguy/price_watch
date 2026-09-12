import sys, re, json
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.parsers import apply_custom_parser

# ---- MediaMarkt: regex parser on the JSON-LD offer ----
print("===== MEDIAMARKT regex parser =====")
mm_url = "https://www.mediamarkt.de/de/product/_samsung-gu55du7170-led-tv-flat-55-zoll-138-cm-uhd-4k-smart-tv-tizen-2924382.html"
mm_html = cr.Session(impersonate="chrome131").get(mm_url, timeout=30).text
mm_parser = {
    "type": "regex",
    "selectors": {
        "price": r'"priceCurrency":"EUR","price":\s*([0-9.]+)',
        "title": [
            r'<meta[^>]*property="og:title"[^>]*content="([^"|]+)',
            r'<meta[^>]*content="([^"|]+)"[^>]*property="og:title"',
            r'<title[^>]*>([^<|]+)',
        ],
    },
    "transforms": {"price": "price_clean"},
    "min_price": 50,
}
try:
    print("  ", apply_custom_parser(mm_html, mm_parser))
except Exception as e:
    print("  PARSER ERR:", e)

# ---- Target: is RedSky API reachable? ----
print("===== TARGET redsky API =====")
t_url = "https://www.target.com/p/keurig-k-classic-single-serve-k-cup-pod-coffee-maker-k50/-/A-50981282"
t_html = cr.Session(impersonate="chrome131").get(t_url, timeout=30).text
tcin = "50981282"
# the public web API key is embedded in the page bundle
keys = re.findall(r'"apiKey":"([0-9a-f]{32})"', t_html) or re.findall(r'key=([0-9a-f]{32})', t_html)
print("  api keys found:", set(keys))
if keys:
    key = keys[0]
    api = (f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"
           f"?key={key}&tcin={tcin}&is_bot=false&pricing_store_id=3991&store_id=3991"
           f"&has_pricing_store_id=true&visitor_id=0&channel=WEB&page=%2Fp%2FA-{tcin}")
    try:
        r = cr.Session(impersonate="chrome131").get(api, timeout=30)
        print("  api status:", r.status_code, "len", len(r.text))
        d = r.json()
        price = d.get("data", {}).get("product", {}).get("price")
        print("  price node:", json.dumps(price)[:200] if price else "(none)")
    except Exception as e:
        print("  API ERR:", type(e).__name__, str(e)[:80])
