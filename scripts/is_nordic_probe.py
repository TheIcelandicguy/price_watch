"""Probe Icelandic + Nordic retailers through the real extraction path."""
import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.extractor import try_jsonld, _looks_like_botwall, find_meta_price

URLS = [
    ("elko.is",          "https://elko.is/vorur/philips-phs5537-2022-sjonvarp-286633/24PHS553712"),
    ("ormsson.is",       "https://ormsson.is/product/aeg-thvottavel-lr612e840-8-kg/"),
    ("sindri.is",        "https://sindri.is/verkfærakassi-186-verkfæri-ibtgcbz186a"),
    ("husgagnahollin.is","https://husgagnahollin.is/vara/imperial-sofi-3s-velvet-svartur/"),
    ("rafland.is",       "https://rafland.is/samsung-55-qled-uhd-4k-sjonvarp-2023.html"),
    ("tolvutek.is",      "https://tolvutek.is/Tolvur-og-skjair/Aukahlutir/Mys-og-lyklabord/Logitech-M705-thradlaus-mus,-svort-og-gra/2_21770.action"),
    ("komplett.dk",      "https://www.komplett.dk/product/1140833/gaming/spiludstyr/gamingkeyboard/logitech-g-pro-gaming-tastatur-sort"),
    ("proshop.dk",       "https://www.proshop.dk/Mus/Logitech-G-PRO-X-SUPERLIGHT-2-Gaming-Mus-Optisk-5-knapper-Sort/3184282"),
    ("clasohlson.com",   "https://www.clasohlson.com/se/39-3883/p/39-3883"),
    ("biltema.dk",       "https://www.biltema.dk/varktoj/handvarktoj/varktojsnogler/skiftenogler/skiftenogle-pro-2000036548"),
    ("netto.is",         "https://netto.is/vorur/thurr-og-nidursuduvorur/nidursuduvorur/avextir-i-dosgleri/ananassneidar-p-20007209"),
]


def probe(host, url):
    try:
        r = cr.Session(impersonate="chrome131").get(url, timeout=30, allow_redirects=True)
        html = r.text or ""
        code = r.status_code
    except Exception as e:
        return f"{host:18} FETCH-ERR {type(e).__name__}: {str(e)[:45]}"
    if code >= 400:
        return f"{host:18} HTTP-{code} (len {len(html)})"
    if _looks_like_botwall(html):
        return f"{host:18} BOT-WALL"
    ld = try_jsonld(html)
    if ld and ld.get("price"):
        return f"{host:18} ✅ JSON-LD  {ld.get('price')} {ld.get('currency') or '?'} | {(ld.get('title') or '')[:38]}"
    mp, mc = find_meta_price(html)
    if mp:
        return f"{host:18} ✅ META     {mp} {mc or '?'}"
    has_ld = "application/ld+json" in html
    return f"{host:18} \U0001f527 NEEDS-SEL (len {len(html)}, ld+json={'y' if has_ld else 'n'})"


print(f"{'RETAILER':18} RESULT")
print("-" * 70)
for host, url in URLS:
    print(probe(host, url), flush=True)
