import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from bs4 import BeautifulSoup
from custom_components.price_watch.parsers import _apply_transforms
def price_clean(v): return _apply_transforms(v, "price_clean")

url = "https://www.amazon.de/-/en/gp/product/B0DTGNB9Q5/ref=ox_sc_act_title_1?smid=A3JWKAKR8XB7XF&th=1"
html = cr.get(url, impersonate="chrome", timeout=30).text
soup = BeautifulSoup(html, "html.parser")

candidates = [
    "span.priceToPay span.a-offscreen",
    "#corePrice_feature_div span.a-offscreen",
    ".a-price.priceToPay .a-offscreen",
    "#corePriceDisplay_desktop_feature_div span.a-offscreen",
    "span.a-price-whole",
    "#productTitle",
]
for sel in candidates:
    el = soup.select_one(sel)
    raw = el.get_text(strip=True) if el else None
    cleaned = None
    if raw is not None:
        try:
            cleaned = price_clean(raw)
        except Exception as e:
            cleaned = f"clean-err: {e}"
    print(f"{sel:55s} raw={raw!r:20} -> {cleaned}")
