import sys, re
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from bs4 import BeautifulSoup

SITES = {
    "elko.is":   ("https://elko.is/vorur/philips-phs5537-2022-sjonvarp-286633/24PHS553712", "elko"),
    "rafland.is":("https://rafland.is/samsung-55-qled-uhd-4k-sjonvarp-2023.html", "rafl"),
    "sindri.is": ("https://sindri.is/verkfærakassi-186-verkfæri-ibtgcbz186a", "sind"),
    "biltema.dk":("https://www.biltema.dk/varktoj/handvarktoj/varktojsnogler/skiftenogler/skiftenogle-pro-2000036548", "bilt"),
}

for host, (url, _) in SITES.items():
    print(f"\n===== {host} =====")
    try:
        html = cr.Session(impersonate="chrome131").get(url, timeout=30).text
    except Exception as e:
        print("  fetch err", e); continue
    soup = BeautifulSoup(html, "html.parser")
    # meta tags
    for m in soup.select('meta[property*="price"], meta[itemprop="price"], meta[name*="price"]'):
        print(f"  META {m.get('property') or m.get('itemprop') or m.get('name')} = {m.get('content')!r}")
    # common price elements
    for sel in ['[itemprop=price]', '.price', '.product-price', '[class*=price]', '[data-price]']:
        el = soup.select_one(sel)
        if el:
            txt = (el.get('content') or el.get('data-price') or el.get_text(' ', strip=True))[:40]
            print(f"  CSS {sel:18} -> {txt!r}")
    # embedded JSON price patterns
    hits = re.findall(r'"(?:price|salePrice|currentPrice|priceAmount|amount)"\s*:\s*"?([0-9][0-9.,]{1,9})"?', html)
    print(f"  JSON price-ish hits (first 6): {hits[:6]}")
    # ld+json type breakdown
    types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
    print(f"  ld @types: {sorted(set(types))[:8]}")
