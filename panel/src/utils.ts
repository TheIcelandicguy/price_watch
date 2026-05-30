/**
 * Helpers for the Price Watch panel.
 *
 * Mostly formatting + the central "build TrackedProduct[] from hass.states"
 * function. Keeping the latter here (not on the panel element) so it's
 * easy to test in isolation.
 */

import type {
  Alternative,
  HomeAssistant,
  Listing,
  TrackedProduct,
  PriceHistoryPoint,
} from "./types.js";

// All Price Watch sensors share the unique_id pattern `{entry_id}_{key}`.
// The price sensor in particular carries most of the panel-relevant
// metadata as attributes (title, image_url, retailer, history, etc.),
// so we centre the aggregation on it.
const PRICE_SUFFIX = "_price";
const PRICE_LOCAL_SUFFIX = "_price_local";
const LOWEST_SUFFIX = "_lowest";
const HIGHEST_SUFFIX = "_highest";
const TARGET_DIFF_SUFFIX = "_target_diff";
const STOCK_COUNT_SUFFIX = "_stock_count";
const IN_STOCK_SUFFIX = "_in_stock";
const DISCONTINUED_SUFFIX = "_discontinued";

/**
 * Convert a HA state value to a finite number, or null when the state
 * is "unknown" / "unavailable" / not parseable. Critical for sensors
 * that legitimately have no value yet (e.g. price_local before FX
 * rates load on first install).
 */
export function stateNumber(value: string | undefined | null): number | null {
  if (value == null || value === "unknown" || value === "unavailable") {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * "yes"-ish / "no"-ish state → boolean. Returns null for unknown so
 * the UI can render a separate "unknown" state instead of
 * misleadingly showing "out of stock" for a sensor that hasn't
 * reported yet.
 */
export function stateBool(value: string | undefined | null): boolean | null {
  if (value == null || value === "unknown" || value === "unavailable") {
    return null;
  }
  if (value === "on" || value === "true") return true;
  if (value === "off" || value === "false") return false;
  return null;
}

/**
 * Build the unique_id we'd expect for a given config_entry_id + key
 * pair. Sensors register against this. The entity registry, accessed
 * via callWS('config/entity_registry/list'), maps these to
 * user-visible entity_ids.
 */
export function uniqueIdFor(entryId: string, key: string): string {
  return `${entryId}_${key}`;
}

/**
 * Format a price + currency for display. Uses the browser's
 * Intl.NumberFormat where possible so locale-correct grouping and
 * decimal characters fall out naturally.
 *
 * Returns `—` (em-dash) for null prices, since the UI treats absence
 * as meaningful — "we have no observation for this product yet".
 */
export function formatPrice(
  value: number | null,
  currency: string | null,
  locale = "en"
): string {
  if (value == null) return "—";
  if (!currency) return value.toLocaleString(locale);
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    // Intl throws on unrecognised currency codes (rare: symbol-only
    // values from sites that don't expose ISO codes). Fall back to a
    // plain number + the symbol as suffix.
    return `${value.toLocaleString(locale, { maximumFractionDigits: 2 })} ${currency}`;
  }
}

/**
 * Relative time formatter. "2 hours ago", "3 days ago", etc. Used for
 * the "last check" line at the bottom of each card.
 */
export function formatRelative(iso: string | null, locale = "en"): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffMs = Date.now() - then;
  const diffSec = Math.round(diffMs / 1000);
  const abs = Math.abs(diffSec);

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  if (abs < 60) return rtf.format(-diffSec, "second");
  if (abs < 3600) return rtf.format(-Math.round(diffSec / 60), "minute");
  if (abs < 86_400) return rtf.format(-Math.round(diffSec / 3600), "hour");
  if (abs < 2_592_000) return rtf.format(-Math.round(diffSec / 86_400), "day");
  return rtf.format(-Math.round(diffSec / 2_592_000), "month");
}

/**
 * Read an attribute that should be a list of dicts (the price sensor's
 * `price_history`). Defensive: returns [] for malformed values so the
 * sparkline renderer doesn't need null-check the array itself.
 */
function readHistory(value: unknown): PriceHistoryPoint[] {
  if (!Array.isArray(value)) return [];
  const out: PriceHistoryPoint[] = [];
  for (const item of value) {
    if (
      item != null &&
      typeof item === "object" &&
      "price" in item &&
      "ts" in item
    ) {
      const rec = item as Record<string, unknown>;
      const price = typeof rec.price === "number" ? rec.price : null;
      if (price == null) continue;
      out.push({
        ts: String(rec.ts ?? ""),
        price,
        currency: String(rec.currency ?? ""),
        in_stock: rec.in_stock !== false,  // default true for older records
      });
    }
  }
  return out;
}

