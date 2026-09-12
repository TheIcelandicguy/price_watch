import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
import re, json

print("############ HUSA ############")
html = cr.get(
    "https://www.husa.is/byggingarefni-vorur/timbur/fragangslistar/thakbrunalistar/thakbrlisti-45x95-furastar/",
    impersonate="chrome", timeout=30,
).text
m = re.search(r'<span class="([^"]*)">\s*ÞAKBRÚNALISTI FURA FRÆSTUR', html)
print("desc span class:", m.group(1) if m else "NOT FOUND")
m2 = re.search(r'<span class="main-sku">([0-9]+)</span>', html)
print("main-sku:", m2.group(1) if m2 else None)
# wider context around the description span
i = html.find("ÞAKBRÚNALISTI FURA FRÆSTUR")
print("desc context:", re.sub(r"\s+", " ", html[i-90:i+50]))

print("\n############ BYKO ############")
bhtml = cr.get("https://byko.is/vara/fura-alhef-45-x95-ab-gagnv-248063", impersonate="chrome", timeout=30).text
d = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', bhtml, re.S).group(1))
p = d["props"]["pageProps"]["product"]
for k in ("name", "shortDescription", "description"):
    v = p.get(k)
    print(f"{k}: type={type(v).__name__} ->", (str(v)[:260] if v else v))
