"""Tests for the Rafland preset (Magento GraphQL raw_json)."""

from __future__ import annotations

import json

from custom_components.price_watch.parsers import apply_custom_parser
from custom_components.price_watch.presets import find_preset, rafland

URL = "https://rafland.is/samsung-43-qled-uhd-4k-sjonvarp-2025.html"


def test_matches_product_url_only():
    assert rafland.matches(URL) is True
    assert rafland.matches("https://rafland.is/") is False
    assert rafland.matches("https://rafland.is/sjonvorp") is False  # category, no .html
    assert rafland.matches("https://elko.is/vorur/x") is False


def test_find_preset_picks_rafland():
    p = find_preset(URL)
    assert p is not None and p.NAME == "Rafland"


def test_build_parser_targets_url_key():
    parser = rafland.build_parser(URL)
    assert parser["type"] == "raw_json"
    assert parser["request_method"] == "POST"
    body = json.loads(parser["request_body"])
    assert body["variables"]["f"]["url_key"]["eq"] == "samsung-43-qled-uhd-4k-sjonvarp-2025"
    assert parser["request_headers"]["Store"] == "rafland_store_view"


def test_parses_graphql_response():
    parser = rafland.build_parser(URL)
    resp = json.dumps(
        {
            "data": {
                "products": {
                    "items": [
                        {
                            "name": "Samsung 43&quot; QLED UHD 4K Sjónvarp (2025)",
                            "sku": "SAM-TQ43Q7FAAUXXC",
                            "stock_status": "IN_STOCK",
                            "price_range": {
                                "minimum_price": {
                                    "final_price": {"value": 79995, "currency": "ISK"}
                                }
                            },
                        }
                    ]
                }
            }
        }
    )
    data = apply_custom_parser(resp, parser)
    assert data["price"] == 79995.0
    assert data["currency"] == "ISK"
    assert data["title"] == 'Samsung 43" QLED UHD 4K Sjónvarp (2025)'  # &quot; unescaped
    assert data["sku"] == "SAM-TQ43Q7FAAUXXC"
    assert data["in_stock"] is True
