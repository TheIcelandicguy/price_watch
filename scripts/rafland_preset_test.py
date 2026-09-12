import sys, json
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr
from custom_components.price_watch.parsers import apply_custom_parser

ENDPOINT = "https://backend-v2-ht.roanuz.com/graphql"
FILTER_Q = (
    'query($f:ProductAttributeFilterInput){products(filter:$f){items{'
    'name sku stock_status '
    'price_range{minimum_price{final_price{value currency}}}}}}'
)
url_key = "samsung-43-qled-uhd-4k-sjonvarp-2025"  # a live product

parser = {
    "type": "raw_json",
    "url": ENDPOINT,
    "request_method": "POST",
    "request_body": json.dumps({"query": FILTER_Q, "variables": {"f": {"url_key": {"eq": url_key}}}}),
    "request_headers": {"Content-Type": "application/json", "Store": "rafland_store_view"},
    "selectors": {
        "title": "data.products.items.0.name",
        "price": "data.products.items.0.price_range.minimum_price.final_price.value",
        "currency": "data.products.items.0.price_range.minimum_price.final_price.currency",
        "sku": "data.products.items.0.sku",
        "stock_count": "data.products.items.0.stock_status",
    },
    "transforms": {"price": "float"},
    "default_currency": "ISK",
    "default_retailer": "Rafland",
    "min_price": 100,
}

# Fetch the GraphQL response the way extract_product would, then parse it.
resp = cr.Session(impersonate="chrome131").post(
    parser["url"], data=parser["request_body"], headers=parser["request_headers"], timeout=30
).text
print("raw resp:", resp[:160])
print("parsed:", apply_custom_parser(resp, parser))
