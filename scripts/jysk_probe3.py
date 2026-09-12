import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from bs4 import BeautifulSoup
from custom_components.price_watch.extractor import try_jsonld, _parse_jysk_original_price

# The bare href from the 300x400 size option (no PathId).
href = "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x4x2-78-m-gratt"
r = cr.get(href, impersonate="chrome", timeout=30, allow_redirects=True)
print("status:", r.status_code, "final url:", r.url)
html = r.text
ld = try_jsonld(html)
print("JSON-LD title:", ld and ld.get("title"))
print("JSON-LD price:", ld and ld.get("price"), ld and ld.get("currency"))
print("original(strike):", _parse_jysk_original_price(html))
soup = BeautifulSoup(html, "html.parser")
cont = soup.find(class_="size-options")
if cont:
    print("size options on the 3x4 page:")
    for it in cont.find_all(class_="size-option-item"):
        cls = " ".join(it.get("class") or [])
        print(f"  {it.get_text(strip=True)!r} selected={'selected' in cls} href={it.get('href')!r}")