/**
 * Read a registry lookup table mapping unique_id → entity_id, built
 * once and passed in. This is faster than scanning the registry for
 * each product on each render.
 */
export interface EntityRegistryIndex {
  byUniqueId: Map<string, string>;
}

/**
 * Construct TrackedProduct[] from the current hass state plus a
 * pre-built entity registry index. Skips entries that don't have at
 * least a price sensor — those are most likely in setup_retry.
 *
 * Sort order: discontinued products go to the bottom, then alphabetical
 * by title so the UI is stable across renders.
 */
/**
 * Coerce raw `alternatives` sensor attribute into Alternative objects.
 * Defensive against missing/malformed entries — the AI synthesizer
 * is allowed to return weird shapes occasionally, and we'd rather
 * drop bad rows than crash the panel.
 */
function readAlternatives(value: unknown): Alternative[] {
  if (!Array.isArray(value)) return [];
  const out: Alternative[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== "object") continue;
    const obj = raw as Record<string, unknown>;
    const title = typeof obj.title === "string" ? obj.title : "";
    const url = typeof obj.url === "string" ? obj.url : "";
    if (!title || !url) continue;
    out.push({
      title,
      url,
      price: typeof obj.price === "number" ? obj.price : null,
      currency: typeof obj.currency === "string" ? obj.currency : "",
      retailer: typeof obj.retailer === "string" ? obj.retailer : "",
      imageUrl:
        typeof obj.image_url === "string" && obj.image_url
          ? obj.image_url
          : null,
      confidence:
        typeof obj.confidence === "number"
          ? Math.max(0, Math.min(1, obj.confidence))
          : 0,
      notes: typeof obj.notes === "string" ? obj.notes : "",
      shipsToUserRegion:
        typeof obj.ships_to_user_region === "boolean"
          ? obj.ships_to_user_region
          : null,
    });
  }
  // Sort high-confidence first, then cheapest first within same
  // confidence. Mirrors the backend sort but reapplied here so the
  // panel still does the right thing if the backend returns them
  // out of order.
  out.sort((a, b) => {
    if (b.confidence !== a.confidence) return b.confidence - a.confidence;
    const ap = a.price ?? Number.POSITIVE_INFINITY;
    const bp = b.price ?? Number.POSITIVE_INFINITY;
    return ap - bp;
  });
  return out;
}

/**
 * Parse a Price Watch unique_id into its constituent pieces.
 *
 * Two patterns the integration produces:
 *   - Legacy/primary: `{entry_id}_{key}`
 *     (key is one of price/lowest/highest/target_diff/stock_count/
 *      price_local/in_stock/discontinued/refresh_now/photo)
 *   - Secondary listing: `{entry_id}_l_{12-hex}_{key}`
 *     (listing_id has the form `l_<12-hex>`; see coordinator's
 *      _new_listing_id and _derive_listing_id)
 *
 * entry_id is a ULID — 26 chars, no underscores — so the first
 * underscore reliably terminates it. Within the remainder, we
 * recognize a secondary listing by the `l_` prefix; everything else
 * is treated as a primary key. No key the integration emits starts
 * with `l_`, so this disambiguation is safe.
 *
 * Returns `null` when the unique_id has no underscore at all (not
 * one of ours; skipped by the caller).
 */
export function parseUniqueId(
  uniqueId: string
): { entryId: string; listingId: string | null; key: string } | null {
  const firstUnderscore = uniqueId.indexOf("_");
  if (firstUnderscore < 0) return null;
  const entryId = uniqueId.slice(0, firstUnderscore);
  const rest = uniqueId.slice(firstUnderscore + 1);

  // Secondary-listing prefix: `l_<hex>_<key>`. The hex segment is
  // [0-9a-z]+ (12 chars in practice, but permissive in case a future
  // generator changes width). The key that follows is captured
  // verbatim — the consumer maps it to fields.
  const m = /^(l_[0-9a-z]+)_(.+)$/.exec(rest);
  if (m) {
    return { entryId, listingId: m[1], key: m[2] };
  }
  return { entryId, listingId: null, key: rest };
}

