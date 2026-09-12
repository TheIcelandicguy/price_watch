import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
import re, json
from custom_components.price_watch.extractor import try_jsonld

url = "https://www.bauhaus.is/gagnvarin-fura-45x95-mm-3-4-2-m"
r = cr.get(url, impersonate="chrome", timeout=30)
html = r.text
print("status", r.status_code, "len", len(html))
print("=== try_jsonld result ===")
print(try_jsonld(html))
print("=== raw JSON-LD blocks ===")
for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        print("parse fail", e); continue
    items = d if isinstance(d, list) else (d.get("@graph") if isinstance(d, dict) and "@graph" in d else [d])
    for it in items:
        if isinstance(it, dict):
            t = it.get("@type")
            print(f"@type={t} name={it.get('name')!r} brand={it.get('brand')!r} mpn={it.get('mpn')!r}")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                print("   offers:", json.dumps(it.get("offers"), ensure_ascii=False)[:200])
print("=== <title> + h1 ===")
m = re.search(r"<title[^>]*>([^<]+)</title>", html); print("title:", m.group(1).strip() if m else None)
m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S); print("h1:", re.sub(r"<[^>]+>","",m.group(1)).strip()[:100] if m else None)
