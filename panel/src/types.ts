/**
 * Shared types for the Price Watch panel.
 *
 * Mirrors the shape of Home Assistant's hass.states[] and the
 * specific attribute set our integration writes onto its sensors.
 * Defined locally rather than imported from HA's frontend typedefs
 * to keep the panel a self-contained bundle.
 */

// --- Home Assistant core types (subset we need) ---

export interface HassState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
  last_updated: string;
}

export interface HassEntity {
  entity_id: string;
  unique_id: string | null;
  platform: string;
  config_entry_id: string | null;
  device_id: string | null;
  name: string | null;
  original_name: string | null;
}

export interface HassConfigEntry {
  entry_id: string;
  domain: string;
  title: string;
  state: string;
  source: string;
  disabled_by: string | null;
}

export interface HomeAssistant {
  states: Record<string, HassState>;
  config: {
    location_name: string;
    time_zone: string;
    language: string;
    [key: string]: unknown;
  };
  language: string;
  // Home Assistant exposes a callWS<T>() for typed WebSocket calls.
  // We use it to fetch config entries and entity registry entries.
  callWS<T>(msg: { type: string; [key: string]: unknown }): Promise<T>;
  // Navigation helper — opens a path inside HA's SPA.
  navigate?: (path: string) => void;
}

// --- Panel-specific types ---

export interface PriceHistoryPoint {
  ts: string;
  price: number;
  currency: string;
  in_stock: boolean;
}

/**
 * One alternative product listing found by the search subsystem.
 * Mirrors the backend `Alternative` dataclass — all fields except
 * title and url are optional.
 *
 * `price` is in the listing's native currency (often the same as
 * the original product's currency, but not always — Amazon CA in
 * CAD vs original Amazon US in USD, etc.). The panel displays the
 * currency code next to the price rather than converting; price
 * comparison across currencies is left to the user.
 *
 * `confidence` is 0.0 - 1.0; the AI's self-reported confidence that
 * this is the same product. The panel sorts DESC by confidence,
 * then ASC by price.
 */
export interface Alternative {
  title: string;
  url: string;
  price: number | null;
  currency: string;
  retailer: string;
  imageUrl: string | null;
  confidence: number;
  notes: string;
  // Whether the retailer ships to the user's region. null = unknown
  // (no badge). true = green "Ships to <X>" badge. false = grey
  // "Doesn't ship" badge. Set by the backend after AI synthesis and
  // optional heuristic override.
  shipsToUserRegion: boolean | null;
}

/**
 * One tracked listing of a product. A product may have N listings —
 * different retailers each polled independently. The primary listing
 * supplies the headline data shown at the top of a card; secondaries
 * are rendered as rows in the Listings section.
 *
 * `isPrimary` is set true for whichever listing the coordinator's
 * 3-way primary resolution chose at runtime (see
 * coordinator._ensure_primary_listing). This is NOT necessarily the
 * listing whose id starts with `l_<entry_id_suffix>` — for
 * shell-then-populate entries it's the first one in self._listings.
 * The panel takes the coordinator's word for it via the price
 * sensor's `listing_id` attribute.
 */
export interface Listing {
  listingId: string;
  isPrimary: boolean;
  retailer: string | null;
  url: string | null;
  price: number | null;
  currency: string;
  inStock: boolean | null;
  discontinued: boolean;
  stockCount: number | null;
  lastCheck: string | null;
  history: PriceHistoryPoint[];
  // Same-origin proxy URL for this listing's image entity
  // (image.<...>_photo for primary, image.<...>_<listing>_photo for
  // secondaries). When present, the listing row shows a thumbnail. HA
  // serves the bytes server-side, sidestepping CDN hotlink/TLS blocking.
  // null when the listing has no photo entity or no bytes cached yet.
  imageProxyUrl: string | null;
  // True if the photo entity exists but is currently unavailable
  // (coordinator couldn't fetch bytes — usually a 404 on the source).
  // The row shows a placeholder rather than a broken-image icon.
  imageBroken: boolean;
  // Whether this listing's retailer ships to the user's region, per the
  // backend shipping heuristic (same one used for alternatives). null =
  // no opinion (always kept visible); true = ships; false = confident it
  // doesn't ship. The panel's "Ships to me only" toggle hides false ones
  // (but never the primary listing). Mirrors Alternative.shipsToUserRegion.
  shipsToUserRegion: boolean | null;
  // Whether anti-bot cookies are stored for this listing (the value itself
  // is never sent to the frontend). Drives the "cookies set" hint in the
  // editor; the cookie box stays write-only.
  hasCookies: boolean;
  // Retailer's seasonal-offers landing page for this listing's host, when
  // configured (Store offer links). Drives the "Tilboð hjá <store>" link
  // after the retailer name. null when the store has no configured page.
  offerPageUrl: string | null;
  // Entity IDs for this listing's sensors. Used for service-call
  // targeting and cross-references. Always populated with the price
  // entity (the listing wouldn't exist without it); others optional.
  entityIds: {
    price?: string;
    inStock?: string;
    discontinued?: string;
  };
}

