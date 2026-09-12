"""Find the price data source for rafland.is / sindri.is (platform + API/JSON)."""
import sys, re
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

SITES = {
    "rafland.is": ("https://rafland.is/samsung-55-qled-uhd-4k-sjonvarp-2023.html", "Samsung 55"),
    "sindri.is":  ("https://sindri.is/verkfærakassi-186-verkfæri-ibtgcbz186a", "186"),
}

PLATFORM_MARKERS = {
    "Magento": ["Magento", "mage/", "/static/version", "requirejs/", "data-mage-init"],
    "WooCommerce": ["woocommerce", "wp-content", "wc-ajax"],
    "Shopify": ["cdn.shopify.com", "Shopify.", "/products/"],
    "Next.js": ["__NEXT_DATA__", "/_next/"],
    "Nuxt": ["__NUXT__", "/_nuxt/"],
    "Salesforce/SFCC": ["demandware", "dwstatic", "/on/demandware"],
    "PrestaShop": ["prestashop", "/themes/"],
}

for host, (url, hint) in SITES.items():
    print(f"\n========== {host} ==========")
    try:
        html = cr.Session(impersonate="chrome131").get(url, timeout=30).text
    except Exception as e:
        print("  fetch err", e); continue
    print(f"  len={len(html)}")
    # platform
    plats = [p for p, marks in PLATFORM_MARKERS.items() if any(m in html for m in marks)]
    print(f"  platform markers: {plats or '(none detected)'}")
    # api-ish URLs referenced in the page
    apis = sorted(set(re.findall(r'["\'](/(?:api|rest|graphql|ajax|index\.php/rest)[^"\'\s]{0,60})', html)))[:12]
    print(f"  api-ish paths: {apis}")
    # absolute api endpoints
    abs_apis = sorted(set(re.findall(r'https?://[^"\'\s]*?/(?:api|rest|graphql)[^"\'\s]{0,40}', html)))[:8]
    print(f"  abs api endpoints: {abs_apis}")
    # any number near 'price' / 'verð' (Icelandic for price) / kr
    for kw in ['"price"', 'priceAmount', 'verð', 'final_price', 'special_price', 'productId', 'sku', 'data-price']:
        idx = html.find(kw)
        if idx >= 0:
            print(f"  found {kw!r}: ...{html[max(0,idx-10):idx+60]!r}...")
    # data layer / product id
    for m in re.finditer(r'(productId|product_id|"id"|sku|entity_id)["\']?\s*[:=]\s*["\']?(\d{2,9})', html):
        print(f"  id-ish: {m.group(1)}={m.group(2)}")
        break
