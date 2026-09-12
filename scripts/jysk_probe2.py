import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
import re
from bs4 import BeautifulSoup

url = "https://jysk.is/stok-vara/NORDMARKA-solhysi-3x3x2-78-m-gratt/?PathId=71af1d46-8786-4886-b15d-07ca0126860c"
html = cr.get(url, impersonate="chrome", timeout=30).text
soup = BeautifulSoup(html, "html.parser")

print("=== DISCOUNT ===")
print("has product-price__offer-price:", "product-price__offer-price" in html)
print("has discount-sticker:", "discount-sticker" in html)
pc = soup.find(class_="product-price-container")
if pc:
    print("container text:", re.sub(r"\s+", " ", pc.get_text(" ", strip=True))[:200])
strike = soup.find(class_="product-price__offer-price")
print("offer-price(strike):", strike.get_text(strip=True) if strike else None)
sticker = soup.find(class_="discount-sticker")
print("sticker:", sticker.get_text(strip=True) if sticker else None)
cur = soup.find(class_="product-price__price")
print("current price:", cur.get_text(strip=True) if cur else None)

print("\n=== SIZE OPTIONS ===")
print("has size-options:", "size-options" in html)
cont = soup.find(class_="size-options")
if cont:
    for it in cont.find_all(class_="size-option-item"):
        cls = " ".join(it.get("class") or [])
        print(f"  size={it.get_text(strip=True)!r} href={it.get('href')!r} selected={'selected' in cls} color={it.get('data-color')!r}")
