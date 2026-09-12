"""Try diverse impersonation profiles + locale headers against the blocked sites."""
import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.extractor import try_jsonld, _looks_like_botwall

PROFILES = ["chrome131", "chrome136", "chrome146", "chrome131_android",
            "safari180", "firefox144", "edge101"]

URLS = [
    ("bestbuy.com",     "https://www.bestbuy.com/product/logitech-m310-wireless-optical-ambidextrous-mouse-wireless-peacock-blue/J7H7ZLVLQJ", "en-US"),
    ("bhphotovideo.com","https://www.bhphotovideo.com/c/product/1731389-REG/sony_alpha_camera.html", "en-US"),
    ("homedepot.com",   "https://www.homedepot.com/p/DEWALT-20V-MAX-Cordless-1-2-in-Drill-Driver-2-20V-1-3Ah-Batteries-Charger-and-Bag-DCD771C2/204279858", "en-US"),
    ("microcenter.com", "https://www.microcenter.com/product/679348/wd-black-sn850x-2tb-112-layer-bics5-tlc-nand-pcie-gen-4-x4-nvme-m2-internal-ssd", "en-US"),
    ("leroymerlin.fr",  "https://www.leroymerlin.fr/produits/outillage/outillage-electroportatif/visseuse-et-tournevis-electrique/visseuse/perceuse-visseuse-sans-fil-bosch-18-v-1-5-ah-2-batteries-universaldrill-83656440.html", "fr-FR"),
    ("elgiganten.dk",   "https://www.elgiganten.dk/product/tv-lyd-smart-home/horetelefoner-tilbehor/horetelefoner/apple-airpods-4-2024-tradlose-hovedtelefoner-med-opladningsetui-usb-c/825340", "da-DK"),
    ("otto.de",         "https://www.otto.de/p/hanseatic-waschmaschine-hwma714b-7-kg-1400-u-min-schnellwaschprogramm-startzeitvorwahl-1826859146/", "de-DE"),
    ("target.com",      "https://www.target.com/p/keurig-k-classic-single-serve-k-cup-pod-coffee-maker-k50/-/A-50981282", "en-US"),
    ("mediamarkt.de",   "https://www.mediamarkt.de/de/product/_samsung-gu55du7170-led-tv-flat-55-zoll-138-cm-uhd-4k-smart-tv-tizen-2924382.html", "de-DE"),
    ("amazon.com",      "https://www.amazon.com/SAMSUNG-Technology-Intelligent-Turbowrite-MZ-V9S1T0B/dp/B0DHLFWBQ1", "en-US"),
]


def attempt(url, profile, lang):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": f"{lang},en;q=0.7",
        "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1",
    }
    try:
        s = cr.Session(impersonate=profile)
        r = s.get(url, headers=headers, timeout=25, allow_redirects=True)
        html = r.text or ""
        s.close()
        return r.status_code, html
    except Exception as e:
        return f"ERR:{type(e).__name__}", ""


for host, url, lang in URLS:
    line = f"{host:18}"
    win = None
    for p in PROFILES:
        code, html = attempt(url, p, lang)
        ok = isinstance(code, int) and code == 200 and not _looks_like_botwall(html) and len(html) > 5000
        tag = f"{p}:{code}"
        if ok and win is None:
            ld = try_jsonld(html)
            price = (ld or {}).get("price")
            win = f"  >>> WIN {p} ({code}) jsonld_price={price} len={len(html)} ld+json={'application/ld+json' in html}"
        line += f" {tag}"
    print(line, flush=True)
    if win:
        print(win, flush=True)
