"""Tests for the live-search junk filters (listing URLs + non-shop domains)."""

from __future__ import annotations

from custom_components.price_watch.coordinator_alternatives import (
    _is_non_shop_domain,
    _looks_like_listing_url,
    is_unusable_search_result,
)


def test_listing_url_search_and_category_pages():
    listing = [
        "https://www.amazon.com/dewalt-drill/s?k=dewalt+drill",
        "https://www.homedepot.com/b/Tools-Power-Tools-Drills/DEWALT/",
        "https://www.lowes.com/pl/power-tools/drills-drivers/drills/d",
        "https://www.ebay.com/sch/i.html?_nkw=dewalt+drill",
        "https://store.example.com/collections/drills",
        "https://shop.example.com/search?q=drill",
    ]
    for url in listing:
        assert _looks_like_listing_url(url) is True, url


def test_listing_url_allows_real_product_pages():
    products = [
        "https://www.amazon.com/DEWALT-DCD777C2/dp/B01N4O8Z9R",
        "https://www.newegg.com/p/N82E16820236991",
        "https://www.coolblue.nl/product/905648/sony-wh-1000xm5-zwart.html",
        "https://www.ikea.com/gb/en/p/billy-bookcase-white-00263850/",
        "https://thepowertoolstore.com/products/dewalt-dcd777c2",
    ]
    for url in products:
        assert _looks_like_listing_url(url) is False, url


def test_non_shop_domains_include_review_sites():
    for url in [
        "https://www.protoolreviews.com/best-dewalt-drill/",
        "https://www.popularmechanics.com/home/tools/g64272444/best-drills/",
        "https://www.rtings.com/headphones/reviews/sony/wh-1000xm5",
    ]:
        assert _is_non_shop_domain(url) is True, url


def test_real_shop_not_flagged_non_shop():
    for url in [
        "https://www.newegg.com/p/N82E16820236991",
        "https://thepowertoolstore.com/products/dewalt-dcd777c2",
        "https://www.planeo.com/power-tools/dewalt-18v-cordless-drill",
    ]:
        assert _is_non_shop_domain(url) is False, url


def test_is_unusable_combines_both_signals():
    assert is_unusable_search_result("https://www.amazon.com/x/s?k=drill") is True
    assert is_unusable_search_result("https://www.protoolreviews.com/x/") is True
    assert is_unusable_search_result("https://www.newegg.com/p/N82E16820236991") is False
