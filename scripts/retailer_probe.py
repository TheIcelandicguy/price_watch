"""Probe popular US/EU retailers through the real extractor fetch path.

For each URL: fetch via curl_cffi (chrome impersonation, fresh session),
then report bot-wall / JSON-LD price / needs-selector.
"""
import sys
from pathlib import Path

# Import the real extractor from this checkout, wherever it lives.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from curl_cffi import requests as cr
from custom_components.price_watch.extractor import try_jsonld, _looks_like_botwall

URLS = [
    # --- US ---
    ("amazon.com",      "https://www.amazon.com/SAMSUNG-Technology-Intelligent-Turbowrite-MZ-V9S1T0B/dp/B0DHLFWBQ1"),
    ("bestbuy.com",     "https://www.bestbuy.com/product/logitech-m310-wireless-optical-ambidextrous-mouse-wireless-peacock-blue/J7H7ZLVLQJ"),
    ("newegg.com",      "https://www.newegg.com/corsair-vengeance-rgb-32gb-ddr5-6000-cas-latency-cl36-desktop-memory-black/p/N82E16820236991"),
    ("walmart.com",     "https://www.walmart.com/ip/Mainstays-2-Slice-Toaster-with-6-Shade-Settings-and-Removable-Crumb-Tray-Black/1233603801"),
    ("target.com",      "https://www.target.com/p/keurig-k-classic-single-serve-k-cup-pod-coffee-maker-k50/-/A-50981282"),
    ("bhphotovideo.com","https://www.bhphotovideo.com/c/product/1731389-REG/sony_alpha_camera.html"),
    ("homedepot.com",   "https://www.homedepot.com/p/DEWALT-20V-MAX-Cordless-1-2-in-Drill-Driver-2-20V-1-3Ah-Batteries-Charger-and-Bag-DCD771C2/204279858"),
    ("lowes.com",       "https://www.lowes.com/pd/Kobalt-4-Amp-Oscillating-Multi-Tool/5001954453"),
    ("microcenter.com", "https://www.microcenter.com/product/679348/wd-black-sn850x-2tb-112-layer-bics5-tlc-nand-pcie-gen-4-x4-nvme-m2-internal-ssd"),
    # --- EU ---
    ("mediamarkt.de",   "https://www.mediamarkt.de/de/product/_samsung-gu55du7170-led-tv-flat-55-zoll-138-cm-uhd-4k-smart-tv-tizen-2924382.html"),
    ("currys.co.uk",    "https://www.currys.co.uk/products/lenovo-ideapad-slim-3-15.3-laptop-copilot-pc-snapdragon-x-256-gb-ssd-luna-grey-10284277.html"),
    ("argos.co.uk",     "https://www.argos.co.uk/product/9420399"),
    ("ikea.com",        "https://www.ikea.com/gb/en/p/billy-bookcase-white-00263850/"),
    ("leroymerlin.fr",  "https://www.leroymerlin.fr/produits/outillage/outillage-electroportatif/visseuse-et-tournevis-electrique/visseuse/perceuse-visseuse-sans-fil-bosch-18-v-1-5-ah-2-batteries-universaldrill-83656440.html"),
    ("coolblue.nl",     "https://www.coolblue.nl/product/905648/sony-wh-1000xm5-zwart.html"),
    ("elgiganten.dk",   "https://www.elgiganten.dk/product/tv-lyd-smart-home/horetelefoner-tilbehor/horetelefoner/apple-airpods-4-2024-tradlose-hovedtelefoner-med-opladningsetui-usb-c/825340"),
    ("wickes.co.uk",    "https://www.wickes.co.uk/Wickes-18V-2-x-1-5Ah-Li-ion-Cordless-Combi-Drill/p/223727"),
    ("otto.de",         "https://www.otto.de/p/hanseatic-waschmaschine-hwma714b-7-kg-1400-u-min-schnellwaschprogramm-startzeitvorwahl-1826859146/"),
]


def probe(host, url):
    try:
        s = cr.Session(impersonate="chrome")
        r = s.get(url, timeout=30, allow_redirects=True)
        html = r.text or ""
        code = r.status_code
        s.close()
    except Exception as e:
        return f"{host:18} FETCH-ERR  {type(e).__name__}: {str(e)[:60]}"

    if code >= 400:
        return f"{host:18} HTTP-{code}   (len {len(html)})"
    if _looks_like_botwall(html):
        return f"{host:18} BOT-WALL   (interstitial/captcha, len {len(html)})"

    ld = try_jsonld(html)
    if ld and ld.get("price"):
        return (f"{host:18} ✅ JSON-LD  {ld.get('price')} {ld.get('currency') or '?'}"
                f"  | {(ld.get('title') or '')[:42]}")
    has_ld = "application/ld+json" in html
    return (f"{host:18} 🔧 NEEDS-SEL (loaded len {len(html)}, "
            f"ld+json={'yes' if has_ld else 'no'}, jsonld_price=no)")


print(f"{'RETAILER':18} RESULT")
print("-" * 78)
for host, url in URLS:
    print(probe(host, url), flush=True)
