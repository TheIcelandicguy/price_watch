import sys, re, json
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.parsers import apply_custom_parser

# ---- elko.is: regex parser on embedded "price" ----
print("===== ELKO regex parser =====")
elko_html = cr.Session(impersonate="chrome131").get(
    "https://elko.is/vorur/philips-phs5537-2022-sjonvarp-286633/24PHS553712", timeout=30).text
parser = {
    "type": "regex",
    "selectors": {
        "price": r'"price"\s*:\s*"?([0-9]+(?:[.,][0-9]+)?)"?',
        "title": [r'<meta property="og:title" content="([^"|]+)', r'<title[^>]*>([^<|]+)'],
    },
    "transforms": {"price": "price_clean"},
    "min_price": 100,
}
try:
    print("  ", apply_custom_parser(elko_html, parser))
except Exception as e:
    print("  ERR:", e)

# ---- biltema.dk: why did try_jsonld miss the offer? ----
print("\n===== BILTEMA JSON-LD blocks =====")
bil_html = cr.Session(impersonate="chrome131").get(
    "https://www.biltema.dk/varktoj/handvarktoj/varktojsnogler/skiftenogler/skiftenogle-pro-2000036548", timeout=30).text
for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', bil_html, re.S):
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        print("  parse fail:", e); continue
    items = d if isinstance(d, list) else (d.get("@graph", [d]) if isinstance(d, dict) else [d])
    for it in items:
        if isinstance(it, dict) and "Product" in str(it.get("@type", "")):
            print("  Product name:", (it.get("name") or "")[:50])
            print("  offers:", json.dumps(it.get("offers"), ensure_ascii=False)[:300])