/**
 * Build a single Listing object from a per-listing keyMap.
 *
 * The keyMap groups all entities belonging to one listing of one
 * product, keyed by short key ("price", "in_stock", etc.) → entity_id.
 * The price entity is the authoritative source — its state attributes
 * carry retailer, currency, URL, history, last_check, etc. Other
 * entities (in_stock, discontinued) supply their own state for
 * sensors that need an authoritative boolean rather than parsing the
 * attribute mirror.
 *
 * Returns null when the keyMap has no price entity (the listing
 * wouldn't be meaningful without one — happens transiently when a
 * coordinator hasn't yet created sensors for a freshly-added listing).
 */
function buildListing(
  hass: HomeAssistant,
  keyMap: Map<string, string>,
  listingId: string,
  isPrimary: boolean
): Listing | null {
  const priceEntity = keyMap.get("price");
  if (!priceEntity) return null;
  const priceState = hass.states[priceEntity];
  if (!priceState) return null;

  const attrs = priceState.attributes;
  const listing: Listing = {
    listingId,
    isPrimary,
    retailer: typeof attrs.retailer === "string" ? attrs.retailer : null,
    url: typeof attrs.product_url === "string" ? attrs.product_url : null,
    price: stateNumber(priceState.state),
    currency:
      typeof attrs.unit_of_measurement === "string"
        ? attrs.unit_of_measurement
        : typeof attrs.currency === "string"
        ? attrs.currency
        : "",
    inStock: null,
    discontinued: attrs.discontinued === true,
    stockCount:
      typeof attrs.stock_count === "number" ? attrs.stock_count : null,
    lastCheck:
      typeof attrs.last_check === "string" ? attrs.last_check : null,
    history: readHistory(attrs.price_history),
    entityIds: { price: priceEntity },
  };

  // in_stock binary sensor — authoritative over the attribute mirror.
  const inStockEntity = keyMap.get("in_stock");
  if (inStockEntity) {
    const s = hass.states[inStockEntity];
    if (s) {
      listing.inStock = stateBool(s.state);
      listing.entityIds.inStock = inStockEntity;
    }
  }

  // discontinued binary sensor — authoritative over the attribute mirror.
  const discontinuedEntity = keyMap.get("discontinued");
  if (discontinuedEntity) {
    const s = hass.states[discontinuedEntity];
    if (s) {
      const flag = stateBool(s.state);
      if (flag != null) listing.discontinued = flag;
      listing.entityIds.discontinued = discontinuedEntity;
    }
  }

  return listing;
}

