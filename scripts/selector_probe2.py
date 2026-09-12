import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from bs4 import BeautifulSoup
import re, json

TARGETS = {
    "amazon.com": ("https://www.amazon.com/SAMSUNG-Technology-Intelligent-Turbowrite-MZ-V9S1T0B/dp/B0DHLFWBQ1",
                   ["#corePrice_feature_div span.a-offscreen", "span.a-price span.a-offscreen", "#productTitle"]),
    "walmart.com": ("https://www.walmart.com/ip/Mainstays-2-Slice-Toaster-with-6-Shade-Settings-and-Removable-Crumb-Tray-Black/1233603801",
                    ['span[itemprop="price"]', 'meta[itemprop="price"]', '[data-testid="price-wrap"]']),
    "target.com": ("https://www.target.com/p/keurig-k-classic-single-serve-k-cup-pod-coffee-maker-k50/-/A-50981282",
                   ['[data-test="product-price"]', 'span[data-test="product-price"]']),
    "mediamarkt.de": ("https://www.mediamarkt.de/de/product/_samsung-gu55du7170-led-tv-flat-55-zoll-138-cm-uhd-4k-smart-tv-tizen-2924382.html",
                      ['meta[property="product:price:amount"]', '[data-test="branded-price-whole-value"]', 'span.price']),
}

for host, (url, sels) in TARGETS.items():
    print(f"\n===== {host} =====")
    try:
        html = cr.Session(impersonate="chrome").get(url, timeout=30).text
    except Exception as e:
        print("  fetch err", e); continue
    soup = BeautifulSoup(html, "html.parser")
    for s in sels:
        el = soup.select_one(s)
        val = (el.get("content") or el.get_text(strip=True)) if el else None
        print(f"  {s:48} -> {val!r}")
    # meta price tags anywhere
    for m in soup.select('meta[itemprop="price"], meta[property*="price:amount"], meta[property="og:price:amount"]'):
        print(f"  META {m.get('property') or m.get('itemprop')} = {m.get('content')!r}")
    # any 2nd JSON-LD with offers
    prices = re.findall(r'"price"\s*:\s*"?([0-9]+[.,][0-9]{2})"?', html)
    print(f"  regex \"price\":N.NN hits (first 5): {prices[:5]}")
