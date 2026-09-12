from curl_cffi import requests as cr
import re, json

url = "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x3x2-78-m-gratt/?PathId=71af1d46-8786-4886-b15d-07ca0126860c"
r = cr.get(url, impersonate="chrome", timeout=30)
html = r.text
print("status", r.status_code, "len", len(html))
print("has JSON-LD:", "application/ld+json" in html)
print("has availability-list:", "availability-list" in html)
print("has __NEXT_DATA__:", "__NEXT_DATA__" in html)
print("has rfl-single-product__availability:", "rfl-single-product__availability" in html)

for pat in [
    r'"price"\s*:\s*"?([0-9.,]+)',
    r'itemprop="price"[^>]*content="([0-9.,]+)"',
    r'class="[^"]*price[^"]*"[^>]*>\s*([^<]*kr[^<]*)',
    r'data-price="([0-9.,]+)"',
]:
    mm = re.findall(pat, html)[:5]
    print("PAT", repr(pat), "->", mm)

# JSON-LD blocks
for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        print("ld parse fail", e); continue
    print("LD-TYPE:", d.get("@type") if isinstance(d, dict) else type(d))
    print(json.dumps(d, ensure_ascii=False)[:800])

# availability section snippet
i = html.find("rfl-single-product__availability")
if i != -1:
    print("AVAIL SNIPPET:", html[i:i+1600])
