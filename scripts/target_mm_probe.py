import sys, re
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from bs4 import BeautifulSoup

SITES = {
    "target": ("https://www.target.com/p/keurig-k-classic-single-serve-k-cup-pod-coffee-maker-k50/-/A-50981282", "115"),
    "mediamarkt": ("https://www.mediamarkt.de/de/product/_samsung-gu55du7170-led-tv-flat-55-zoll-138-cm-uhd-4k-smart-tv-tizen-2924382.html", "474"),
}

for name, (url, hint) in SITES.items():
    print(f"\n========== {name} ==========")
    html = cr.Session(impersonate="chrome131").get(url, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    # meta tags
    for sel in ['meta[property="og:title"]', 'meta[name="title"]',
                'meta[property="og:price:amount"]', 'meta[property="product:price:amount"]',
                'meta[itemprop="price"]', 'meta[name="twitter:title"]']:
        el = soup.select_one(sel)
        if el:
            print(f"  META {sel} = {el.get('content')!r}")
    # JSON key contexts around the price hint
    print("  --- price-key contexts ---")
    seen = set()
    for m in re.finditer(r'[\"\']([a-zA-Z_]*[Pp]rice[a-zA-Z_]*|current_retail|formatted_[a-z_]*)[\"\']\s*:\s*([\"\']?[\d.,]+[\"\']?|\{[^}]{0,60})', html):
        key, val = m.group(1), m.group(2)
        sig = (key, val)
        if sig in seen:
            continue
        seen.add(sig)
        if len(seen) <= 25:
            print(f"    {key} : {val[:60]}")
    # raw contexts around the hint number
    print(f"  --- contexts around '{hint}' (first 3) ---")
    for i, m in enumerate(re.finditer(re.escape(hint) + r'[.,]\d{2}', html)):
        if i >= 3:
            break
        s = max(0, m.start() - 45)
        print(f"    ...{html[s:m.end()+5]}...")
