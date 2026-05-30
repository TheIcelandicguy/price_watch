"""Region/shipping heuristics for alternative search results.

The AI provides a soft `ships_to_user_region` signal per alternative,
but it gets this wrong sometimes — most often confidently saying
"yes" for retailers that technically have international shipping but
in practice don't deliver electronics to Iceland (or charge $80+ to
do so). This module encodes hard-won "trust me" knowledge that
overrides the AI when we're more confident than it is.

The heuristic operates on the URL + retailer name + AI's guess, and
returns one of three outcomes:
- bool (True/False): a confident override of the AI's guess
- None: no opinion, leave the AI's guess alone

Philosophy:
- We never override the AI from None → True. If we're not sure, leave
  it as unknown; positive false claims are worse than null.
- We DO override the AI from True → False when we know the retailer
  has well-documented shipping restrictions to the user's region.
- We override AI from None → False for known-bad-fit retailers, so
  the panel can show a "Doesn't ship" badge even when the AI shrugged.
- The country code is ISO 3166-1 alpha-2 ("IS", "NO", "US", etc.).
"""
from __future__ import annotations

from urllib.parse import urlparse

# Nordic country group — these retailers ship within the Nordics
# generally (and from each other's countries). Not all do, but most
# Nordic electronics retailers (Komplett, Elkjøp, NetOnNet, Power,
# Elgiganten, Proshop, Inet) have intra-Nordic shipping arrangements.
_NORDIC_COUNTRIES = frozenset({"IS", "NO", "SE", "DK", "FI"})

# EU country group — for retailers like Amazon DE / .fr / .es / .it
# that mostly ship throughout the EU. Iceland is in EFTA, not EU, so
# IS is NOT in this set — EU retailers often skip IS or charge a
# significant surcharge.
_EU_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
    "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT",
    "RO", "SK", "SI", "ES", "SE",
})

# Country code → set of TLDs that retailers in that country use.
# When a URL's TLD matches the user's country TLD, that's a strong
# positive signal.
_COUNTRY_TLDS: dict[str, frozenset[str]] = {
    "IS": frozenset({"is"}),
    "NO": frozenset({"no"}),
    "SE": frozenset({"se"}),
    "DK": frozenset({"dk"}),
    "FI": frozenset({"fi"}),
    "DE": frozenset({"de"}),
    "FR": frozenset({"fr"}),
    "ES": frozenset({"es"}),
    "IT": frozenset({"it"}),
    "UK": frozenset({"uk", "co.uk"}),
    "GB": frozenset({"uk", "co.uk"}),
    "US": frozenset({"com"}),  # weak signal, .com is global
    "CA": frozenset({"ca"}),
    "AU": frozenset({"au", "com.au"}),
}

# Hostname suffixes for known retailers that are US-only (no
# international shipping for typical electronics) for users outside
# the US. Lowercase, no leading dot.
_US_ONLY_RETAILERS = frozenset({
    "newegg.com",
    "bestbuy.com",
    "microcenter.com",
    "bhphotovideo.com",
    "frys.com",
    "tigerdirect.com",
    "walmart.com",  # ships internationally only for select items
})

# Retailers known to ship globally including to Iceland and other
# small markets. These get overridden to True for almost any user.
_GLOBAL_SHIPPERS = frozenset({
    "aliexpress.com",
    "banggood.com",
    "ebay.com",
    # Amazon's .com sometimes ships to IS but with high costs +
    # often refuses electronics — DO NOT add amazon.com here.
})

# Hostname suffixes that are price-comparison / aggregator sites,
# not retailers. We shouldn't show "ships to X" for these — they
# aren't selling anything directly. Override to None (unknown) to
# suppress the AI's guess and the panel won't show a badge.
_AGGREGATORS = frozenset({
    "pangoly.com",
    "prisjakt.no",
    "prisjakt.se",
    "pricerunner.com",
    "pricerunner.dk",
    "geizhals.de",
    "geizhals.eu",
    "idealo.de",
    "idealo.co.uk",
    "kelkoo.com",
    "shopping.google.com",
})


