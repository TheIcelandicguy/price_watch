"""URL and domain heuristics for search results.

Shared by the two places raw web hits turn into candidate listings — the
coordinator's alternatives discovery (coordinator_alternatives.py) and the
panel's live "Search & add" (websocket.py). Everything here is a pure
function of the URL string: no I/O, no Home Assistant.

The names keep their leading underscore from when they were private to
coordinator_alternatives.py; they are module-internal to the search
package, and both callers import them by name.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Per-hit snippet length forwarded in the DDG-only (no-AI) path. Without
# an AI to summarize, the raw snippet is handed to the panel as `notes`.
# One value for both search paths (coordinator alternatives and the
# panel's live search) so their rows look alike.
_DDG_SNIPPET_CHARS = 220


def _host_label(url: str) -> str:
    """Human-ish retailer label derived from a URL host.

    DDG raw hits carry no retailer field, so we default to the bare
    hostname ("www." stripped) — e.g. "newegg.com", "amazon.de". Good
    enough for the card until JSON-LD (if any) gives something better.
    """
    try:
        host = urlparse(url).netloc.lower()
    except (ValueError, TypeError):
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_domain(value: str) -> str:
    """Normalize a user-entered domain to a bare lowercase host.

    Accepts full URLs ("https://www.amazon.de/foo"), host-with-www, or
    bare hosts. Strips scheme, path, port, leading "www.", surrounding
    whitespace, and a trailing dot. Returns "" for junk so callers can
    drop empties.
    """
    if not value:
        return ""
    s = str(value).strip().lower()
    if not s:
        return ""
    if "://" in s:
        try:
            s = urlparse(s).netloc or s
        except (ValueError, TypeError):
            pass
    # Drop any path/port/userinfo that survived a bare "amazon.de/foo".
    s = s.split("/")[0].split("@")[-1].split(":")[0]
    s = s.strip().strip(".")
    if s.startswith("www."):
        s = s[4:]
    return s


def _host_excluded(url: str, excluded: set[str]) -> bool:
    """True if the URL's host equals or is a subdomain of an excluded host."""
    if not excluded:
        return False
    host = _normalize_domain(url)
    if not host:
        return False
    return any(host == ex or host.endswith("." + ex) for ex in excluded)


# Domains that are clearly NOT shops — code hosts, video, social, forums,
# Q&A, encyclopedias, docs/tutorial blogs. Used by Free-mode "Search & add"
# to flag raw web hits that can't be a seller. Conservative on purpose: we
# only mark the obvious non-commerce sites, so a real store never gets a
# false "not a store" badge (the inverse — an unflagged non-shop — is the
# safe failure: the user just judges it themselves, same as before).
_NON_SHOP_DOMAINS: frozenset[str] = frozenset(
    {
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "githubusercontent.com",
        "youtube.com",
        "youtu.be",
        "vimeo.com",
        "reddit.com",
        "quora.com",
        "stackoverflow.com",
        "stackexchange.com",
        "superuser.com",
        "serverfault.com",
        "wikipedia.org",
        "wikimedia.org",
        "fandom.com",
        "medium.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "pinterest.com",
        "tiktok.com",
        "linkedin.com",
        "readthedocs.io",
        "readthedocs.org",
        "instructables.com",
        "hackster.io",
        "hackaday.com",
        "hackaday.io",
        "dronebotworkshop.com",
        "randomnerdtutorials.com",
        "home-assistant.io",
        "lastminuteengineers.com",
        "circuitdigest.com",
        "electronicshub.org",
        "allaboutcircuits.com",
        "makeuseof.com",
        "howtogeek.com",
        "wled.ge",
        # Review / editorial / spec sites — surface heavily for product
        # queries ("best X", "X review") but never sell anything. None of
        # these host a checkout, so dropping them only removes dead rows.
        "protoolreviews.com",
        "popularmechanics.com",
        "rtings.com",
        "tomsguide.com",
        "tomshardware.com",
        "techradar.com",
        "cnet.com",
        "theverge.com",
        "engadget.com",
        "pcmag.com",
        "gsmarena.com",
        "notebookcheck.net",
        "trustedreviews.com",
        "wirecutter.com",
        "nytimes.com",
        "consumerreports.org",
        "which.co.uk",
        "digitaltrends.com",
        "androidauthority.com",
        "thespruce.com",
        "familyhandyman.com",
        "bobvila.com",
    }
)

# Subdomain prefixes that signal documentation, community, or editorial
# content rather than a product listing — none of these ever host a
# checkout. Catches doc/wiki/forum hosts (kno.wled.ge, docs.espressif.com,
# community.home-assistant.io) that aren't worth denylisting individually.
# Conservative: a store never lives at docs./forum./help., so this can't
# false-flag a real seller's product page.
_NON_SHOP_SUBDOMAIN_PREFIXES: tuple[str, ...] = (
    "docs.",
    "doc.",
    "kno.",
    "wiki.",
    "blog.",
    "forum.",
    "forums.",
    "community.",
    "help.",
    "support.",
    "learn.",
    "kb.",
)


def _is_non_shop_domain(url: str) -> bool:
    """True if the URL's host is a known non-commerce site (heuristic).

    Two signals, both conservative:
      1. Suffix match against the curated denylist, so subdomains
         (gist.github.com, m.youtube.com, en.wikipedia.org) are caught.
      2. A documentation/community subdomain prefix (docs., kno., forum.,
         help., ...) — those hosts never sell a product.

    An unrecognized host returns False (treated as a possible shop),
    which is the safe default.
    """
    host = _normalize_domain(url)
    if not host:
        return False
    if any(host == nd or host.endswith("." + nd) for nd in _NON_SHOP_DOMAINS):
        return True
    return host.startswith(_NON_SHOP_SUBDOMAIN_PREFIXES)


# Path fragments that mark a search-results or category/browse page rather than
# a single product — these never carry one trackable price (Amazon /s?k=,
# Home Depot /b/, Lowe's /pl/, eBay /sch/, Shopify /collections/, etc.).
_LISTING_PATH_MARKERS: tuple[str, ...] = (
    "/b/",
    "/pl/",
    "/sch/",
    "/search",
    "/browse/",
    "/category/",
    "/categories/",
    "/collections/",
    "/c/",
    "/shop/",
)
# Query keys that mark a search (?k=, ?q=, ?query=, ...).
_LISTING_QUERY_KEYS: tuple[str, ...] = (
    "k=",
    "q=",
    "query=",
    "searchterm=",
    "keyword=",
    "searchkeyword=",
)


def _looks_like_listing_url(url: str) -> bool:
    """True if the URL is a search/category/browse page, not a single product.

    Conservative: matches well-known listing path fragments and search query
    keys. A real product URL (Amazon /dp/, /gp/product/, retailer /product/…)
    has none of these, so this won't drop a trackable page.
    """
    if not url:
        return False
    try:
        parts = urlparse(url.lower())
    except ValueError:
        return False
    path, query = parts.path, parts.query
    if any(marker in path for marker in _LISTING_PATH_MARKERS):
        return True
    # Amazon search: path ends with "/s" and carries a search query.
    if (path == "/s" or path.endswith("/s")) and "k=" in query:
        return True
    if any(query == k or query.startswith(k) or ("&" + k) in query for k in _LISTING_QUERY_KEYS):
        return True
    return False


def is_unusable_search_result(url: str) -> bool:
    """Drop signal for live search / alternatives: a non-shop domain (review,
    spec, wiki, video) OR a search/category page — neither is a trackable,
    priceable product listing."""
    return _is_non_shop_domain(url) or _looks_like_listing_url(url)
