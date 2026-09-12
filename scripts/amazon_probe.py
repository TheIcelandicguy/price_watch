import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
import re
from custom_components.price_watch.extractor import try_jsonld

url = "https://www.amazon.de/-/en/gp/product/B0DTGNB9Q5/ref=ox_sc_act_title_1?smid=A3JWKAKR8XB7XF&th=1"
r = cr.get(url, impersonate="chrome", timeout=30)
html = r.text
print("status", r.status_code, "len", len(html))

# CAPTCHA / robot check markers
low = html.lower()
for marker in ["captcha", "api-services-support@amazon", "robot", "to discuss automated access",
               "enter the characters you see below", "automated access to amazon data"]:
    if marker in low:
        print("MARKER FOUND:", marker)

# JSON-LD?
print("=== try_jsonld ===")
try:
    print(try_jsonld(html))
except Exception as e:
    print("jsonld error:", e)

ld = re.findall(r'application/ld\+json', html)
print("ld+json blocks:", len(ld))

# Amazon price selectors
for sel in ["corePrice", "a-price-whole", "priceToPay", "apexPriceToPay", "twister-plus-price"]:
    print(f"  contains {sel!r}:", sel in html)

# title
m = re.search(r'<title[^>]*>([^<]+)</title>', html)
print("title:", m.group(1).strip()[:120] if m else None)

# show a price-ish snippet
m = re.search(r'a-price-whole[^>]*>([^<]{1,20})', html)
print("a-price-whole sample:", m.group(1) if m else None)
m = re.search(r'id="productTitle"[^>]*>(.*?)</', html, re.S)
print("productTitle:", re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else None)