export function buildProducts(
  hass: HomeAssistant,
  registry: EntityRegistryIndex
): TrackedProduct[] {
  // Group registry entries by entry_id, splitting primary (legacy
  // unique_id) keys from secondary-listing-prefixed keys. Each entry
  // gets a `legacy` map for its primary listing's entities and a
  // `listings` nested map for secondary listings, keyed by listing_id.
  //
  // entry_id is a ULID — no underscores — so parseUniqueId reliably
  // splits the first underscore as entry boundary. The remainder is
  // either a plain key (primary) or `l_<hex>_<key>` (secondary).
  interface EntryBuckets {
    legacy: Map<string, string>;
    listings: Map<string, Map<string, string>>;
  }
  const byEntry = new Map<string, EntryBuckets>();

  for (const [uniqueId, entityId] of registry.byUniqueId) {
    const parsed = parseUniqueId(uniqueId);
    if (!parsed) continue;
    let bucket = byEntry.get(parsed.entryId);
    if (!bucket) {
      bucket = { legacy: new Map(), listings: new Map() };
      byEntry.set(parsed.entryId, bucket);
    }
    if (parsed.listingId === null) {
      bucket.legacy.set(parsed.key, entityId);
    } else {
      let listingMap = bucket.listings.get(parsed.listingId);
      if (!listingMap) {
        listingMap = new Map();
        bucket.listings.set(parsed.listingId, listingMap);
      }
      listingMap.set(parsed.key, entityId);
    }
  }

  const products: TrackedProduct[] = [];

  for (const [entryId, buckets] of byEntry) {
    const keyMap = buckets.legacy;  // primary listing's keys (legacy form)
    const priceEntity = keyMap.get("price");
    if (!priceEntity) continue;  // no price sensor → not a Price Watch product
    const priceState = hass.states[priceEntity];
    if (!priceState) continue;  // entity registered but state not yet pushed

    const attrs = priceState.attributes;
    const product: TrackedProduct = {
      entryId,
      title: String(attrs.title ?? attrs.friendly_name ?? "Unknown product"),
      url: String(attrs.product_url ?? ""),
      retailer: typeof attrs.retailer === "string" ? attrs.retailer : null,
      imageUrl: typeof attrs.image_url === "string" ? attrs.image_url : null,
      // Filled in below if the photo image entity is present and available.
      imageProxyUrl: null,
      imageBroken: false,

      price: stateNumber(priceState.state),
      currency:
        typeof attrs.unit_of_measurement === "string"
          ? attrs.unit_of_measurement
          : typeof attrs.currency === "string"
          ? attrs.currency
          : "",
      priceLocal: null,
      localCurrency: null,
      lowest: null,
      highest: null,
      targetDiff: null,
      targetPrice:
        typeof attrs.target_price === "number" ? attrs.target_price : null,

      inStock: null,
      stockCount:
        typeof attrs.stock_count === "number" ? attrs.stock_count : null,

      discontinued: attrs.discontinued === true,
      discontinuedReason:
        typeof attrs.discontinued_reason === "string"
          ? attrs.discontinued_reason
          : null,
      discontinuedAt:
        typeof attrs.discontinued_at === "string" ? attrs.discontinued_at : null,
      lastKnownPrice:
        typeof attrs.last_known_price === "number"
          ? attrs.last_known_price
          : null,
      lastKnownCurrency:
        typeof attrs.last_known_currency === "string"
          ? attrs.last_known_currency
          : null,

      lastCheck:
        typeof attrs.last_check === "string" ? attrs.last_check : null,
      history: readHistory(attrs.price_history),
      alternatives: readAlternatives(attrs.alternatives),
      alternativesFetchedAt:
        typeof attrs.alternatives_fetched_at === "string"
          ? attrs.alternatives_fetched_at
          : null,
      alternativesError:
        typeof attrs.alternatives_error === "string" && attrs.alternatives_error
          ? attrs.alternatives_error
          : null,
      entityIds: { price: priceEntity },
      // Filled in just before products.push, after the per-listing
      // aggregation pass below. Initialized empty here so the type
      // system stays happy (Listing[] is required, not optional).
      listings: [],
    };

    // Pick up the related sensors when present.
    const lookups: Array<[
      string,
      (state: import("./types.js").HassState) => void
    ]> = [
      [
        "price_local",
        (s) => {
          product.priceLocal = stateNumber(s.state);
          product.localCurrency =
            typeof s.attributes.unit_of_measurement === "string"
              ? s.attributes.unit_of_measurement
              : null;
          product.entityIds.priceLocal = s.entity_id;
        },
      ],
      [
        "lowest",
        (s) => {
          product.lowest = stateNumber(s.state);
          product.entityIds.lowest = s.entity_id;
        },
      ],
      [
        "highest",
        (s) => {
          product.highest = stateNumber(s.state);
          product.entityIds.highest = s.entity_id;
        },
      ],
      [
        "target_diff",
        (s) => {
          product.targetDiff = stateNumber(s.state);
          product.entityIds.targetDiff = s.entity_id;
        },
      ],
      [
        "stock_count",
        (s) => {
          product.stockCount = stateNumber(s.state);
          product.entityIds.stockCount = s.entity_id;
        },
      ],
      [
        "in_stock",
        (s) => {
          product.inStock = stateBool(s.state);
          product.entityIds.inStock = s.entity_id;
        },
      ],
      [
        "discontinued",
        (s) => {
          // Trust the binary sensor's state over the price sensor's
          // attribute mirror — the sensor is the source of truth.
          const flag = stateBool(s.state);
          if (flag != null) product.discontinued = flag;
          product.entityIds.discontinued = s.entity_id;
        },
      ],
      [
        "photo",
        (s) => {
          // The photo image entity goes "unavailable" when the
          // coordinator can't fetch bytes (404, blocked CDN, etc).
          // Mark imageBroken=true in that case so the card shows a
          // placeholder instead of trying the raw imageUrl (which is
          // usually broken for the same reason — that's why the byte
          // fetch failed in the first place).
          if (s.state === "unavailable" || s.state === "unknown") {
            product.imageBroken = true;
            return;
          }
          const ep = s.attributes.entity_picture;
          if (typeof ep === "string" && ep.length > 0) {
            product.imageProxyUrl = ep;
          }
        },
      ],
    ];
    for (const [key, apply] of lookups) {
      const entityId = keyMap.get(key);
      if (!entityId) continue;
      const state = hass.states[entityId];
      if (!state) continue;
      apply(state);
    }

    // Build the listings array — primary first, then secondaries
    // (Map preserves insertion order, which corresponds to creation
    // order for secondary listings since add_listing appends to
    // options.listings; that's the order we want to display).
    //
    // The primary listing's runtime ID comes from the price sensor's
    // listing_id attribute when present (the coordinator writes the
    // canonical runtime ID there during _async_update_one_listing).
    // Falls back to the deterministic ID — `l_<entry suffix>` — when
    // the attribute is missing, matching coordinator._derive_listing_id.
    // The fallback is rare in practice (would mean the price sensor
    // updated before the listing_id attribute was set, or an older
    // integration version that didn't write the attribute yet).
    const primaryListingId =
      typeof attrs.listing_id === "string" && attrs.listing_id
        ? attrs.listing_id
        : `l_${entryId.slice(-12).toLowerCase()}`;
    const primary = buildListing(hass, buckets.legacy, primaryListingId, true);
    if (primary) product.listings.push(primary);
    for (const [listingId, listingKeyMap] of buckets.listings) {
      const secondary = buildListing(hass, listingKeyMap, listingId, false);
      if (secondary) product.listings.push(secondary);
    }

    products.push(product);
  }

  products.sort((a, b) => {
    if (a.discontinued !== b.discontinued) {
      return a.discontinued ? 1 : -1;
    }
    return a.title.localeCompare(b.title);
  });

  return products;
}

