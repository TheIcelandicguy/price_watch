"""Confirm impersonate=chrome131 (no extra headers) unblocks BestBuy/B&H AND
does not regress the 7 already-working sites. Mirrors the integration's fetch."""
import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.extractor import try_jsonld, _looks_like_botwall

URLS = [
    ("bestbuy.com NEW",  "https://www.bestbuy.com/product/logitech-m310-wireless-optical-ambidextrous-mouse-wireless-peacock-blue/J7H7ZLVLQJ"),
    ("bhphoto.com NEW",  "https://www.bhphotovideo.com/c/product/1731389-REG/sony_alpha_camera.html"),
    ("newegg WORKING",   "https://www.newegg.com/corsair-vengeance-rgb-32gb-ddr5-6000-cas-latency-cl36-desktop-memory-black/p/N82E16820236991"),
    ("currys WORKING",   "https://www.currys.co.uk/products/lenovo-ideapad-slim-3-15.3-laptop-copilot-pc-snapdragon-x-256-gb-ssd-luna-grey-10284277.html"),
    ("argos WORKING",    "https://www.argos.co.uk/product/9420399"),
    ("ikea WORKING",     "https://www.ikea.com/gb/en/p/billy-bookcase-white-00263850/"),
    ("coolblue WORKING", "https://www.coolblue.nl/product/905648/sony-wh-1000xm5-zwart.html"),
    ("wickes WORKING",   "https://www.wickes.co.uk/Wickes-18V-2-x-1-5Ah-Li-ion-Cordless-Combi-Drill/p/223727"),
    ("walmart WORKING",  "https://www.walmart.com/ip/Mainstays-2-Slice-Toaster-with-6-Shade-Settings-and-Removable-Crumb-Tray-Black/1233603801"),
    ("amazon.de KNOWN",  "https://www.amazon.de/-/en/gp/product/B0DTGNB9Q5/ref=ox_sc_act_title_1?smid=A3JWKAKR8XB7XF&th=1"),
]

for label, url in URLS:
    try:
        # mirror the integration: impersonate + fresh session, no extra headers
        r = cr.Session(impersonate="chrome131").get(url, timeout=30, allow_redirects=True)
        html = r.text or ""
        if r.status_code != 200:
            print(f"{label:18} HTTP-{r.status_code}")
            continue
        if _looks_like_botwall(html):
            print(f"{label:18} BOT-WALL")
            continue
        ld = try_jsonld(html)
        price = (ld or {}).get("price")
        print(f"{label:18} 200  jsonld_price={price}  len={len(html)}")
    except Exception as e:
        print(f"{label:18} ERR {type(e).__name__}: {str(e)[:50]}")
