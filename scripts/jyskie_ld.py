import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
import re, json

html = cr.get(
    "https://jysk.ie/garden/sun-shades/gazebos-and-pergolas/gazebo-nordmarka-w3xl4xh278m-grey",
    impersonate="chrome", timeout=30,
).text
for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
    d = json.loads(m.group(1))
    if isinstance(d, dict) and d.get("@type") == "ProductGroup":
        print("TOP KEYS:", list(d.keys()))
        print("has offers:", "offers" in d, "| has hasVariant:", "hasVariant" in d)
        if "offers" in d:
            print("OFFERS:", json.dumps(d["offers"], ensure_ascii=False)[:500])
        hv = d.get("hasVariant") or []
        print("num hasVariant:", len(hv))
        if hv and isinstance(hv[0], dict):
            v = hv[0]
            print("variant[0] @type:", v.get("@type"), "keys:", list(v.keys()))
            print("variant[0]:", json.dumps(v, ensure_ascii=False)[:700])
