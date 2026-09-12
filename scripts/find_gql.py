import sys, re
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

SITES = [
    ("rafland", "https://rafland.is/samsung-55-qled-uhd-4k-sjonvarp-2023.html"),
    ("sindri", "https://sindri.is/verkfærakassi-186-verkfæri-ibtgcbz186a"),
]
for host, url in SITES:
    html = cr.Session(impersonate="chrome131").get(url, timeout=30).text
    print("=====", host, "=====")
    gql = sorted(set(re.findall(r"https?://[^\"'\s]*graphql[^\"'\s]*", html)))[:6]
    print(" graphql urls:", gql)
    hosts = sorted(set(re.findall(r"https?://([a-z0-9.\-]+\.(?:is|com|net|cloud|io))", html)))
    print(" foreign hosts:", [h for h in hosts if host not in h][:12])
    for kw in ["graphqlEndpoint", "backendUrl", "apiBase", "NEXT_PUBLIC", "magento",
               "storeCode", "store_code", "baseMediaUrl", "graphql", "/graphql"]:
        i = html.lower().find(kw.lower())
        if i >= 0:
            print(f"  {kw}: ...{html[i:i+90]!r}")