/**
 * All the data the UI needs for one tracked product, derived entirely
 * from hass.states[]. Built by aggregating sensors that share the same
 * config_entry_id.
 *
 * If any required field is missing (most often because the entry is in
 * setup_retry and entities haven't materialized yet), the product is
 * skipped — better to show fewer cards than half-broken ones.
 */
export interface TrackedProduct {
  entryId: string;
  title: string;
  url: string;
  retailer: string | null;
  imageUrl: string | null;
  // Same-origin proxy URL for the image entity (image.<...>_photo).
  // When present, prefer this over imageUrl — HA serves the bytes
  // server-side, sidestepping hotlink protection and CDN blocking.
  // null when the image entity is unavailable (e.g. the source 404'd).
  imageProxyUrl: string | null;
  // True if the photo image entity exists but is currently
  // unavailable (coordinator couldn't fetch bytes — usually a 404 on
  // the source URL). In that case we render the placeholder rather
  // than falling back to the raw imageUrl, which would just show a
  // broken-image icon for the same reason.
  imageBroken: boolean;

  // Price sensor state. All numbers in source currency; price_local is
  // separately in the user's home currency.
  price: number | null;
  currency: string;
  priceLocal: number | null;
  localCurrency: string | null;
  lowest: number | null;
  highest: number | null;
  targetDiff: number | null;
  targetPrice: number | null;
  // On-sale signals from the price sensor. onSale true when the retailer
  // shows a struck-through "was" price above the current one; originalPrice
  // is that was-price and discountPercent is the rounded % off.
  onSale: boolean;
  originalPrice: number | null;
  discountPercent: number | null;
  // Per-physical-store stock, when the retailer exposes it (Húsa / JYSK).
  // Full list plus a convenience list of stores that actually have it. null
  // when not applicable. JYSK rows carry `fromWarehouse` (red-asterisk stock
  // that's at the Reykjavík warehouse, not physically in that store).
  storeAvailability:
    | { store: string; status: string; fromWarehouse?: boolean }[]
    | null;
  availableStores: string[] | null;
  // True when every in-stock store is warehouse-sourced (JYSK) — the item
  // can't be picked up locally without ordering it in.
  stockFromWarehouse: boolean;
  // Sibling size pages (JYSK "Stærðir"), each its own product URL. The
  // current size is `selected`. null when the retailer has no size picker.
  sizeOptions: { label: string; url: string; selected: boolean }[] | null;
  // Retailer product number (Húsa "Vörunúmer", Byko "VNR") and a fuller
  // description name beyond the short title, shown under the title. null
  // when the retailer doesn't expose them.
  productNumber: string | null;
  descriptionName: string | null;
  // Whether polling is currently paused for this product (set via the
  // options flow or the price_watch.set_paused service). Surfaced on the
  // price sensor's attributes so the panel can render the inline pause
  // toggle and a "Paused" badge without a separate WS round-trip.
  paused: boolean;

  // Stock
  inStock: boolean | null;
  stockCount: number | null;

  // Discontinuation
  discontinued: boolean;
  discontinuedReason: string | null;
  discontinuedAt: string | null;
  lastKnownPrice: number | null;
  lastKnownCurrency: string | null;

  // Misc context for the bottom of the card
  lastCheck: string | null;
  history: PriceHistoryPoint[];

  // Alternatives — populated by the find_alternatives service. The
  // panel renders these as a collapsible section under the
  // sparkline with retailer, price, and a click-through to the URL.
  // Empty array when none have been fetched. `alternativesError` is
  // populated (and the array left empty) when the most recent
  // fetch failed.
  alternatives: Alternative[];
  alternativesFetchedAt: string | null;
  alternativesError: string | null;

  // Entity IDs we resolved (kept around so cards can deep-link or trigger
  // service calls like refresh_now).
  entityIds: {
    price?: string;
    priceLocal?: string;
    lowest?: string;
    highest?: string;
    targetDiff?: string;
    stockCount?: string;
    inStock?: string;
    discontinued?: string;
  };

  // All listings for this product, ordered with primary first.
  // Single-listing products have one entry (the primary); multi-
  // listing products have N entries. Always non-empty when the
  // product was successfully built (a product without listings would
  // have no price sensor and wouldn't pass the early-skip check in
  // buildProducts).
  //
  // The primary listing's data is also mirrored onto the top-level
  // fields above (price, currency, lowest, highest, history, etc.)
  // for back-compat with the rest of the card that doesn't know
  // about listings. New code should prefer reading from this array.
  listings: Listing[];
}
