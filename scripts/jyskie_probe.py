import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
import re, json
from custom_components.price_watch.extractor import try_jsonld

url = "https://jysk.ie/garden/sun-shades/gazebos-and-pergolas/gazebo-nordmarka-w3xl4xh278m-grey"
r = cr.get(url, impersonate="chrome", timeout=30, allow_redirects=True)
html = r.text
print("status:", r.status_code, "final:", r.url, "len:", len(html))
print("has ld+json:", "application/ld+json" in html)
print("has __NEXT_DATA__:", "__NEXT_DATA__" in html)
print("try_jsonld:", try_jsonld(html))
# dump any ld+json type
for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
    blob = m.group(1).strip()
    try:
        d = json.loads(blob)
    except Exception as e:
        print("LD parse fail:", e, "| head:", blob[:120]); continue
    t = d.get("@type") if isinstance(d, dict) else [x.get("@type") for x in d if isinstance(x, dict)]
    print("LD @type:", t)
    print(json.dumps(d, ensure_ascii=False)[:500])
# price hints
for pat in [r'"price"\s*:\s*"?([0-9.,]+)', r'itemprop="price"[^>]*content="([0-9.,]+)"', r'€\s*([0-9][0-9.,]*)']:
    print("PAT", pat, "->", re.findall(pat, html)[:4])