/**
 * Generate an SVG path string for a sparkline.
 *
 * Returns an empty string when there are fewer than 2 usable points
 * (a line needs two), letting the caller's template omit the SVG
 * entirely.
 *
 * Outlier handling: real-world price history is dirty. Custom parsers
 * sometimes match the wrong field on a page (e.g. an Amazon regex
 * grabs the price of a "frequently bought together" item, or hits a
 * SKU number, or pulls in a value from sponsored placements). When
 * a single bad fetch records 48,500 alongside legitimate values around
 * 350, the sparkline becomes a zigzag dominated by the outlier and
 * the real signal is lost.
 *
 * We use the Median Absolute Deviation (MAD) test to drop outliers
 * before rendering:
 *   - Compute the median of all prices
 *   - Compute deviations from that median
 *   - Compute the median of those deviations (MAD)
 *   - Drop points where |price - median| > k * MAD
 *
 * MAD is robust to outliers in a way that mean/stddev are not — it's
 * a standard robust-statistics technique. With k=5 we keep anything
 * within a wide band around the median, which trims wild outliers
 * without being too aggressive with legitimate price movements.
 *
 * Edge cases:
 *   - All points identical (MAD = 0): keep everything, the
 *     sparkline will be a flat line which is fine.
 *   - Fewer than 4 points: MAD is unreliable, skip filtering.
 */
export function sparklinePath(
  points: PriceHistoryPoint[],
  width: number,
  height: number,
  paddingY = 2
): string {
  if (points.length < 2) return "";

  // Drop outliers using MAD if we have enough data.
  const cleaned = points.length >= 4 ? filterOutliers(points) : points;
  if (cleaned.length < 2) return "";

  const prices = cleaned.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;  // avoid divide-by-zero on flat history
  const usableHeight = height - paddingY * 2;
  const stepX = width / (cleaned.length - 1);

  let d = "";
  cleaned.forEach((point, i) => {
    const x = i * stepX;
    const y = height - paddingY - ((point.price - min) / range) * usableHeight;
    d += i === 0 ? `M ${x.toFixed(2)} ${y.toFixed(2)}` : ` L ${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  return d;
}

/**
 * Median-Absolute-Deviation outlier filter for a price-history series.
 *
 * Keeps points where the price is within k * MAD of the median. Used
 * by `sparklinePath` and exposed for any future code that needs the
 * same "cleaned series" view (e.g. the lowest/highest display, if we
 * decide those should also ignore outliers).
 *
 * Returns the original array if MAD is zero (all values identical
 * or near-identical) since the filter would otherwise drop everything
 * that doesn't exactly match the median.
 */
export function filterOutliers(
  points: PriceHistoryPoint[],
  k = 5
): PriceHistoryPoint[] {
  if (points.length < 2) return points;
  const prices = points.map((p) => p.price);
  const median = computeMedian(prices);
  const deviations = prices.map((p) => Math.abs(p - median));
  const mad = computeMedian(deviations);
  if (mad === 0) return points;
  return points.filter((p) => Math.abs(p.price - median) <= k * mad);
}

/**
 * Median of a non-empty number array. Mutates a copy via sort.
 * Doesn't try to handle empty input — callers ensure points.length > 0.
 */
function computeMedian(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}