def _extract_host(url: str) -> str:
    """Return the lowercase hostname of a URL, '' on parse failure."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        # Strip leading "www." for matching consistency
        if host.startswith("www."):
            host = host[4:]
        return host
    except (ValueError, AttributeError):
        return ""


def _tld_of(host: str) -> str:
    """Return the last TLD label of a hostname, '' on empty."""
    if not host or "." not in host:
        return ""
    parts = host.rsplit(".", 2)
    # Handle 2-part TLDs like .co.uk specially
    if len(parts) >= 2 and parts[-2] == "co" and parts[-1] in ("uk", "nz", "jp"):
        return f"{parts[-2]}.{parts[-1]}"
    return parts[-1]


def evaluate_shipping(
    url: str,
    retailer: str,
    user_region: str,
    ai_guess: bool | None,
) -> bool | None:
    """Decide if a retailer ships to `user_region`.

    Returns the heuristic's final answer:
    - bool: confident override (or confirmation) of AI's guess
    - None: no opinion (leave AI's guess in place)

    The caller should use this return value as the FINAL
    `ships_to_user_region` unless it's None, in which case fall back
    to the AI's guess.

    Rules (in order of precedence — first match wins):
    1. No user_region → can't evaluate, return None
    2. Aggregator hostname → return None (suppress, not relevant)
    3. Global shipper hostname → return True
    4. US-only retailer + user is non-US → return False
    5. Matching country TLD → return True
    6. Nordic TLD + user is Nordic → return True
    7. EU TLD + user is in EU → return True (Amazon DE etc. for EU users)
    8. Otherwise → return None (let AI's guess stand)
    """
    if not user_region:
        return None

    user_region = user_region.upper()
    host = _extract_host(url)
    if not host:
        return None

    # Rule 2: aggregator
    for suffix in _AGGREGATORS:
        if host == suffix or host.endswith("." + suffix):
            return None  # suppress entirely

    # Rule 3: global shipper
    for suffix in _GLOBAL_SHIPPERS:
        if host == suffix or host.endswith("." + suffix):
            return True

    # Rule 4: US-only retailer, user not in US
    if user_region != "US":
        for suffix in _US_ONLY_RETAILERS:
            if host == suffix or host.endswith("." + suffix):
                return False

    tld = _tld_of(host)

    # Rule 5: matching country TLD
    country_tlds = _COUNTRY_TLDS.get(user_region, frozenset())
    if tld in country_tlds and tld != "com":  # .com is too weak alone
        return True

    # Rule 6: Nordic TLDs are interchangeable within Nordic group
    if user_region in _NORDIC_COUNTRIES:
        for nordic in _NORDIC_COUNTRIES:
            nordic_tlds = _COUNTRY_TLDS.get(nordic, frozenset())
            if tld in nordic_tlds and tld != "com":
                return True

    # Rule 7: EU TLDs for EU users (excluding the country match
    # already handled above)
    if user_region in _EU_COUNTRIES:
        for eu in _EU_COUNTRIES:
            eu_tlds = _COUNTRY_TLDS.get(eu, frozenset())
            if tld in eu_tlds and tld != "com":
                return True

    # No rule fired — leave AI's guess in place
    return None


def apply_to_alternative(alt, user_region: str) -> None:
    """Mutate alt.ships_to_user_region in place based on the heuristic.

    The heuristic can OVERRIDE the AI's guess in both directions:
    - heuristic says True  → set True regardless of AI
    - heuristic says False → set False regardless of AI
    - heuristic says None  → leave AI's guess as-is

    This is intentional: the heuristic encodes ground truth that the
    AI doesn't know (Newegg won't ship to IS, .is TLD definitely
    ships to IS), and we want it to win.
    """
    if not user_region:
        return
    decision = evaluate_shipping(
        url=alt.url,
        retailer=alt.retailer,
        user_region=user_region,
        ai_guess=alt.ships_to_user_region,
    )
    if decision is not None:
        alt.ships_to_user_region = decision