/**
 * <price-watch-panel>
 *
 * Top-level Lit element registered as the HA panel via panel_custom
 * with embed_iframe=False. In that mode HA does NOT inject `hass` as
 * a property — the documented property-forwarding contract only runs
 * for the iframe path, and the iframe path failed in our environment.
 *
 * So this element bootstraps its OWN connection to HA's WebSocket
 * API using the global `hassConnection` Promise that HA's frontend
 * exposes on window. From that connection we:
 *
 *   - fetch the entity registry once (config/entity_registry/list)
 *   - subscribe to state-changed events for the entities we care about
 *   - subscribe to entity_registry_updated for add/remove notifications
 *
 * `buildProducts()` still expects a hass-like object so we keep the
 * shape stable by accumulating states into a local `_states` map and
 * presenting it as if it were `hass.states`.
 */

import { LitElement, html, css } from "lit";
import { state } from "lit/decorators.js";

import "./card.js";
import type {
  Alternative,
  HomeAssistant,
  HassState,
  Listing,
  TrackedProduct,
} from "./types.js";
import { buildProducts, type EntityRegistryIndex } from "./utils.js";

// Sort options offered in the toolbar. Order here is the order shown
// in the <select>. "name" is the default (stable, predictable).
const SORT_KEYS = [
  "name",
  "drop",
  "cheapest",
  "last_checked",
  "below_target",
] as const;
type SortKey = (typeof SORT_KEYS)[number];

const SORT_LABELS: Record<SortKey, string> = {
  name: "Name (A–Z)",
  drop: "Biggest drop",
  cheapest: "Cheapest",
  last_checked: "Last checked",
  below_target: "Below target",
};

// Shape of the entity_registry/list response.
interface RegistryEntry {
  entity_id: string;
  unique_id: string;
  platform: string;
  config_entry_id: string | null;
}

// One result row from the price_watch/search WS command. Mirrors the
// backend Alternative.to_dict() shape (snake_case keys, straight off
// the wire — we don't camel-case these like buildProducts does).
interface SearchResult {
  title: string;
  url: string;
  price: number | null;
  currency: string;
  retailer: string;
  image_url: string | null;
  confidence: number;
  notes: string;
  ships_to_user_region: boolean | null;
  // Free mode (no AI) only: the backend sets `retailer` to the bare domain
  // and flags hits on known non-commerce sites (GitHub/YouTube/wiki/docs)
  // so the user can tell a seller from a guide/video/repo. Absent/false in
  // AI modes (those already return curated retailer listings).
  likely_non_shop?: boolean;
}

// Reply envelope from price_watch/search.
interface SearchResponse {
  engine: "anthropic_native" | "ai_synthesizer" | "duckduckgo" | "none";
  results: SearchResult[];
}

// Human labels for the engine that produced the results, shown as a
// small caption so the user understands result quality (AI-cleaned vs
// raw web hits).
const ENGINE_LABELS: Record<SearchResponse["engine"], string> = {
  anthropic_native: "AI web search",
  ai_synthesizer: "AI + web search",
  duckduckgo: "Web results (no AI)",
  none: "",
};

// How many results to ask the backend for.
const SEARCH_MAX_RESULTS = 8;

// --- AI provider editor ---
// The three provider modes the panel editor exposes. "none" is the
// backend's name for Free mode (anthropic provider with a null key).
type ProviderKind = "none" | "anthropic" | "openai_compatible";

// Reply shape of price_watch/get_provider_settings (and the body of the
// set reply). Mirrors websocket._current_provider_state(). SECURITY: the
// backend never sends the raw key — only has_api_key.
interface ProviderSettings {
  provider: ProviderKind;
  model: string;
  base_url: string;
  has_api_key: boolean;
  input_cost_per_mtok: number;
  output_cost_per_mtok: number;
  max_html_chars: number;
  force_json_mode: boolean;
  extra_headers: string;
  anthropic_models: string[];
  // Global blocklist of retailer hostnames dropped from every
  // alternatives/search result. Returned normalized (bare lowercase
  // hosts); sent back as a list on save.
  excluded_domains: string[];
  // When true, the AI is used only as a price-fetch fallback (search stays
  // on free DuckDuckGo). Only meaningful when a provider is configured.
  ai_fallback_only: boolean;
  // Per-retailer seasonal-offers links (host → offers page URL). Drives the
  // "Tilboð hjá <store>" link on cards; editable here.
  store_offer_links: { host: string; url: string }[];
}

// set_provider_settings adds a count of product entries scheduled for
// reload on top of the refreshed settings snapshot.
interface SetProviderResponse extends ProviderSettings {
  reloaded: number;
}

// Human labels for the provider <select>.
const PROVIDER_LABELS: Record<ProviderKind, string> = {
  none: "Free — web search, no AI",
  anthropic: "Anthropic (Claude)",
  openai_compatible: "OpenAI-compatible (Ollama, OpenAI, …)",
};

// --- Advanced price-selector editor ---
// Result of one selector run, as reported by price_watch/test_selector.
interface SelectorRun {
  selector: string;
  found: boolean;
  raw: string | null;
  value?: number | null; // only on the price run
  error?: string;
}
// Reply shape of price_watch/test_selector.
interface TestSelectorResponse {
  fetch_ok: boolean;
  page_title: string;
  price: SelectorRun;
  title?: SelectorRun;
}

// --- Variant picker ---
// One option group on a Wix product page (e.g. "Remote", "Voltage").
interface VariantOptionGroup {
  title: string;
  choices: string[];
}
// One concrete variant combo with its price.
interface VariantCombo {
  labels: string[];
  price: number;
  currency: string;
  in_stock: boolean;
}
// Reply shape of price_watch/list_variants.
interface ListVariantsResponse {
  supported: boolean;
  options?: VariantOptionGroup[];
  variants?: VariantCombo[];
  current?: string[];
  currency?: string;
}

// The element-picker bookmarklet. When dropped on a retailer's product
// page and clicked, it overlays a picker: hovering highlights elements,
// clicking one computes a reasonably-robust CSS selector for it and
// copies that selector to the clipboard (falling back to a prompt() the
// user can copy from). The user then pastes it into the editor's price
// selector field. This is the only way to get a click-to-pick UX —
// retailer pages can't be iframed into our panel (X-Frame-Options/CSP),
// and same-origin policy blocks reaching into a cross-origin tab, so the
// picker has to run IN the retailer's own page via a bookmarklet.
//
// Kept as readable source here; minified into the javascript: URL at
// render time by _bookmarkletHref(). Self-contained, no external loads
// (CSP on many sites blocks remote scripts), cleans up after itself.
const BOOKMARKLET_SOURCE = `(function(){
  if(window.__pwPickerActive){return;}
  window.__pwPickerActive=true;
  var hl=document.createElement('div');
  hl.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:rgba(25,118,210,0.25);border:2px solid #1976d2;border-radius:3px;transition:all 40ms ease';
  var tip=document.createElement('div');
  tip.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:#1976d2;color:#fff;font:12px/1.4 sans-serif;padding:3px 6px;border-radius:4px;max-width:90vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis';
  document.body.appendChild(hl);document.body.appendChild(tip);
  function sel(el){
    if(!el||el.nodeType!==1)return'';
    if(el.id&&/^[A-Za-z][-_A-Za-z0-9]*$/.test(el.id))return'#'+el.id;
    var parts=[],node=el,depth=0;
    while(node&&node.nodeType===1&&depth<5){
      var part=node.tagName.toLowerCase();
      if(node.id&&/^[A-Za-z][-_A-Za-z0-9]*$/.test(node.id)){parts.unshift('#'+node.id);break;}
      var cls=(node.getAttribute('class')||'').trim().split(/\\s+/).filter(function(c){return c&&!/^(is-|has-|js-)/.test(c)&&c.length<30;}).slice(0,2);
      if(cls.length)part+='.'+cls.join('.');
      var p=node.parentElement;
      if(p){var sib=Array.prototype.filter.call(p.children,function(c){return c.tagName===node.tagName;});if(sib.length>1){part+=':nth-of-type('+(sib.indexOf(node)+1)+')';}}
      parts.unshift(part);node=p;depth++;
    }
    return parts.join(' > ');
  }
  function move(e){
    var el=e.target;if(!el||el===hl||el===tip)return;
    var r=el.getBoundingClientRect();
    hl.style.left=r.left+'px';hl.style.top=r.top+'px';hl.style.width=r.width+'px';hl.style.height=r.height+'px';
    var s=sel(el);tip.textContent=s;
    tip.style.left=r.left+'px';tip.style.top=(r.top>24?r.top-24:r.bottom+4)+'px';
  }
  function done(){window.removeEventListener('mousemove',move,true);window.removeEventListener('click',click,true);window.removeEventListener('keydown',key,true);hl.remove();tip.remove();window.__pwPickerActive=false;}
  function click(e){
    e.preventDefault();e.stopPropagation();
    var s=sel(e.target);
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(s).then(function(){},function(){window.prompt('Copy this selector:',s);});}
    else{window.prompt('Copy this selector:',s);}
    done();
  }
  function key(e){if(e.key==='Escape'){done();}}
  window.addEventListener('mousemove',move,true);
  window.addEventListener('click',click,true);
  window.addEventListener('keydown',key,true);
})();`;

// Minimal Connection interface from home-assistant-js-websocket. We
// can't import the type because we don't depend on that package at
// build time (it's not in package.json), so we re-declare the parts
// we use. The Connection itself lives in the host frontend.
interface HassConnection {
  sendMessagePromise<T = unknown>(msg: { type: string; [key: string]: unknown }): Promise<T>;
  subscribeEvents(
    callback: (event: { event_type: string; data: unknown }) => void,
    eventType: string
  ): Promise<() => void>;
  subscribeMessage<T = unknown>(
    callback: (data: T) => void,
    subscribeMessage: { type: string; [key: string]: unknown }
  ): Promise<() => void>;
}

interface HassConnectionWrapper {
  conn: HassConnection;
  // The home-assistant-js-websocket Auth object. We use its access token to
  // POST to HA's REST automation-config endpoint (the same mechanism HA's
  // own automation editor uses) when creating price alerts.
  auth?: {
    accessToken?: string;
    data?: { access_token?: string };
  };
}

// One notify.* target from price_watch/list_notify_targets.
interface NotifyTarget {
  service: string; // e.g. "notify.mobile_app_davids_simi"
  label: string; // e.g. "Davids Simi"
}

// The alert triggers, mapped to the integration's bus events.
type AlertTrigger =
  | "back_in_stock"
  | "below_target"
  | "price_drop"
  | "on_sale";
const ALERT_EVENT: Record<AlertTrigger, string> = {
  back_in_stock: "price_watch_back_in_stock",
  below_target: "price_watch_target_hit",
  price_drop: "price_watch_price_drop",
  on_sale: "price_watch_discount",
};

declare global {
  interface Window {
    hassConnection?: Promise<HassConnectionWrapper>;
  }
}

// What state-changed events look like over the websocket.
interface StateChangedEvent {
  event_type: "state_changed";
  data: {
    entity_id: string;
    new_state: HassState | null;
    old_state: HassState | null;
  };
}

export class PriceWatchPanel extends LitElement {
  @state() private _products: TrackedProduct[] = [];
  @state() private _registry: EntityRegistryIndex | null = null;
  @state() private _registryError: string | null = null;
  @state() private _connected = false;
  // Entry IDs whose alternatives search is currently in flight. Set
  // when the user clicks refresh, cleared when the service call
  // returns (success or failure). The card uses this to show a
  // spinner on its refresh icon.
  @state() private _refreshingEntries = new Set<string>();
  // When true, alternatives flagged as not shipping to the user's
  // region are hidden across every card. Persisted to localStorage so
  // the preference survives reloads. Restored in the constructor.
  @state() private _hideNonShipping = false;
  // Toolbar state. Search is session-only (cleared on reload); sort and
  // the hide-discontinued toggle are persisted to localStorage so the
  // user's preferred view sticks across reloads. Restored in constructor.
  @state() private _search = "";
  @state() private _sort: SortKey = "name";
  @state() private _hideDiscontinued = false;
  // Entry IDs whose refresh_now (price re-check) is in flight. Distinct
  // from _refreshingEntries, which tracks the slower alternatives search,
  // so a card can show independent spinners for each action.
  @state() private _refreshingNow = new Set<string>();

  // --- Live search ("Search & add") modal state ---
  // Whether the search overlay is open.
  @state() private _searchOpen = false;
  // Current query text in the search box.
  @state() private _searchQuery = "";
  // True while a price_watch/search WS call is in flight.
  @state() private _searchLoading = false;
  // Results from the last completed search (empty until one runs).
  @state() private _searchResults: SearchResult[] = [];
  // The engine that produced _searchResults, for the quality caption.
  @state() private _searchEngine: SearchResponse["engine"] = "none";
  // True once a search has completed at least once this session — lets
  // us distinguish "no results" from "haven't searched yet".
  @state() private _searchRan = false;
  // User-facing error from the last search (WS error message), or null.
  @state() private _searchError: string | null = null;
  // Hosts with an exclude_domain call currently in flight (disables that
  // row's "Exclude site" button and shows a spinner label).
  @state() private _excludingHosts: Set<string> = new Set();
  // Hosts excluded this session via an alternative row's "⊘" button. Passed
  // to each card so its alternatives from these hosts hide immediately, until
  // the next find_alternatives drops them server-side.
  @state() private _hiddenAltHosts: Set<string> = new Set();
  // When true, Free-mode results flagged as non-stores (GitHub, YouTube,
  // wiki, docs/forums) are hidden from the list. Persisted to localStorage.
  // Only affects rows with likely_non_shop===true (Free mode only); AI
  // modes never set the flag, so the toggle is a no-op there.
  @state() private _hideNonShops = false;
  // The result the user is confirming in the "Track this" dialog, or
  // null when the results list is showing. When set, the modal swaps to
  // the confirm form pre-filled from this result.
  @state() private _trackTarget: SearchResult | null = null;
  // Editable confirm-dialog fields, seeded from _trackTarget on pick.
  @state() private _trackName = "";
  @state() private _trackUrl = "";
  @state() private _trackTargetPrice = "";
  // True while the track_product service call is in flight.
  @state() private _tracking = false;
  // Error from the last track_product attempt (e.g. already tracked).
  @state() private _trackError: string | null = null;
  // --- AI provider editor modal state ---
  // Whether the provider settings overlay is open.
  @state() private _providerOpen = false;
  // True while the initial get_provider_settings call is in flight.
  @state() private _providerLoading = false;
  // True while a set_provider_settings call is in flight.
  @state() private _providerSaving = false;
  // Error from the last load/save (WS error message), or null.
  @state() private _providerError: string | null = null;
  // True briefly after a successful save (shows the confirmation banner).
  @state() private _providerSuccess = false;
  // Whether the OpenAI-compat "Advanced" section is expanded.
  @state() private _providerAdvancedOpen = false;
  // The currently selected provider mode in the editor form.
  @state() private _pProvider: ProviderKind = "none";
  // Editable form fields, seeded from get_provider_settings on open.
  // _pApiKey is always blank on load — the backend never returns the key,
  // and a blank submit means "keep the stored key".
  @state() private _pApiKey = "";
  @state() private _pModel = "";
  @state() private _pBaseUrl = "";
  @state() private _pInputCost = "";
  @state() private _pOutputCost = "";
  @state() private _pMaxHtml = "";
  @state() private _pForceJson = false;
  @state() private _pExtraHeaders = "";
  // Global domain blocklist as edited in the textarea — one host per
  // line. Seeded from get_provider_settings (joined with newlines) and
  // split back into a list on save. Applies to every product's
  // alternatives search, not just one.
  @state() private _pExcludedDomains = "";
  // "Use AI only as a price-fetch fallback" — keep search on free DDG.
  @state() private _pFallbackOnly = false;
  // Store offer links, edited as "host | url" lines.
  @state() private _pStoreOfferLinks = "";
  // Whether a key is already stored (drives the "leave blank to keep"
  // placeholder). Never the key itself.
  @state() private _providerHasKey = false;
  // Anthropic model choices offered in the dropdown (from the backend so
  // the panel and HA stay in sync).
  @state() private _providerModels: string[] = [];

  // --- Advanced price-selector editor modal state ---
  // Whether the selector editor overlay is open.
  @state() private _selectorOpen = false;
  // The product + listing being edited (drives the edit_listing call).
  private _selProduct: TrackedProduct | null = null;
  private _selListing: Listing | null = null;
  // Editable form fields.
  @state() private _selPriceSelector = "";
  @state() private _selTitleSelector = "";
  // Request cookies (Cookie-header string). Write-only: we never surface
  // the stored value to the frontend (cookies are session secrets), so the
  // field starts blank and an empty value means "leave existing cookies
  // untouched". The backend keeps cookies independent of the selector.
  @state() private _selCookies = "";
  // True while a price_watch/test_selector call is in flight.
  @state() private _selTesting = false;
  // The last test result, or null before the first test.
  @state() private _selTestResult: TestSelectorResponse | null = null;
  // Error from the last test (WS error message), or null.
  @state() private _selTestError: string | null = null;
  // True while the edit_listing save is in flight.
  @state() private _selSaving = false;
  // Error from the last save, or null.
  @state() private _selSaveError: string | null = null;
  // True briefly after a successful save (shows the confirmation banner).
  @state() private _selSaved = false;
  // Whether the bookmarklet "copy code" fallback block is expanded.
  @state() private _selBookmarkletOpen = false;

  // --- Variant picker modal state ---
  // Whether the variant picker overlay is open.
  @state() private _variantOpen = false;
  // The product + listing whose variant is being chosen.
  private _varProduct: TrackedProduct | null = null;
  private _varListing: Listing | null = null;
  // True while the price_watch/list_variants fetch is in flight.
  @state() private _varLoading = false;
  // Fetch/parse error, or null.
  @state() private _varError: string | null = null;
  // The option groups returned by the backend (null before load / when
  // the page isn't a variant page).
  @state() private _varGroups: VariantOptionGroup[] | null = null;
  // Every concrete combo the page ships, for price preview + validation.
  @state() private _varCombos: VariantCombo[] = [];
  // The user's current per-group selection (one label per group, index-
  // aligned to _varGroups). Empty string = "not chosen yet".
  @state() private _varSelection: string[] = [];
  // Whether the inspected page even supports variant selection.
  @state() private _varSupported = true;
  // True while the set_variant save is in flight.
  @state() private _varSaving = false;
  // Error from the last save, or null.
  @state() private _varSaveError: string | null = null;
  // True briefly after a successful save (shows the confirmation banner).
  @state() private _varSaved = false;

  // --- Alert ("notify me") dialog state ---
  @state() private _alertOpen = false;
  private _alertProduct: TrackedProduct | null = null;
  @state() private _alertTrigger: AlertTrigger = "back_in_stock";
  // notify.* targets fetched from the backend on open.
  @state() private _alertTargets: NotifyTarget[] = [];
  // Which notify services the user ticked.
  @state() private _alertSelected: Set<string> = new Set();
  @state() private _alertLoading = false;
  @state() private _alertSaving = false;
  @state() private _alertError: string | null = null;
  // Holds the created automation's friendly id briefly on success.
  @state() private _alertSaved: string | null = null;

  // Stashed connection used for the post-bootstrap call_service
  // sends. Populated by _bootstrap() once the wrapper resolves.
  private _conn: HassConnection | null = null;

  // Our local mirror of relevant entity states. Populated initially
  // via get_states, kept fresh via state-changed events. Only contains
  // entities we know are ours (filtered by unique_id prefix in the
  // registry).
  private _states: Record<string, HassState> = {};

  // Connection unsubscribers, kept so we can clean up on disconnect.
  private _unsubState?: () => void;
  private _unsubRegistry?: () => void;

  // localStorage keys for persisted view preferences.
  private static readonly HIDE_NONSHIP_KEY = "price-watch:hide-non-shipping";
  private static readonly SORT_KEY = "price-watch:sort";
  private static readonly HIDE_DISCONTINUED_KEY =
    "price-watch:hide-discontinued";
  private static readonly HIDE_NONSHOPS_KEY = "price-watch:hide-non-shops";

  constructor() {
    super();
    // Restore the toggle preferences. Wrapped in try/catch because
    // localStorage can throw in locked-down / private-mode contexts.
    try {
      this._hideNonShipping =
        localStorage.getItem(PriceWatchPanel.HIDE_NONSHIP_KEY) === "1";
      this._hideDiscontinued =
        localStorage.getItem(PriceWatchPanel.HIDE_DISCONTINUED_KEY) === "1";
      this._hideNonShops =
        localStorage.getItem(PriceWatchPanel.HIDE_NONSHOPS_KEY) === "1";
      const savedSort = localStorage.getItem(PriceWatchPanel.SORT_KEY);
      if (savedSort && SORT_KEYS.includes(savedSort as SortKey)) {
        this._sort = savedSort as SortKey;
      }
    } catch {
      // Ignore — defaults (show everything, sort by name) are safe.
    }
  }

  connectedCallback(): void {
    super.connectedCallback();
    void this._bootstrap();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsubState?.();
    this._unsubRegistry?.();
    this._unsubState = undefined;
    this._unsubRegistry = undefined;
  }

  private async _bootstrap(): Promise<void> {
    const wrapperPromise = window.hassConnection;
    if (!wrapperPromise) {
      this._registryError =
        "Home Assistant WebSocket connection not available on this page. " +
        "Try reloading.";
      return;
    }

    let conn: HassConnection;
    try {
      const wrapper = await wrapperPromise;
      conn = wrapper.conn;
      this._conn = conn;
      this._connected = true;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this._registryError = `Could not open HA connection: ${message}`;
      return;
    }

    try {
      await this._fetchRegistry(conn);
      await this._fetchInitialStates(conn);
      this._unsubState = await conn.subscribeEvents(
        (event) => this._onStateChanged(event as StateChangedEvent),
        "state_changed"
      );
      this._unsubRegistry = await conn.subscribeEvents(
        () => {
          // Registry changed (add/remove product). Re-fetch.
          void this._fetchRegistry(conn).then(() =>
            this._fetchInitialStates(conn)
          );
        },
        "entity_registry_updated"
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this._registryError = `Setup failed after connection: ${message}`;
      console.error("[price-watch-panel]", err);
    }
  }

  private async _fetchRegistry(conn: HassConnection): Promise<void> {
    const entries = await conn.sendMessagePromise<RegistryEntry[]>({
      type: "config/entity_registry/list",
    });

    const byUniqueId = new Map<string, string>();
    for (const entry of entries) {
      if (entry.platform !== "price_watch") continue;
      byUniqueId.set(entry.unique_id, entry.entity_id);
    }
    this._registry = { byUniqueId };
    this._registryError = null;
    this._rebuildProducts();
  }

  private async _fetchInitialStates(conn: HassConnection): Promise<void> {
    if (!this._registry) return;

    // Build the set of entity IDs we care about (the values of the
    // registry map). We only fetch these — no point pulling the entire
    // HA state map for a panel that only renders a handful of entities.
    const ourEntityIds = new Set(this._registry.byUniqueId.values());

    // get_states returns ALL states; we filter client-side. There's
    // no get_states_for_entities API, sadly.
    const allStates = await conn.sendMessagePromise<HassState[]>({
      type: "get_states",
    });
    const next: Record<string, HassState> = {};
    for (const state of allStates) {
      if (ourEntityIds.has(state.entity_id)) {
        next[state.entity_id] = state;
      }
    }
    this._states = next;
    this._rebuildProducts();
  }

  private _onStateChanged(event: StateChangedEvent): void {
    const { entity_id, new_state } = event.data;
    if (!this._registry) return;

    // Only react to our entities. Build a set on each event call —
    // cheap (small map), avoids cache-invalidation bugs.
    const ourEntityIds = new Set(this._registry.byUniqueId.values());
    if (!ourEntityIds.has(entity_id)) return;

    if (new_state === null) {
      delete this._states[entity_id];
    } else {
      this._states = { ...this._states, [entity_id]: new_state };
    }
    this._rebuildProducts();
  }

  /**
   * Compose a hass-shaped object from our local state mirror so we
   * can reuse `buildProducts()` unchanged. The object only carries
   * the fields buildProducts touches (states + dummies for the rest).
   */
  private _rebuildProducts(): void {
    if (!this._registry) {
      this._products = [];
      return;
    }
    const fakeHass: HomeAssistant = {
      states: this._states,
      config: {
        location_name: "",
        time_zone: "UTC",
        language: "en",
      },
      language: "en",
      // callWS is only used by the old code path; bootstrap doesn't
      // need it. We provide a stub that rejects so misuse surfaces.
      callWS: () =>
        Promise.reject(new Error("callWS unavailable in bootstrap mode")),
    };
    this._products = buildProducts(fakeHass, this._registry);
  }

  private _handleOpen = (product: TrackedProduct): void => {
    if (!product.url) return;
    window.open(product.url, "_blank", "noopener,noreferrer");
  };

  /**
   * Trigger an alternatives search for one product.
   *
   * Fires a price_watch.find_alternatives service call via the
   * websocket. While the call is in flight, the entry is added to
   * _refreshingEntries so the card shows a spinner. When the call
   * returns (success or error), the entry is removed.
   *
   * The sensor's alternatives attribute updates server-side when
   * the search completes — our state_changed subscription picks
   * that up and feeds it through _rebuildProducts, so the new
   * alternatives appear without any explicit re-fetch here.
   *
   * Note: the service call typically takes 5-60s (DDG + Ollama or
   * Anthropic). We do not enforce a client-side timeout; if the
   * call hangs longer than HA's own service timeout (~60s), the
   * websocket layer raises and we clear the spinner.
   */
  private _handleRefreshAlternatives = async (
    product: TrackedProduct
  ): Promise<void> => {
    if (!this._conn) return;
    if (this._refreshingEntries.has(product.entryId)) return;

    // Add to refreshing set — re-render so the spinner appears.
    this._refreshingEntries = new Set([
      ...this._refreshingEntries,
      product.entryId,
    ]);

    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "find_alternatives",
        service_data: { entry_id: product.entryId },
      });
    } catch (err) {
      // Log but don't surface to the user — the sensor's
      // alternatives_error attribute already carries any
      // backend-side failure, so the card will show it. Network
      // errors at the websocket layer (rare) just look like a
      // missed refresh.
      console.error(
        "[price-watch-panel] find_alternatives failed:",
        err
      );
    } finally {
      // Drop from refreshing set — re-render to clear spinner.
      const next = new Set(this._refreshingEntries);
      next.delete(product.entryId);
      this._refreshingEntries = next;
    }
  };

  /**
   * Remove a single listing from a product.
   *
   * Fires price_watch.remove_listing via the websocket. The card
   * has already shown a window.confirm before invoking this — by
   * the time we get here the user has agreed.
   *
   * On success, the integration unregisters the listing's sensor
   * entities and persists the change. HA emits
   * entity_registry_updated, our subscription fires, _fetchRegistry
   * rebuilds, and the card re-renders without the removed row —
   * no explicit state management needed here.
   *
   * On failure (network, service error, listing not found), we
   * surface the error to the console. A future enhancement could
   * show a toast / banner. The user can re-try from the row.
   */
  private _handleRemoveListing = async (
    product: TrackedProduct,
    listing: Listing
  ): Promise<void> => {
    if (!this._conn) return;
    if (listing.isPrimary) {
      // Defensive — the card hides the button for primary listings,
      // but if something slips through we refuse rather than calling
      // the service (which would error anyway since the integration
      // also rejects primary removal).
      console.warn(
        "[price-watch-panel] refusing to remove primary listing",
        listing.listingId
      );
      return;
    }
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "remove_listing",
        service_data: {
          entry_id: product.entryId,
          listing_id: listing.listingId,
        },
      });
    } catch (err) {
      console.error(
        "[price-watch-panel] remove_listing failed:",
        err
      );
    }
  };

  /**
   * Add an alternative as a tracked listing on its product.
   *
   * Fires price_watch.add_listing with the alternative's URL plus
   * retailer/currency hints so the backend doesn't have to re-derive
   * them. The card has already shown a window.confirm before invoking
   * this. add_listing mutates entry.options.listings and reloads the
   * entry; the coordinator re-instantiates with the new listing, sensor
   * entities are created, entity_registry_updated fires, our
   * subscription rebuilds the registry, and the new row appears in the
   * card's Listings section — no explicit state management here.
   *
   * On failure (duplicate URL, network, service error) we log to the
   * console; the integration rejects duplicate URLs, which is the most
   * likely error and is already guarded against in the card (the add
   * button is replaced by a ✓ once a matching listing exists).
   */
  private _handleAddListing = async (
    product: TrackedProduct,
    alt: Alternative
  ): Promise<void> => {
    if (!this._conn) return;
    const url = (alt.url ?? "").trim();
    if (!url) return;
    const serviceData: Record<string, unknown> = {
      entry_id: product.entryId,
      url,
    };
    if (alt.retailer) serviceData.retailer = alt.retailer;
    if (alt.currency) serviceData.currency = alt.currency;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "add_listing",
        service_data: serviceData,
      });
    } catch (err) {
      console.error("[price-watch-panel] add_listing failed:", err);
    }
  };

  // --- Advanced price-selector editor ---

  /**
   * Open the advanced selector editor for one listing. Seeds the form
   * blank (we don't surface the existing custom_parser in the Listing
   * model, and starting fresh is the common case — the user is here
   * because the default extractor failed). The URL/retailer come from
   * the listing so Test and Save target the right page.
   */
  private _handleEditListing = (
    product: TrackedProduct,
    listing: Listing
  ): void => {
    this._selProduct = product;
    this._selListing = listing;
    this._selPriceSelector = "";
    this._selTitleSelector = "";
    this._selCookies = "";
    this._selTestResult = null;
    this._selTestError = null;
    this._selSaveError = null;
    this._selSaved = false;
    this._selBookmarkletOpen = false;
    this._selectorOpen = true;
  };

  private _closeSelectorEditor = (): void => {
    this._selectorOpen = false;
    this._selProduct = null;
    this._selListing = null;
  };

  private _onSelectorBackdropClick = (e: Event): void => {
    if (e.target === e.currentTarget) this._closeSelectorEditor();
  };

  private _onSelPriceInput = (e: Event): void => {
    this._selPriceSelector = (e.target as HTMLInputElement).value;
  };

  private _onSelTitleInput = (e: Event): void => {
    this._selTitleSelector = (e.target as HTMLInputElement).value;
  };

  private _onSelCookiesInput = (e: Event): void => {
    this._selCookies = (e.target as HTMLTextAreaElement).value;
  };

  /**
   * Run the price (and optional title) selector against the live page
   * server-side via price_watch/test_selector. The backend fetches with
   * the same curl_cffi pipeline the poller uses and applies the same
   * price_clean transform, so the previewed value matches what would be
   * stored. Title defaults to `h1` when left blank — a custom CSS parser
   * needs BOTH a title and a price, and most product pages put the name
   * in an <h1>.
   */
  private _runSelectorTest = async (): Promise<void> => {
    if (!this._conn || !this._selListing) return;
    const url = (this._selListing.url ?? "").trim();
    const priceSelector = this._selPriceSelector.trim();
    if (!url) {
      this._selTestError = "This listing has no URL to test against.";
      return;
    }
    if (!priceSelector) {
      this._selTestError = "Enter a price selector first.";
      return;
    }
    this._selTesting = true;
    this._selTestError = null;
    this._selTestResult = null;
    const titleSelector = this._selTitleSelector.trim() || "h1";
    const cookies = this._selCookies.trim();
    try {
      const resp = await this._conn.sendMessagePromise<TestSelectorResponse>({
        type: "price_watch/test_selector",
        url,
        price_selector: priceSelector,
        title_selector: titleSelector,
        // Include any pasted cookies so the test fetches the page the same
        // way the poll will — otherwise testing a cookie-walled site hits
        // the bot wall and fails even though the real listing would work.
        ...(cookies ? { request_cookies: cookies } : {}),
      });
      this._selTestResult = resp;
    } catch (err) {
      this._selTestError =
        (err as { message?: string })?.message ?? "Test failed.";
    } finally {
      this._selTesting = false;
    }
  };

  /**
   * Persist the form via price_watch.edit_listing. The price selector and
   * the cookies are independent: a CSS custom_parser is only sent when a
   * price selector is entered, and request_cookies is only sent when the
   * cookie box is non-empty. The backend keeps the two orthogonal — setting
   * one never clobbers the other — so either can be saved on its own.
   */
  private _saveSelector = async (): Promise<void> => {
    if (!this._conn || !this._selProduct || !this._selListing) return;
    const priceSelector = this._selPriceSelector.trim();
    const cookies = this._selCookies.trim();
    if (!priceSelector && !cookies) {
      this._selSaveError = "Enter a price selector or cookies first.";
      return;
    }
    const serviceData: Record<string, unknown> = {
      entry_id: this._selProduct.entryId,
      listing_id: this._selListing.listingId,
    };
    if (priceSelector) {
      const titleSelector = this._selTitleSelector.trim() || "h1";
      serviceData.custom_parser = {
        type: "css",
        selectors: { price: priceSelector, title: titleSelector },
        transforms: { price: "price_clean" },
      };
    }
    if (cookies) {
      serviceData.request_cookies = cookies;
    }
    this._selSaving = true;
    this._selSaveError = null;
    this._selSaved = false;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "edit_listing",
        service_data: serviceData,
      });
      this._selSaved = true;
      // Brief success flash, then close. The entry reloads server-side;
      // our registry subscription rebuilds the card.
      window.setTimeout(() => this._closeSelectorEditor(), 1200);
    } catch (err) {
      this._selSaveError =
        (err as { message?: string })?.message ?? "Save failed.";
    } finally {
      this._selSaving = false;
    }
  };

  /**
   * Clear the custom parser on this listing, reverting it to the default
   * JSON-LD + AI extraction pipeline. edit_listing treats an empty
   * custom_parser as "clear". Cookies normally survive a parser edit
   * (they're orthogonal), so a full reset clears them explicitly too —
   * this is also the panel's only way to drop stored cookies.
   */
  private _clearSelector = async (): Promise<void> => {
    if (!this._conn || !this._selProduct || !this._selListing) return;
    if (
      !window.confirm(
        "Remove the custom price selector and any stored cookies, and go " +
          "back to automatic extraction?"
      )
    )
      return;
    this._selSaving = true;
    this._selSaveError = null;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "edit_listing",
        service_data: {
          entry_id: this._selProduct.entryId,
          listing_id: this._selListing.listingId,
          custom_parser: "",
          request_cookies: "",
        },
      });
      this._selSaved = true;
      window.setTimeout(() => this._closeSelectorEditor(), 1200);
    } catch (err) {
      this._selSaveError =
        (err as { message?: string })?.message ?? "Clear failed.";
    } finally {
      this._selSaving = false;
    }
  };

  // --- Variant picker ---

  /**
   * Open the variant picker for one listing. Resets state, opens the
   * overlay, and kicks off the price_watch/list_variants fetch which reads
   * the page's embedded option groups (Wix stores). The user then picks one
   * choice per group; Save pins that combo via set_variant (primary
   * listing) or edit_listing's variant_options (secondary listings).
   */
  private _handleEditVariant = (
    product: TrackedProduct,
    listing: Listing
  ): void => {
    this._varProduct = product;
    this._varListing = listing;
    this._varError = null;
    this._varGroups = null;
    this._varCombos = [];
    this._varSelection = [];
    this._varSupported = true;
    this._varSaveError = null;
    this._varSaved = false;
    this._variantOpen = true;
    void this._loadVariants();
  };

  private _closeVariantPicker = (): void => {
    this._variantOpen = false;
    this._varProduct = null;
    this._varListing = null;
    this._varGroups = null;
    this._varCombos = [];
    this._varSelection = [];
  };

  /**
   * JYSK size chip → switch the tracked page. Each size is its own product
   * URL, so we point the PRIMARY listing at the chosen size's URL via
   * edit_listing; the coordinator then tracks that size on the next refresh.
   */
  private _handleChangeSize = async (
    product: TrackedProduct,
    url: string,
    label: string
  ): Promise<void> => {
    if (!this._conn) return;
    const primary = product.listings.find((l) => l.isPrimary);
    const listingId = primary?.listingId;
    if (!listingId) {
      window.alert("Could not resolve the primary listing to switch size.");
      return;
    }
    if (
      !window.confirm(
        `Track the ${label} size instead?\n\nThis product will follow that size's own page — its price, stock and discount.`
      )
    )
      return;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "edit_listing",
        service_data: { entry_id: product.entryId, listing_id: listingId, url },
      } as never);
    } catch (err) {
      window.alert(
        `Could not switch size: ${
          (err as { message?: string })?.message ?? "unknown error"
        }`
      );
    }
  };

  private _onVariantBackdropClick = (e: Event): void => {
    if (e.target === e.currentTarget) this._closeVariantPicker();
  };

  /**
   * Fetch the listing page's variant option groups via the backend. The
   * server fetches with the same pipeline the poller uses and parses the
   * embedded Wix data. Seeds the per-group selection from the currently-
   * pinned variant so the modal opens on the active combo.
   */
  private _loadVariants = async (): Promise<void> => {
    if (!this._conn || !this._varProduct || !this._varListing) return;
    this._varLoading = true;
    this._varError = null;
    try {
      const req: Record<string, unknown> = {
        type: "price_watch/list_variants",
        entry_id: this._varProduct.entryId,
      };
      // Only target a specific listing for secondaries; the primary uses
      // the product URL + product-level variant on the backend.
      if (!this._varListing.isPrimary) {
        req.listing_id = this._varListing.listingId;
      }
      const resp = await this._conn.sendMessagePromise<ListVariantsResponse>(
        req as never
      );
      this._varSupported = !!resp.supported;
      if (!resp.supported) {
        this._varGroups = null;
        this._varCombos = [];
        this._varSelection = [];
        return;
      }
      const groups = resp.options ?? [];
      this._varGroups = groups;
      this._varCombos = resp.variants ?? [];
      // Pre-select from the currently-pinned variant (case-insensitive
      // match against each group's choices); blank where no match.
      const current = (resp.current ?? []).map((s) => s.toLowerCase());
      this._varSelection = groups.map((g) => {
        const hit = g.choices.find((c) => current.includes(c.toLowerCase()));
        return hit ?? "";
      });
    } catch (err) {
      this._varError =
        (err as { message?: string })?.message ?? "Could not read variants.";
    } finally {
      this._varLoading = false;
    }
  };

  private _onVariantSelect = (groupIndex: number, value: string): void => {
    const next = [...this._varSelection];
    next[groupIndex] = value;
    this._varSelection = next;
  };

  /**
   * The combo matching the current per-group selection, if every group is
   * chosen and that exact combo exists on the page. Drives the live price
   * preview and gates the Save button.
   */
  private _matchedCombo(): VariantCombo | null {
    if (!this._varGroups || this._varGroups.length === 0) return null;
    if (this._varSelection.some((s) => !s)) return null;
    const want = this._varSelection.map((s) => s.toLowerCase());
    return (
      this._varCombos.find((c) => {
        const labels = c.labels.map((l) => l.toLowerCase());
        return want.every((w) => labels.includes(w));
      }) ?? null
    );
  }

  /**
   * Persist the chosen variant. Primary listing → set_variant (writes the
   * product-level fallback used by from-scratch entries). Secondary →
   * edit_listing's variant_options. Both reload the entry server-side.
   */
  private _saveVariant = async (): Promise<void> => {
    if (!this._conn || !this._varProduct || !this._varListing) return;
    const labels = this._varSelection.filter((s) => !!s);
    if (labels.length === 0) {
      this._varSaveError = "Pick an option in each group first.";
      return;
    }
    this._varSaving = true;
    this._varSaveError = null;
    this._varSaved = false;
    try {
      const data: Record<string, unknown> = this._varListing.isPrimary
        ? {
            type: "call_service",
            domain: "price_watch",
            service: "set_variant",
            service_data: {
              entry_id: this._varProduct.entryId,
              variant_options: labels,
            },
          }
        : {
            type: "call_service",
            domain: "price_watch",
            service: "edit_listing",
            service_data: {
              entry_id: this._varProduct.entryId,
              listing_id: this._varListing.listingId,
              variant_options: labels,
            },
          };
      await this._conn.sendMessagePromise(data as never);
      this._varSaved = true;
      window.setTimeout(() => this._closeVariantPicker(), 1200);
    } catch (err) {
      this._varSaveError =
        (err as { message?: string })?.message ?? "Save failed.";
    } finally {
      this._varSaving = false;
    }
  };

  /**
   * Clear the pinned variant, reverting to the page's default offer. Same
   * service split as save; an empty variant_options clears it.
   */
  private _clearVariant = async (): Promise<void> => {
    if (!this._conn || !this._varProduct || !this._varListing) return;
    if (
      !window.confirm(
        "Stop following a specific variant and go back to the default price?"
      )
    )
      return;
    this._varSaving = true;
    this._varSaveError = null;
    try {
      const data: Record<string, unknown> = this._varListing.isPrimary
        ? {
            type: "call_service",
            domain: "price_watch",
            service: "set_variant",
            service_data: {
              entry_id: this._varProduct.entryId,
              variant_options: [],
            },
          }
        : {
            type: "call_service",
            domain: "price_watch",
            service: "edit_listing",
            service_data: {
              entry_id: this._varProduct.entryId,
              listing_id: this._varListing.listingId,
              variant_options: [],
            },
          };
      await this._conn.sendMessagePromise(data as never);
      this._varSaved = true;
      window.setTimeout(() => this._closeVariantPicker(), 1200);
    } catch (err) {
      this._varSaveError =
        (err as { message?: string })?.message ?? "Clear failed.";
    } finally {
      this._varSaving = false;
    }
  };

  /** Build the javascript: href for the draggable picker bookmarklet. */
  private _bookmarkletHref(): string {
    // Collapse the readable source to a single javascript: URL. We strip
    // comment-free source as-is; encodeURIComponent keeps it valid in an
    // href attribute. Wrapped in void() so clicking the live link (if the
    // user clicks instead of dragging) is a no-op rather than navigating.
    return "javascript:" + encodeURIComponent(BOOKMARKLET_SOURCE);
  }

  private _copyBookmarklet = async (): Promise<void> => {
    const code = this._bookmarkletHref();
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      this._selBookmarkletOpen = true; // reveal the textarea for manual copy
    }
  };

  private _handleToggleHideNonShipping = (): void => {
    this._hideNonShipping = !this._hideNonShipping;
    try {
      localStorage.setItem(
        PriceWatchPanel.HIDE_NONSHIP_KEY,
        this._hideNonShipping ? "1" : "0"
      );
    } catch {
      // Non-fatal — the toggle still works for this session.
    }
  };

  private _handleToggleHideDiscontinued = (): void => {
    this._hideDiscontinued = !this._hideDiscontinued;
    try {
      localStorage.setItem(
        PriceWatchPanel.HIDE_DISCONTINUED_KEY,
        this._hideDiscontinued ? "1" : "0"
      );
    } catch {
      // Non-fatal.
    }
  };

  private _handleSearch = (e: Event): void => {
    this._search = (e.target as HTMLInputElement).value;
  };

  private _handleSort = (e: Event): void => {
    const value = (e.target as HTMLSelectElement).value as SortKey;
    this._sort = value;
    try {
      localStorage.setItem(PriceWatchPanel.SORT_KEY, value);
    } catch {
      // Non-fatal.
    }
  };

  /**
   * Force an immediate price re-check for one product.
   *
   * Fires price_watch.refresh_now. While in flight, the entry sits in
   * _refreshingNow so the card spins its refresh button. The coordinator
   * pushes new state when the check completes; our state_changed
   * subscription updates the card. Independent of the alternatives
   * search spinner (_refreshingEntries).
   */
  private _handleRefreshNow = async (
    product: TrackedProduct
  ): Promise<void> => {
    if (!this._conn) return;
    if (this._refreshingNow.has(product.entryId)) return;
    this._refreshingNow = new Set([...this._refreshingNow, product.entryId]);
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "refresh_now",
        service_data: { entry_id: product.entryId },
      });
    } catch (err) {
      console.error("[price-watch-panel] refresh_now failed:", err);
    } finally {
      const next = new Set(this._refreshingNow);
      next.delete(product.entryId);
      this._refreshingNow = next;
    }
  };

  /**
   * Set (or clear) the target price for one product inline.
   *
   * Fires price_watch.set_target. A null/undefined value clears the
   * target server-side. The coordinator persists it to options and
   * re-pushes the price sensor (whose target_price attribute we read),
   * so the card reflects the change after the state_changed round-trip.
   */
  private _handleSetTarget = async (
    product: TrackedProduct,
    target: number | null
  ): Promise<void> => {
    if (!this._conn) return;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "set_target",
        service_data:
          target === null
            ? { entry_id: product.entryId }
            : { entry_id: product.entryId, target_price: target },
      });
    } catch (err) {
      console.error("[price-watch-panel] set_target failed:", err);
    }
  };

  /**
   * Pause or resume polling for one product inline.
   *
   * Fires price_watch.set_paused. The coordinator persists CONF_PAUSED
   * and stops/restarts its update loop; the price sensor's `paused`
   * attribute updates so the card's toggle and badge reflect the new
   * state after the round-trip.
   */
  private _handleSetPaused = async (
    product: TrackedProduct,
    paused: boolean
  ): Promise<void> => {
    if (!this._conn) return;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "set_paused",
        service_data: { entry_id: product.entryId, paused },
      });
    } catch (err) {
      console.error("[price-watch-panel] set_paused failed:", err);
    }
  };

  /**
   * Apply the search filter, hide-discontinued filter, and current sort
   * to the product list. Returns a new array; never mutates _products.
   *
   * Search matches title or retailer, case-insensitive. Sorting is
   * stable-ish (Array.sort) with sensible tiebreaks; products missing
   * the sort's key sink to the bottom rather than throwing off the order.
   */
  private _visibleProducts(): TrackedProduct[] {
    const q = this._search.trim().toLowerCase();
    let list = this._products.filter((p) => {
      if (this._hideDiscontinued && p.discontinued) return false;
      if (!q) return true;
      const hay = `${p.title} ${p.retailer ?? ""}`.toLowerCase();
      return hay.includes(q);
    });

    const byName = (a: TrackedProduct, b: TrackedProduct) =>
      a.title.localeCompare(b.title);

    // Push nulls to the end regardless of sort direction.
    const nlast = (v: number | null): number =>
      v === null ? Number.POSITIVE_INFINITY : v;

    list = [...list].sort((a, b) => {
      switch (this._sort) {
        case "cheapest":
          return nlast(a.price) - nlast(b.price) || byName(a, b);
        case "last_checked": {
          // Most recently checked first. Missing timestamps sink.
          const ta = a.lastCheck ? Date.parse(a.lastCheck) : -Infinity;
          const tb = b.lastCheck ? Date.parse(b.lastCheck) : -Infinity;
          return tb - ta || byName(a, b);
        }
        case "drop": {
          // Biggest drop from the highest seen price (a "deal" sort):
          // discount = highest - price, descending. Products without
          // both numbers get zero discount and sort after real drops.
          const da =
            a.highest !== null && a.price !== null ? a.highest - a.price : -1;
          const db =
            b.highest !== null && b.price !== null ? b.highest - b.price : -1;
          return db - da || byName(a, b);
        }
        case "below_target": {
          // Products at/under target first, ordered by how far under.
          const under = (p: TrackedProduct): number =>
            p.targetPrice !== null && p.price !== null && p.price <= p.targetPrice
              ? p.targetPrice - p.price
              : -1;
          return under(b) - under(a) || byName(a, b);
        }
        case "name":
        default:
          return byName(a, b);
      }
    });
    return list;
  }

  private _handleAddProduct = (): void => {
    const url = "/config/integrations/dashboard/add?domain=price_watch";
    window.history.pushState(null, "", url);
    window.dispatchEvent(new CustomEvent("location-changed"));
  };

  // --- Live search handlers ---

  private _openSearch = (): void => {
    this._searchOpen = true;
    this._trackTarget = null;
    this._trackError = null;
  };

  private _closeSearch = (): void => {
    this._searchOpen = false;
    this._trackTarget = null;
    this._searchError = null;
    this._trackError = null;
  };

  /** Backdrop click closes; clicks inside the dialog are swallowed. */
  private _onBackdropClick = (e: Event): void => {
    if (e.target === e.currentTarget) this._closeSearch();
  };

  private _handleSearchQueryInput = (e: Event): void => {
    this._searchQuery = (e.target as HTMLInputElement).value;
  };

  private _handleSearchKeydown = (e: KeyboardEvent): void => {
    if (e.key === "Enter") {
      e.preventDefault();
      void this._runSearch();
    } else if (e.key === "Escape") {
      this._closeSearch();
    }
  };

  /**
   * Run a live product search via the price_watch/search WS command.
   *
   * Unlike the service calls elsewhere, this command RETURNS data in its
   * reply (ranked results), which we render directly — no entity round-
   * trip. On a backend error the WS layer rejects with a message we show
   * inline. The backend auto-selects the engine (AI vs raw DuckDuckGo).
   */
  private _runSearch = async (): Promise<void> => {
    if (!this._conn) return;
    const q = this._searchQuery.trim();
    if (!q || this._searchLoading) return;

    this._searchLoading = true;
    this._searchError = null;
    this._trackTarget = null;
    try {
      const resp = await this._conn.sendMessagePromise<SearchResponse>({
        type: "price_watch/search",
        query: q,
        max_results: SEARCH_MAX_RESULTS,
      });
      this._searchResults = resp.results ?? [];
      this._searchEngine = resp.engine ?? "none";
      this._searchRan = true;
    } catch (err: unknown) {
      // home-assistant-js-websocket rejects with {code, message} on a
      // send_error; fall back to String() for anything else.
      const message =
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : String(err);
      this._searchError = message || "Search failed.";
      this._searchResults = [];
      this._searchRan = true;
      console.error("[price-watch-panel] search failed:", err);
    } finally {
      this._searchLoading = false;
    }
  };

  /** Open the "Track this" confirm form for a chosen result. */
  private _pickResult = (result: SearchResult): void => {
    this._trackTarget = result;
    this._trackName = result.title;
    this._trackUrl = result.url;
    this._trackTargetPrice = "";
    this._trackError = null;
  };

  /** Back out of the confirm form to the results list. */
  private _cancelTrack = (): void => {
    this._trackTarget = null;
    this._trackError = null;
  };

  private _handleTrackNameInput = (e: Event): void => {
    this._trackName = (e.target as HTMLInputElement).value;
  };
  private _handleTrackUrlInput = (e: Event): void => {
    this._trackUrl = (e.target as HTMLInputElement).value;
  };
  private _handleTrackTargetInput = (e: Event): void => {
    this._trackTargetPrice = (e.target as HTMLInputElement).value;
  };

  /**
   * Confirm tracking: fire price_watch.track_product. The backend drives
   * the config flow's panel_track step to create the product entry. On
   * success the new entry's entities arrive via our registry
   * subscription and a card appears; we close the modal. On failure
   * (e.g. already tracked) we show the error in the dialog.
   */
  private _confirmTrack = async (): Promise<void> => {
    if (!this._conn || this._tracking) return;
    const url = this._trackUrl.trim();
    if (!url) {
      this._trackError = "A URL is required to track a product.";
      return;
    }
    const name = this._trackName.trim();
    const targetRaw = this._trackTargetPrice.trim();
    let targetPrice: number | null = null;
    if (targetRaw !== "") {
      const parsed = Number(targetRaw);
      if (Number.isNaN(parsed)) {
        this._trackError = "Target price must be a number.";
        return;
      }
      targetPrice = parsed;
    }

    this._tracking = true;
    this._trackError = null;
    try {
      await this._conn.sendMessagePromise({
        type: "call_service",
        domain: "price_watch",
        service: "track_product",
        service_data: {
          url,
          ...(name ? { name } : {}),
          ...(targetPrice !== null ? { target_price: targetPrice } : {}),
        },
      });
      // Success — close the whole modal. The new card shows up when the
      // entity_registry_updated subscription refreshes.
      this._closeSearch();
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : String(err);
      this._trackError = message || "Could not add product.";
      console.error("[price-watch-panel] track_product failed:", err);
    } finally {
      this._tracking = false;
    }
  };

  // --- AI provider editor handlers ---

  /** Normalize a WS reject ({code, message}) or any throw to a string. */
  private _wsErrorMessage(err: unknown): string {
    return err && typeof err === "object" && "message" in err
      ? String((err as { message: unknown }).message)
      : String(err);
  }

  /** Copy a settings snapshot into the editable form fields. */
  private _applyProviderSettings(s: ProviderSettings): void {
    this._providerModels = s.anthropic_models ?? [];
    this._pProvider = s.provider;
    this._pModel = s.model || this._providerModels[0] || "";
    this._pBaseUrl = s.base_url ?? "";
    this._providerHasKey = !!s.has_api_key;
    this._pApiKey = ""; // never prefilled — blank means "keep stored key"
    this._pInputCost = String(s.input_cost_per_mtok ?? 0);
    this._pOutputCost = String(s.output_cost_per_mtok ?? 0);
    this._pMaxHtml = String(s.max_html_chars ?? 100000);
    this._pForceJson = !!s.force_json_mode;
    this._pExtraHeaders = s.extra_headers ?? "";
    this._pExcludedDomains = (s.excluded_domains ?? []).join("\n");
    this._pFallbackOnly = !!s.ai_fallback_only;
    this._pStoreOfferLinks = (s.store_offer_links ?? [])
      .map((l) => `${l.host} | ${l.url}`)
      .join("\n");
  }

  /**
   * Open the provider editor and load current settings.
   *
   * Fetches price_watch/get_provider_settings (which never returns the
   * raw API key — only has_api_key) and seeds the form. Errors surface
   * inline in the modal.
   */
  private _openProviderEditor = async (): Promise<void> => {
    this._providerOpen = true;
    this._providerError = null;
    this._providerSuccess = false;
    this._providerAdvancedOpen = false;
    if (!this._conn) {
      this._providerError = "Not connected to Home Assistant yet.";
      return;
    }
    this._providerLoading = true;
    try {
      const s = await this._conn.sendMessagePromise<ProviderSettings>({
        type: "price_watch/get_provider_settings",
      });
      this._applyProviderSettings(s);
    } catch (err) {
      this._providerError =
        this._wsErrorMessage(err) || "Could not load provider settings.";
      console.error("[price-watch-panel] get_provider_settings failed:", err);
    } finally {
      this._providerLoading = false;
    }
  };

  private _closeProviderEditor = (): void => {
    this._providerOpen = false;
    this._providerError = null;
    this._providerSuccess = false;
  };

  /** Backdrop click closes; clicks inside the dialog are swallowed. */
  private _onProviderBackdropClick = (e: Event): void => {
    if (e.target === e.currentTarget) this._closeProviderEditor();
  };

  private _onProviderChange = (e: Event): void => {
    this._pProvider = (e.target as HTMLSelectElement).value as ProviderKind;
    this._providerSuccess = false;
    this._providerError = null;
  };

  /**
   * Validate + persist provider settings via price_watch/set_provider_settings.
   *
   * The backend re-validates credentials (same path as HA's config flow)
   * and, on success, reloads every product entry so coordinators rebuild
   * their AI provider. We send the API key field ONLY when the user typed
   * one — a blank field tells the backend to keep the stored key. On a
   * typed WS error we show the backend's message inline; nothing is saved.
   */
  private _saveProvider = async (): Promise<void> => {
    if (!this._conn || this._providerSaving) return;
    this._providerSaving = true;
    this._providerError = null;
    this._providerSuccess = false;

    const payload: Record<string, unknown> = { provider: this._pProvider };
    // Blank key = keep existing. Only send a non-empty typed key.
    const typedKey = this._pApiKey.trim();
    if (typedKey) payload.api_key = typedKey;

    if (this._pProvider === "anthropic") {
      payload.model = this._pModel;
    } else if (this._pProvider === "openai_compatible") {
      payload.base_url = this._pBaseUrl.trim();
      payload.model = this._pModel.trim();
      payload.input_cost_per_mtok = Number(this._pInputCost) || 0;
      payload.output_cost_per_mtok = Number(this._pOutputCost) || 0;
      payload.max_html_chars = Number(this._pMaxHtml) || 100000;
      payload.force_json_mode = this._pForceJson;
      const headers = this._pExtraHeaders.trim();
      if (headers) payload.extra_headers = headers;
    }

    // Global blocklist — independent of the provider, so always sent.
    // The backend splits on newlines/commas and normalizes each host.
    payload.excluded_domains = this._pExcludedDomains;
    // Fallback-only flag — only meaningful with a provider, but always sent
    // so toggling it off persists too.
    payload.ai_fallback_only = this._pFallbackOnly;
    // Store offer links — "host | url" lines; backend parses + normalizes.
    payload.store_offer_links = this._pStoreOfferLinks;

    try {
      const s = await this._conn.sendMessagePromise<SetProviderResponse>({
        type: "price_watch/set_provider_settings",
        ...payload,
      });
      this._applyProviderSettings(s);
      this._providerSuccess = true;
    } catch (err) {
      this._providerError =
        this._wsErrorMessage(err) || "Could not save provider settings.";
      console.error("[price-watch-panel] set_provider_settings failed:", err);
    } finally {
      this._providerSaving = false;
    }
  };

  // --- Alert ("notify me") dialog ---

  private _handleAlert = (product: TrackedProduct): void => {
    this._alertProduct = product;
    this._alertTrigger = "back_in_stock";
    this._alertSelected = new Set();
    this._alertError = null;
    this._alertSaved = null;
    this._alertOpen = true;
    void this._loadNotifyTargets();
  };

  private _closeAlert = (): void => {
    this._alertOpen = false;
    this._alertProduct = null;
  };

  private _onAlertBackdropClick = (e: Event): void => {
    if (e.target === e.currentTarget) this._closeAlert();
  };

  /** Fetch the notify.* targets for the device picker. */
  private _loadNotifyTargets = async (): Promise<void> => {
    if (!this._conn) return;
    this._alertLoading = true;
    this._alertError = null;
    try {
      const resp = await this._conn.sendMessagePromise<{ targets: NotifyTarget[] }>({
        type: "price_watch/list_notify_targets",
      });
      this._alertTargets = resp.targets ?? [];
    } catch (err) {
      this._alertError =
        (err as { message?: string })?.message ?? "Could not load notify targets.";
    } finally {
      this._alertLoading = false;
    }
  };

  private _setAlertTrigger = (t: AlertTrigger): void => {
    this._alertTrigger = t;
  };

  private _toggleAlertTarget = (service: string): void => {
    const next = new Set(this._alertSelected);
    if (next.has(service)) next.delete(service);
    else next.add(service);
    this._alertSelected = next;
  };

  /**
   * POST an automation config to HA's REST endpoint — the same mechanism
   * HA's own automation editor uses, so HA owns validation, storage location
   * (automations.yaml vs storage), and the reload. We pull the access token
   * off the bootstrapped connection's Auth object.
   */
  private async _createAutomation(uniqueId: string, config: unknown): Promise<void> {
    const wrapper = await window.hassConnection;
    const auth = wrapper?.auth;
    const token = auth?.accessToken ?? auth?.data?.access_token;
    const resp = await fetch(
      `/api/config/automation/config/${encodeURIComponent(uniqueId)}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(config),
      }
    );
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `Home Assistant rejected the automation (HTTP ${resp.status}). ${text.slice(0, 180)}`
      );
    }
  }

  /** Build the alert automation from the dialog and create it via HA. */
  private _createAlert = async (): Promise<void> => {
    const product = this._alertProduct;
    if (!product) return;
    const services = [...this._alertSelected];
    if (services.length === 0) {
      this._alertError = "Pick at least one device to notify.";
      return;
    }
    const trigger = this._alertTrigger;
    const eventType = ALERT_EVENT[trigger];

    // Per-trigger title + message. The bus event payload carries title,
    // price, currency, previous_price, target and url, so the message is
    // rich and independent of entity_id renames.
    const COPY: Record<AlertTrigger, { emoji: string; title: string; body: string }> = {
      back_in_stock: {
        emoji: "🛒",
        title: "Back in stock!",
        body: "{{ trigger.event.data.title }} is back in stock at {{ trigger.event.data.price }} {{ trigger.event.data.currency }}",
      },
      below_target: {
        emoji: "🎯",
        title: "Target price hit!",
        body: "{{ trigger.event.data.title }} hit your target — now {{ trigger.event.data.price }} {{ trigger.event.data.currency }}",
      },
      price_drop: {
        emoji: "📉",
        title: "Price drop",
        body: "{{ trigger.event.data.title }}: {{ trigger.event.data.price }} {{ trigger.event.data.currency }} (was {{ trigger.event.data.previous_price }})",
      },
      on_sale: {
        emoji: "🏷️",
        title: "On sale!",
        body: "{{ trigger.event.data.title }} is on sale — {{ trigger.event.data.price }} {{ trigger.event.data.currency }} (was {{ trigger.event.data.original_price }}), −{{ trigger.event.data.discount_percent }}%",
      },
    };
    const copy = COPY[trigger];
    const action = services.map((svc) => ({
      service: svc,
      data: {
        title: `${copy.emoji} ${copy.title}`,
        message: copy.body,
        data: { url: "{{ trigger.event.data.url }}" },
      },
    }));

    const config = {
      alias: `Price Watch: ${product.title} — ${copy.title}`,
      description: "Created via the Price Watch panel's Alert-me button.",
      mode: "single",
      trigger: [
        {
          platform: "event",
          event_type: eventType,
          event_data: { entry_id: product.entryId },
        },
      ],
      action,
    };
    // Stable id → re-creating the same product+trigger updates in place
    // rather than piling up duplicates.
    const uniqueId = `pw_alert_${product.entryId.toLowerCase()}_${trigger}`;

    this._alertSaving = true;
    this._alertError = null;
    this._alertSaved = null;
    try {
      await this._createAutomation(uniqueId, config);
      this._alertSaved = config.alias;
      window.setTimeout(() => this._closeAlert(), 1600);
    } catch (err) {
      this._alertError =
        (err as { message?: string })?.message ?? "Could not create the alert.";
    } finally {
      this._alertSaving = false;
    }
  };

  /**
   * Jump to Home Assistant's Price Watch integration page (Settings →
   * Devices & Services → Price Watch), where the settings entry's region,
   * currency, budgets, and the add/remove-product config live. The panel
   * renders in the main HA document (embed_iframe=False), so we navigate
   * with HA's client-side router — pushState + a "location-changed" event —
   * rather than a full page reload.
   */
  private _openIntegrationSettings = (): void => {
    const path = "/config/integrations/integration/price_watch";
    window.history.pushState(null, "", path);
    window.dispatchEvent(
      new CustomEvent("location-changed", { detail: { replace: false } })
    );
  };

  private _renderHeader() {
    return html`
      <header class="panel-header">
        <div class="panel-header__title">
          <h1>Price Watch</h1>
        </div>
        <div class="panel-header__actions">
          <button
            class="add-button add-button--secondary"
            @click=${this._openIntegrationSettings}
            title="Open the Price Watch integration page in Home Assistant settings — region, currency, budgets, and tracked products"
          >
            🛠 Settings
          </button>
          <button
            class="add-button add-button--secondary"
            @click=${this._openProviderEditor}
            title="Choose AI provider (Free / Anthropic / OpenAI-compatible)"
          >
            ⚙ AI provider
          </button>
          <button
            class="add-button add-button--secondary"
            @click=${this._openSearch}
          >
            🔍 Search &amp; add
          </button>
          <button class="add-button" @click=${this._handleAddProduct}>
            + Add product
          </button>
        </div>
      </header>
    `;
  }

  /**
   * The live-search overlay. Two modes in one dialog: the results list
   * (default) and the "Track this" confirm form (when _trackTarget set).
   * Rendered at the panel root so it overlays everything; nothing renders
   * when closed.
   */
  private _renderSearchModal() {
    if (!this._searchOpen) return null;
    return html`
      <div
        class="modal-backdrop"
        @click=${this._onBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Search and add a product"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>${this._trackTarget ? "Track this product" : "Search & add"}</h2>
            <button
              class="modal__close"
              @click=${this._closeSearch}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          ${this._trackTarget
            ? this._renderTrackForm()
            : this._renderSearchBody()}
        </div>
      </div>
    `;
  }

  private _renderSearchBody() {
    return html`
      <div class="modal__searchbar">
        <input
          type="search"
          class="modal__searchinput"
          placeholder="Search for a product to track…"
          .value=${this._searchQuery}
          @input=${this._handleSearchQueryInput}
          @keydown=${this._handleSearchKeydown}
          aria-label="Product search query"
          autofocus
        />
        <button
          class="add-button"
          @click=${this._runSearch}
          ?disabled=${this._searchLoading || !this._searchQuery.trim()}
        >
          ${this._searchLoading ? "Searching…" : "Search"}
        </button>
      </div>
      ${this._renderSearchResults()}
    `;
  }

  private _renderSearchResults() {
    if (this._searchLoading) {
      return html`<div class="modal__status">Searching the web…</div>`;
    }
    if (this._searchError) {
      return html`
        <div class="modal__status modal__status--error">
          ⚠ ${this._searchError}
        </div>
      `;
    }
    if (!this._searchRan) {
      return html`
        <div class="modal__status">
          Type what you're looking for and press Enter — e.g. a product
          name, model number, or brand.
        </div>
      `;
    }
    if (this._searchResults.length === 0) {
      return html`
        <div class="modal__status">
          No results. Try a different or more specific query.
        </div>
      `;
    }
    // Count how many rows the heuristic flagged as non-stores, so the
    // toggle can show "(N)" and we only render it when it'd do something.
    const nonShopCount = this._searchResults.filter(
      (r) => r.likely_non_shop
    ).length;
    const visible = this._hideNonShops
      ? this._searchResults.filter((r) => !r.likely_non_shop)
      : this._searchResults;
    return html`
      <div class="results-bar">
        <div class="modal__engine">${ENGINE_LABELS[this._searchEngine]}</div>
        ${nonShopCount > 0
          ? html`<label
              class="results-bar__toggle"
              title="Hide GitHub, YouTube, wikis, forums and other non-store results"
            >
              <input
                type="checkbox"
                .checked=${this._hideNonShops}
                @change=${this._handleHideNonShopsToggle}
              />
              Hide non-stores (${nonShopCount})
            </label>`
          : null}
      </div>
      ${visible.length === 0
        ? html`<div class="modal__status">
            All ${this._searchResults.length} results were non-stores and are
            hidden. Untick "Hide non-stores" to see them.
          </div>`
        : html`<ul class="results">
            ${visible.map((r) => this._renderResultRow(r))}
          </ul>`}
    `;
  }

  private _handleHideNonShopsToggle = (e: Event) => {
    this._hideNonShops = (e.target as HTMLInputElement).checked;
    try {
      localStorage.setItem(
        PriceWatchPanel.HIDE_NONSHOPS_KEY,
        this._hideNonShops ? "1" : "0"
      );
    } catch {
      // Ignore — preference just won't persist in locked-down contexts.
    }
  };

  private _renderResultRow(r: SearchResult) {
    const price =
      r.price !== null
        ? `${r.price} ${r.currency}`.trim()
        : "Price unknown";
    const ships =
      r.ships_to_user_region === true
        ? html`<span class="results__ship results__ship--yes">Ships to you</span>`
        : r.ships_to_user_region === false
        ? html`<span class="results__ship results__ship--no">Doesn't ship</span>`
        : null;
    // Free-mode hint: flag obvious non-shops (repo/video/wiki/docs) so the
    // user doesn't try to track a guide as if it were a seller.
    const notAShop = r.likely_non_shop
      ? html`<span class="results__kind results__kind--info"
          >not a store?</span
        >`
      : null;
    return html`
      <li class="results__row ${r.likely_non_shop ? "results__row--muted" : ""}">
        <div class="results__thumb">
          ${r.image_url
            ? html`<img src=${r.image_url} alt="" loading="lazy" />`
            : html`<span class="results__thumb-ph">🏷️</span>`}
        </div>
        <div class="results__info">
          <a
            class="results__title results__title--link"
            href=${r.url}
            target="_blank"
            rel="noopener noreferrer"
            title=${`${r.title} — open to verify`}
          >
            ${r.title}
            <span class="results__ext" aria-hidden="true">↗</span>
          </a>
          <div class="results__meta">
            <span class="results__price">${price}</span>
            ${r.retailer
              ? html`<span class="results__retailer">${r.retailer}</span>`
              : null}
            ${notAShop}
            ${ships}
          </div>
          ${r.notes
            ? html`<div class="results__notes">${r.notes}</div>`
            : null}
        </div>
        <div class="results__actions">
          <button class="results__add" @click=${() => this._pickResult(r)}>
            Track
          </button>
          <button
            class="results__exclude"
            @click=${() => this._excludeResultSite(r)}
            ?disabled=${this._excludingHosts.has(this._hostOf(r.url))}
            title=${`Hide ${this._hostOf(r.url) ||
              "this site"} from all current and future searches`}
          >
            ${this._excludingHosts.has(this._hostOf(r.url))
              ? "Excluding…"
              : "Exclude site"}
          </button>
        </div>
      </li>
    `;
  }

  /** Bare lowercase host for a URL (www. stripped), or "" if unparseable. */
  private _hostOf(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./i, "").toLowerCase();
    } catch {
      return "";
    }
  }

  /**
   * Add a search result's site to the global excluded-domains blocklist
   * via price_watch/exclude_domain, then drop every result from that host
   * out of the current list. Future searches honor the blocklist server-
   * side (ws_search filters it), so the site won't come back.
   */
  private _excludeResultSite = async (r: SearchResult): Promise<void> => {
    if (!this._conn) return;
    const host = this._hostOf(r.url);
    if (!host) return;
    this._excludingHosts = new Set(this._excludingHosts).add(host);
    try {
      await this._conn.sendMessagePromise({
        type: "price_watch/exclude_domain",
        domain: host,
      });
      // Drop all rows from this host from the visible results immediately.
      this._searchResults = this._searchResults.filter(
        (row) => this._hostOf(row.url) !== host
      );
    } catch (err) {
      this._searchError =
        (err as { message?: string })?.message ??
        `Could not exclude ${host}.`;
    } finally {
      const next = new Set(this._excludingHosts);
      next.delete(host);
      this._excludingHosts = next;
    }
  };

  /**
   * Add an alternative's site to the global excluded-domains blocklist via
   * price_watch/exclude_domain, then hide that host's alternatives on every
   * card immediately. The blocklist is honored server-side on the next
   * find_alternatives / search, so the site won't return.
   */
  private _handleExcludeAlternative = async (
    _product: TrackedProduct,
    alt: Alternative
  ): Promise<void> => {
    if (!this._conn) return;
    const host = this._hostOf(alt.url ?? "");
    if (!host) return;
    try {
      await this._conn.sendMessagePromise({
        type: "price_watch/exclude_domain",
        domain: host,
      });
      this._hiddenAltHosts = new Set(this._hiddenAltHosts).add(host);
    } catch (err) {
      window.alert(
        `Could not exclude ${host}: ${
          (err as { message?: string })?.message ?? "unknown error"
        }`
      );
    }
  };

  private _renderTrackForm() {
    const r = this._trackTarget;
    return html`
      <div class="trackform">
        ${r && r.price !== null
          ? html`<div class="trackform__hint">
              Currently ${r.price} ${r.currency} at
              ${r.retailer || "this retailer"}.
            </div>`
          : null}
        <label class="trackform__field">
          <span>Name</span>
          <input
            type="text"
            .value=${this._trackName}
            @input=${this._handleTrackNameInput}
            placeholder="Display name"
          />
        </label>
        <label class="trackform__field">
          <span>URL</span>
          <input
            type="url"
            .value=${this._trackUrl}
            @input=${this._handleTrackUrlInput}
            placeholder="https://…"
          />
        </label>
        <label class="trackform__field">
          <span>Target price <em>(optional)</em></span>
          <input
            type="number"
            step="any"
            .value=${this._trackTargetPrice}
            @input=${this._handleTrackTargetInput}
            placeholder="Alert when at or below…"
          />
        </label>
        ${this._trackError
          ? html`<div class="modal__status modal__status--error">
              ⚠ ${this._trackError}
            </div>`
          : null}
        <div class="trackform__actions">
          <button class="trackform__cancel" @click=${this._cancelTrack}>
            Back
          </button>
          <button
            class="add-button"
            @click=${this._confirmTrack}
            ?disabled=${this._tracking || !this._trackUrl.trim()}
          >
            ${this._tracking ? "Adding…" : "Track product"}
          </button>
        </div>
      </div>
    `;
  }

  /**
   * The AI-provider editor overlay. Mirrors HA's options flow: pick Free /
   * Anthropic / OpenAI-compatible and fill the relevant credentials, then
   * Save & apply (which validates server-side and reloads products).
   * Rendered at the panel root; nothing renders when closed.
   */
  private _renderProviderModal() {
    if (!this._providerOpen) return null;
    return html`
      <div
        class="modal-backdrop"
        @click=${this._onProviderBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="AI provider settings"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>AI provider</h2>
            <button
              class="modal__close"
              @click=${this._closeProviderEditor}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          ${this._providerLoading
            ? html`<div class="modal__status">Loading current settings…</div>`
            : this._renderProviderForm()}
        </div>
      </div>
    `;
  }

  private _renderProviderForm() {
    return html`
      <div class="trackform">
        <label class="trackform__field">
          <span>Provider</span>
          <select @change=${this._onProviderChange}>
            ${(["none", "anthropic", "openai_compatible"] as ProviderKind[]).map(
              (kind) => html`
                <option value=${kind} ?selected=${this._pProvider === kind}>
                  ${PROVIDER_LABELS[kind]}
                </option>
              `
            )}
          </select>
        </label>

        ${this._pProvider === "none" ? this._renderNoneInfo() : null}
        ${this._pProvider === "anthropic"
          ? this._renderAnthropicFields()
          : null}
        ${this._pProvider === "openai_compatible"
          ? this._renderOpenAIFields()
          : null}

        ${this._pProvider !== "none" ? this._renderFallbackOnly() : null}

        ${this._renderExcludedDomains()}
        ${this._renderStoreOfferLinks()}

        ${this._providerError
          ? html`<div class="modal__status modal__status--error">
              ⚠ ${this._providerError}
            </div>`
          : null}
        ${this._providerSuccess
          ? html`<div class="modal__status modal__status--ok">
              ✓ Saved — reloading tracked products to apply the change.
            </div>`
          : null}

        <div class="trackform__actions">
          <button
            class="trackform__cancel"
            @click=${this._closeProviderEditor}
          >
            Close
          </button>
          <button
            class="add-button"
            @click=${this._saveProvider}
            ?disabled=${this._providerSaving}
          >
            ${this._providerSaving ? "Saving…" : "Save & apply"}
          </button>
        </div>
      </div>
    `;
  }

  /**
   * "Fallback-only" toggle: keep alternatives search on free DuckDuckGo and
   * use the configured AI ONLY when free/JSON-LD price extraction can't read
   * a price. Lets a user run fast/free search with an AI safety net for odd
   * product pages. Shown only when an AI provider is selected.
   */
  private _renderFallbackOnly() {
    return html`
      <label class="ship-toggle provider__check">
        <input
          type="checkbox"
          .checked=${this._pFallbackOnly}
          @change=${(e: Event) =>
            (this._pFallbackOnly = (e.target as HTMLInputElement).checked)}
        />
        <span>Use AI only as a price-fetch fallback</span>
      </label>
      <div class="trackform__hint">
        Alternatives search stays on free DuckDuckGo; the AI is used only when
        free price extraction can't read a price. Leave off to also use the AI
        for richer alternative search.
      </div>
    `;
  }

  /**
   * "Store offer links" editor — one "host | url" per line. A card whose
   * listing host matches gets a "Tilboð hjá <store>" link. Editable so a
   * store's offers page (e.g. Húsa's rotating seasonal campaign) can be
   * updated, or new stores added, without a code change.
   */
  private _renderStoreOfferLinks() {
    return html`
      <label class="trackform__field">
        <span>Store offer links</span>
        <textarea
          class="provider__textarea"
          rows="3"
          placeholder="One per line: host | url&#10;byko.is | https://byko.is/tilbod"
          .value=${this._pStoreOfferLinks}
          @input=${(e: Event) =>
            (this._pStoreOfferLinks = (e.target as HTMLTextAreaElement).value)}
        ></textarea>
      </label>
      <div class="trackform__hint">
        Cards from these stores show a <strong>Tilboð hjá …</strong> link to
        the store's seasonal-offers page. Format
        <code>host | url</code> per line (e.g.
        <code>jysk.is | https://jysk.is/tilbodsvorur/</code>). Update Húsa's
        when the seasonal campaign changes.
      </div>
    `;
  }

  /**
   * Global "Excluded sites" editor. One hostname per line; applies to
   * every product's alternatives search and the live Search & add
   * results regardless of which AI provider is selected (hence rendered
   * for all provider modes). Matching is host-suffix based server-side,
   * so "amazon.de" also drops "www.amazon.de" and any subdomain.
   */
  private _renderExcludedDomains() {
    return html`
      <label class="trackform__field">
        <span>Excluded sites</span>
        <textarea
          class="provider__textarea"
          rows="3"
          placeholder="One site per line, e.g.&#10;amazon.de&#10;alza.cz"
          .value=${this._pExcludedDomains}
          @input=${(e: Event) =>
            (this._pExcludedDomains = (e.target as HTMLTextAreaElement).value)}
        ></textarea>
      </label>
      <div class="trackform__hint">
        Retailers listed here are dropped from every alternatives search
        and from Search &amp; add — useful for foreign sites that claim to
        ship to Iceland but you don't want to see. One hostname per line
        (e.g. <code>amazon.de</code>); subdomains are matched too.
      </div>
    `;
  }

  private _renderNoneInfo() {
    return html`
      <div class="trackform__hint">
        Free mode uses DuckDuckGo web search with deterministic price
        extraction — no API key and no per-call cost. AI-powered HTML
        parsing and richer alternative ranking are disabled.
      </div>
    `;
  }

  private _renderAnthropicFields() {
    return html`
      <label class="trackform__field">
        <span>Model</span>
        <select
          @change=${(e: Event) =>
            (this._pModel = (e.target as HTMLSelectElement).value)}
        >
          ${this._providerModels.map(
            (m) => html`
              <option value=${m} ?selected=${this._pModel === m}>${m}</option>
            `
          )}
        </select>
      </label>
      <label class="trackform__field">
        <span>
          API key
          ${this._providerHasKey
            ? html`<em>(leave blank to keep current)</em>`
            : null}
        </span>
        <input
          type="password"
          autocomplete="off"
          .value=${this._pApiKey}
          @input=${(e: Event) =>
            (this._pApiKey = (e.target as HTMLInputElement).value)}
          placeholder=${this._providerHasKey
            ? "•••••• stored — type to replace"
            : "sk-ant-…"}
        />
      </label>
    `;
  }

  private _renderOpenAIFields() {
    return html`
      <label class="trackform__field">
        <span>Base URL</span>
        <input
          type="url"
          .value=${this._pBaseUrl}
          @input=${(e: Event) =>
            (this._pBaseUrl = (e.target as HTMLInputElement).value)}
          placeholder="http://192.168.0.92:11434/v1"
        />
      </label>
      <label class="trackform__field">
        <span>Model</span>
        <input
          type="text"
          .value=${this._pModel}
          @input=${(e: Event) =>
            (this._pModel = (e.target as HTMLInputElement).value)}
          placeholder="qwen2.5:7b"
        />
      </label>
      <label class="trackform__field">
        <span>API key <em>(optional for local endpoints)</em></span>
        <input
          type="password"
          autocomplete="off"
          .value=${this._pApiKey}
          @input=${(e: Event) =>
            (this._pApiKey = (e.target as HTMLInputElement).value)}
          placeholder=${this._providerHasKey
            ? "•••••• stored — type to replace"
            : "optional"}
        />
      </label>

      <button
        type="button"
        class="provider__advtoggle"
        @click=${() => (this._providerAdvancedOpen = !this._providerAdvancedOpen)}
      >
        ${this._providerAdvancedOpen ? "▾" : "▸"} Advanced (cost &amp; format)
      </button>
      ${this._providerAdvancedOpen ? this._renderOpenAIAdvanced() : null}
    `;
  }

  private _renderOpenAIAdvanced() {
    return html`
      <label class="trackform__field">
        <span>Input cost / Mtok (USD)</span>
        <input
          type="number"
          step="any"
          .value=${this._pInputCost}
          @input=${(e: Event) =>
            (this._pInputCost = (e.target as HTMLInputElement).value)}
          placeholder="0"
        />
      </label>
      <label class="trackform__field">
        <span>Output cost / Mtok (USD)</span>
        <input
          type="number"
          step="any"
          .value=${this._pOutputCost}
          @input=${(e: Event) =>
            (this._pOutputCost = (e.target as HTMLInputElement).value)}
          placeholder="0"
        />
      </label>
      <label class="trackform__field">
        <span>Max HTML chars</span>
        <input
          type="number"
          .value=${this._pMaxHtml}
          @input=${(e: Event) =>
            (this._pMaxHtml = (e.target as HTMLInputElement).value)}
          placeholder="100000"
        />
      </label>
      <label class="ship-toggle provider__check">
        <input
          type="checkbox"
          .checked=${this._pForceJson}
          @change=${(e: Event) =>
            (this._pForceJson = (e.target as HTMLInputElement).checked)}
        />
        <span>Force JSON response mode</span>
      </label>
      <label class="trackform__field">
        <span>Extra headers <em>(JSON object)</em></span>
        <textarea
          class="provider__textarea"
          rows="3"
          .value=${this._pExtraHeaders}
          @input=${(e: Event) =>
            (this._pExtraHeaders = (e.target as HTMLTextAreaElement).value)}
          placeholder='{"Authorization": "Bearer …"}'
        ></textarea>
      </label>
    `;
  }

  /**
   * At-a-glance counts across ALL tracked products (not affected by the
   * search box or filters — these are the totals, the toolbar narrows
   * what's shown below). Clicking a chip is intentionally not wired up
   * yet; it's a pure status readout.
   */
  private _renderSummary() {
    const products = this._products;
    const total = products.length;
    const inStock = products.filter((p) => p.inStock === true).length;
    const belowTarget = products.filter(
      (p) =>
        p.targetPrice !== null &&
        p.price !== null &&
        p.price <= p.targetPrice
    ).length;
    const discontinued = products.filter((p) => p.discontinued).length;

    const chip = (label: string, value: number, cls: string) => html`
      <div class="stat ${cls}">
        <span class="stat__value">${value}</span>
        <span class="stat__label">${label}</span>
      </div>
    `;

    return html`
      <div class="summary">
        ${chip("Tracked", total, "stat--total")}
        ${chip("In stock", inStock, "stat--stock")}
        ${chip("Below target", belowTarget, "stat--target")}
        ${chip("Discontinued", discontinued, "stat--disc")}
      </div>
    `;
  }

  /**
   * Toolbar: search box, sort selector, and the two view toggles
   * (ships-to-me, hide-discontinued). Sits between the summary bar and
   * the grid so users can narrow the view without scrolling.
   */
  private _renderToolbar() {
    return html`
      <div class="toolbar">
        <div class="toolbar__search">
          <input
            type="search"
            placeholder="Search products or retailers…"
            .value=${this._search}
            @input=${this._handleSearch}
            aria-label="Search products"
          />
        </div>
        <div class="toolbar__controls">
          <label class="sort-label">
            <span>Sort</span>
            <select @change=${this._handleSort} aria-label="Sort products">
              ${SORT_KEYS.map(
                (key) => html`
                  <option value=${key} ?selected=${this._sort === key}>
                    ${SORT_LABELS[key]}
                  </option>
                `
              )}
            </select>
          </label>
          <label
            class="ship-toggle"
            title="Hide alternatives that don't ship to your region"
          >
            <input
              type="checkbox"
              .checked=${this._hideNonShipping}
              @change=${this._handleToggleHideNonShipping}
            />
            <span>Ships to me only</span>
          </label>
          <label
            class="ship-toggle"
            title="Hide products marked discontinued"
          >
            <input
              type="checkbox"
              .checked=${this._hideDiscontinued}
              @change=${this._handleToggleHideDiscontinued}
            />
            <span>Hide discontinued</span>
          </label>
        </div>
      </div>
    `;
  }

  private _renderEmptyState() {
    return html`
      <div class="empty">
        <div class="empty__icon">🏷️</div>
        <h2>No products tracked yet</h2>
        <p>Add a product to start watching its price.</p>
        <button class="add-button" @click=${this._handleAddProduct}>
          + Add product
        </button>
      </div>
    `;
  }

  private _renderError() {
    return html`
      <div class="error">
        <div class="error__icon">⚠</div>
        <p>${this._registryError}</p>
      </div>
    `;
  }

  private _renderLoading() {
    return html`
      <div class="loading">
        <p>Loading tracked products…</p>
      </div>
    `;
  }

  private _renderGrid() {
    const visible = this._visibleProducts();
    if (visible.length === 0) {
      // Products exist but the search/filters hid them all. Distinct
      // from the no-products-at-all empty state.
      return html`
        <div class="empty">
          <div class="empty__icon">🔍</div>
          <h2>No matches</h2>
          <p>No tracked products match your search or filters.</p>
        </div>
      `;
    }
    return html`
      <div class="grid">
        ${visible.map(
          (p) => html`
            <price-watch-card
              .product=${p}
              .onOpen=${this._handleOpen}
              .onRefreshAlternatives=${this._handleRefreshAlternatives}
              .refreshingAlternatives=${this._refreshingEntries.has(p.entryId)}
              .onRefreshNow=${this._handleRefreshNow}
              .refreshingNow=${this._refreshingNow.has(p.entryId)}
              .onSetTarget=${this._handleSetTarget}
              .onSetPaused=${this._handleSetPaused}
              .hideNonShipping=${this._hideNonShipping}
              .onRemoveListing=${this._handleRemoveListing}
              .onAddListing=${this._handleAddListing}
              .onEditListing=${this._handleEditListing}
              .onEditVariant=${this._handleEditVariant}
              .onAlert=${this._handleAlert}
              .onChangeSize=${this._handleChangeSize}
              .onExcludeAlternative=${this._handleExcludeAlternative}
              .excludedAltHosts=${this._hiddenAltHosts}
            ></price-watch-card>
          `
        )}
      </div>
    `;
  }

  render() {
    const ready = this._connected && this._registry;
    const hasProducts = this._products.length > 0;
    return html`
      <div class="panel">
        ${this._renderHeader()}
        ${this._registryError
          ? this._renderError()
          : !ready
          ? this._renderLoading()
          : !hasProducts
          ? this._renderEmptyState()
          : html`
              ${this._renderSummary()} ${this._renderToolbar()}
              ${this._renderGrid()}
            `}
      </div>
      ${this._renderSearchModal()}
      ${this._renderProviderModal()}
      ${this._renderSelectorModal()}
      ${this._renderVariantModal()}
      ${this._renderAlertModal()}
    `;
  }

  /**
   * The "Alert me" overlay. Pick a trigger (back in stock / target hit /
   * any price drop) and one or more notify devices; on Create it builds a
   * Home Assistant automation (event trigger on the integration's bus event,
   * scoped to this product's entry_id) and saves it via HA's automation
   * config endpoint. Rendered at the panel root; nothing when closed.
   */
  private _renderAlertModal() {
    if (!this._alertOpen || !this._alertProduct) return null;
    const product = this._alertProduct;
    const hasTarget = product.targetPrice != null;
    const triggers: { key: AlertTrigger; label: string; hint: string; disabled?: boolean }[] = [
      {
        key: "back_in_stock",
        label: "Back in stock",
        hint: "When this product returns to stock",
      },
      {
        key: "below_target",
        label: "Target price hit",
        hint: hasTarget
          ? `When the price reaches your target (${product.targetPrice})`
          : "Set a target price on this product first",
        disabled: !hasTarget,
      },
      {
        key: "price_drop",
        label: "Any price drop",
        hint: "Every time the price drops",
      },
      {
        key: "on_sale",
        label: "Goes on sale",
        hint: "When the retailer puts it on sale (a discount appears)",
      },
    ];
    return html`
      <div
        class="modal-backdrop"
        @click=${this._onAlertBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Create a price alert"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>🔔 Alert me</h2>
            <button class="modal__close" @click=${this._closeAlert} aria-label="Close">
              ✕
            </button>
          </div>
          <div class="trackform">
            <p class="sel__intro">
              Get a notification about <strong>${product.title}</strong>. This
              creates a Home Assistant automation for you — no YAML needed.
            </p>

            <div class="alert__section-label">When</div>
            <div class="alert__triggers">
              ${triggers.map(
                (t) => html`
                  <label
                    class="alert__trigger ${this._alertTrigger === t.key
                      ? "alert__trigger--on"
                      : ""} ${t.disabled ? "alert__trigger--disabled" : ""}"
                  >
                    <input
                      type="radio"
                      name="pw-alert-trigger"
                      .checked=${this._alertTrigger === t.key}
                      ?disabled=${t.disabled}
                      @change=${() => this._setAlertTrigger(t.key)}
                    />
                    <span class="alert__trigger-body">
                      <span class="alert__trigger-label">${t.label}</span>
                      <span class="alert__trigger-hint">${t.hint}</span>
                    </span>
                  </label>
                `
              )}
            </div>

            <div class="alert__section-label">Notify</div>
            ${this._alertLoading
              ? html`<div class="modal__status">Loading your devices…</div>`
              : this._alertTargets.length === 0
              ? html`<div class="modal__status">
                  No notify devices found. Set up the Home Assistant mobile app
                  to get push notifications.
                </div>`
              : html`<div class="alert__targets">
                  ${this._alertTargets.map(
                    (t) => html`
                      <label class="alert__target">
                        <input
                          type="checkbox"
                          .checked=${this._alertSelected.has(t.service)}
                          @change=${() => this._toggleAlertTarget(t.service)}
                        />
                        <span>${t.label}</span>
                      </label>
                    `
                  )}
                </div>`}

            ${this._alertError
              ? html`<div class="modal__status modal__status--error">
                  ⚠ ${this._alertError}
                </div>`
              : null}
            ${this._alertSaved
              ? html`<div class="modal__status modal__status--ok">
                  ✓ Created "${this._alertSaved}". You'll be notified.
                </div>`
              : null}

            <div class="trackform__actions sel__actions">
              <button class="trackform__cancel" @click=${this._closeAlert}>
                Cancel
              </button>
              <button
                class="add-button"
                @click=${this._createAlert}
                ?disabled=${this._alertSaving || this._alertSelected.size === 0}
              >
                ${this._alertSaving ? "Creating…" : "Create alert"}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * The variant picker overlay. Reads the listing page's embedded option
   * groups (Wix stores) and renders one dropdown per group plus a live
   * price preview, so the user can follow a specific combo (e.g. "with IR
   * remote") instead of the default offer. Rendered at the panel root;
   * nothing renders when closed.
   */
  private _renderVariantModal() {
    if (!this._variantOpen || !this._varListing) return null;
    const listing = this._varListing;
    const product = this._varProduct;
    const groups = this._varGroups;
    const matched = this._matchedCombo();
    const incomplete = this._varSelection.some((s) => !s);
    return html`
      <div
        class="modal-backdrop"
        @click=${this._onVariantBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Choose product variant"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>Choose variant</h2>
            <button
              class="modal__close"
              @click=${this._closeVariantPicker}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div class="trackform">
            <p class="sel__intro">
              For ${listing.retailer || "this listing"}${product
                ? html` on <strong>${product.title}</strong>`
                : null}. Pick the exact combination you want to track — the
              price below updates to match, and the tracker follows it from
              the next check on.
            </p>

            ${this._varLoading
              ? html`<div class="modal__status">Reading variants…</div>`
              : null}
            ${this._varError
              ? html`<div class="modal__status modal__status--error">
                  ⚠ ${this._varError}
                </div>`
              : null}
            ${!this._varLoading && !this._varError && !this._varSupported
              ? html`<div class="modal__status">
                  This page doesn't expose selectable variants, so there's
                  nothing to pin — it already tracks its only price.
                </div>`
              : null}

            ${groups && this._varSupported
              ? html`
                  <div class="var__groups">
                    ${groups.map(
                      (g, gi) => html`
                        <label class="trackform__field">
                          <span>${g.title}</span>
                          <select
                            class="var__select"
                            .value=${this._varSelection[gi] ?? ""}
                            @change=${(e: Event) =>
                              this._onVariantSelect(
                                gi,
                                (e.target as HTMLSelectElement).value
                              )}
                          >
                            <option value="" ?selected=${!this
                              ._varSelection[gi]}>
                              — choose —
                            </option>
                            ${g.choices.map(
                              (c) => html`<option
                                value=${c}
                                ?selected=${this._varSelection[gi] === c}
                              >
                                ${c}
                              </option>`
                            )}
                          </select>
                        </label>
                      `
                    )}
                  </div>

                  <div class="var__preview">
                    ${matched
                      ? html`<span class="var__price"
                            >${this._formatVariantPrice(matched)}</span
                          >
                          ${matched.in_stock
                            ? null
                            : html`<span class="var__oos"
                                >out of stock</span
                              >`}`
                      : incomplete
                      ? html`<span class="var__hint"
                          >Pick an option in each group to see the price.</span
                        >`
                      : html`<span class="var__hint var__hint--warn"
                          >That combination isn't available on the page.</span
                        >`}
                  </div>
                `
              : null}

            ${this._varSaveError
              ? html`<div class="modal__status modal__status--error">
                  ⚠ ${this._varSaveError}
                </div>`
              : null}
            ${this._varSaved
              ? html`<div class="modal__status modal__status--ok">
                  ✓ Saved — tracking this variant from the next check.
                </div>`
              : null}

            <div class="trackform__actions sel__actions">
              <button
                class="trackform__cancel"
                @click=${this._clearVariant}
                ?disabled=${this._varSaving || !this._varSupported}
                title="Revert to the page's default price"
              >
                Track default again
              </button>
              <button
                class="add-button"
                @click=${this._saveVariant}
                ?disabled=${this._varSaving ||
                !this._varSupported ||
                incomplete ||
                !matched}
              >
                ${this._varSaving ? "Saving…" : "Track this variant"}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /** Format a variant combo's price with its currency for the preview. */
  private _formatVariantPrice(combo: VariantCombo): string {
    const cur = combo.currency || "";
    try {
      if (cur) {
        return new Intl.NumberFormat(undefined, {
          style: "currency",
          currency: cur,
        }).format(combo.price);
      }
    } catch {
      // Unknown currency code — fall through to a plain number.
    }
    return cur ? `${combo.price} ${cur}` : `${combo.price}`;
  }

  /**
   * The advanced price-selector editor overlay. Lets an advanced user
   * point at a price element via F12 (or the picker bookmarklet), paste
   * a CSS selector, Test it against the live page server-side, and save
   * it onto the listing as a custom parser. Rendered at the panel root;
   * nothing renders when closed.
   */
  private _renderSelectorModal() {
    if (!this._selectorOpen || !this._selListing) return null;
    const listing = this._selListing;
    const product = this._selProduct;
    const url = listing.url ?? "";
    const test = this._selTestResult;
    return html`
      <div
        class="modal-backdrop"
        @click=${this._onSelectorBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-label="Advanced price selector"
      >
        <div class="modal">
          <div class="modal__head">
            <h2>Custom price selector</h2>
            <button
              class="modal__close"
              @click=${this._closeSelectorEditor}
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div class="trackform">
            <p class="sel__intro">
              For ${listing.retailer || "this listing"}${product
                ? html` on <strong>${product.title}</strong>`
                : null}. Use this when the automatic price reader can't
              find the price. Open the page in your browser, press
              <kbd>F12</kbd>, right-click the price →
              <em>Copy → Copy selector</em>, and paste it below — or use
              the point-and-click picker further down.
            </p>
            ${url
              ? html`<div class="sel__url" title=${url}>${url}</div>`
              : html`<div class="modal__status modal__status--error">
                  ⚠ This listing has no URL, so Test won't work.
                </div>`}

            <label class="trackform__field">
              <span>Price selector <em>(CSS)</em></span>
              <input
                type="text"
                .value=${this._selPriceSelector}
                @input=${this._onSelPriceInput}
                placeholder=".product-price .amount  (or  span#price@content)"
                spellcheck="false"
                autocapitalize="off"
              />
            </label>
            <label class="trackform__field">
              <span>Title selector <em>(optional — defaults to h1)</em></span>
              <input
                type="text"
                .value=${this._selTitleSelector}
                @input=${this._onSelTitleInput}
                placeholder="h1"
                spellcheck="false"
                autocapitalize="off"
              />
            </label>

            <div class="sel__test-row">
              <button
                class="sel__test-btn"
                @click=${this._runSelectorTest}
                ?disabled=${this._selTesting || !url}
              >
                ${this._selTesting ? "Testing…" : "Test on live page"}
              </button>
              <span class="sel__hint"
                >Append <code>@attr</code> to read an attribute, e.g.
                <code>meta[itemprop=price]@content</code>.</span
              >
            </div>

            ${this._selTestError
              ? html`<div class="modal__status modal__status--error">
                  ⚠ ${this._selTestError}
                </div>`
              : null}
            ${test ? this._renderSelectorTestResult(test) : null}

            ${this._renderBookmarklet()}

            <label class="trackform__field">
              <span>
                Request cookies <em>(optional — for bot-walled sites)</em>
                ${listing.hasCookies
                  ? html`<span class="sel__cookies-set"
                      >✓ cookies currently set</span
                    >`
                  : null}
              </span>
              <textarea
                rows="3"
                .value=${this._selCookies}
                @input=${this._onSelCookiesInput}
                placeholder=${listing.hasCookies
                  ? "Leave blank to keep current cookies, or paste new ones to replace"
                  : "session-id=123-456; ubid=ABC; i18n-prefs=GBP"}
                spellcheck="false"
                autocapitalize="off"
              ></textarea>
            </label>
            <p class="sel__hint">
              Paste the page's <code>Cookie</code> header (F12 → Network →
              any request → Request Headers → <em>Cookie</em>) to reach
              content behind Cloudflare / Amazon session walls. Stored
              separately from the selector — saving a selector won't erase
              cookies and vice-versa. Leave blank to keep existing cookies;
              cookies expire, so re-paste when a site starts failing.
            </p>

            ${this._selSaveError
              ? html`<div class="modal__status modal__status--error">
                  ⚠ ${this._selSaveError}
                </div>`
              : null}
            ${this._selSaved
              ? html`<div class="modal__status modal__status--ok">
                  ✓ Saved — the listing will use it on the next check.
                </div>`
              : null}

            <div class="trackform__actions sel__actions">
              <button
                class="trackform__cancel"
                @click=${this._clearSelector}
                ?disabled=${this._selSaving}
                title="Revert to automatic extraction (clears selector + cookies)"
              >
                Reset to automatic
              </button>
              <button
                class="add-button"
                @click=${this._saveSelector}
                ?disabled=${this._selSaving ||
                (!this._selPriceSelector.trim() && !this._selCookies.trim())}
              >
                ${this._selSaving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /** Render the result of a test_selector run: price preview + raw text. */
  private _renderSelectorTestResult(test: TestSelectorResponse) {
    const price = test.price;
    const title = test.title;
    return html`
      <div class="sel__result">
        <div class="sel__result-head">
          Tested${test.page_title
            ? html` — <span class="sel__page-title">${test.page_title}</span>`
            : null}
        </div>
        <div class="sel__result-row">
          <span class="sel__result-label">Price</span>
          ${price.found
            ? html`<span class="sel__result-ok">
                  ${price.value !== null && price.value !== undefined
                    ? html`<strong>${price.value}</strong>`
                    : html`<em>matched, but not a number</em>`}
                </span>
                <code class="sel__raw">${price.raw}</code>`
            : html`<span class="sel__result-bad"
                >No match${price.error ? html` — ${price.error}` : null}</span
              >`}
        </div>
        ${title
          ? html`<div class="sel__result-row">
              <span class="sel__result-label">Title</span>
              ${title.found
                ? html`<code class="sel__raw">${title.raw}</code>`
                : html`<span class="sel__result-bad">No match</span>`}
            </div>`
          : null}
        ${price.found && (price.value === null || price.value === undefined)
          ? html`<p class="sel__warn">
              The element matched but no number could be parsed from it. Try a
              more specific selector, or append <code>@content</code> /
              <code>@data-price</code> to read a price attribute.
            </p>`
          : null}
      </div>
    `;
  }

  /** Render the point-and-click picker bookmarklet (drag link + copy code). */
  private _renderBookmarklet() {
    const href = this._bookmarkletHref();
    return html`
      <details
        class="sel__bm"
        ?open=${this._selBookmarkletOpen}
        @toggle=${(e: Event) =>
          (this._selBookmarkletOpen = (e.target as HTMLDetailsElement).open)}
      >
        <summary>Point-and-click picker (bookmarklet)</summary>
        <div class="sel__bm-body">
          <p>
            Drag this button to your bookmarks bar. Then, on the retailer's
            product page, click the bookmark and click the price — its CSS
            selector is copied to your clipboard. Paste it above.
            <kbd>Esc</kbd> cancels.
          </p>
          <p>
            <a class="sel__bm-link" href=${href} @click=${(e: Event) =>
              e.preventDefault()}
              >📍 Pick price selector</a
            >
          </p>
          <p class="sel__hint">
            Can't drag it? Copy the code and make a bookmark whose URL is this:
          </p>
          <div class="sel__bm-copy">
            <button class="sel__test-btn" @click=${this._copyBookmarklet}>
              Copy bookmarklet code
            </button>
          </div>
          <textarea
            class="sel__bm-code"
            readonly
            rows="3"
            @click=${(e: Event) => (e.target as HTMLTextAreaElement).select()}
          >${href}</textarea>
        </div>
      </details>
    `;
  }

  static styles = css`
    :host {
      display: block;
      width: 100%;
      min-height: 100vh;
      background: var(--primary-background-color, #fafafa);
      color: var(--primary-text-color, #212121);
      box-sizing: border-box;
    }

    .panel {
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
      box-sizing: border-box;
    }

    .panel-header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }
    .panel-header h1 {
      margin: 0;
      font-size: 1.75rem;
      font-weight: 500;
    }
    .panel-header__counts {
      color: var(--secondary-text-color, #757575);
      font-size: 0.875rem;
      margin-top: 4px;
    }

    .panel-header__actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .ship-toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
    }
    .ship-toggle input {
      cursor: pointer;
      accent-color: var(--primary-color, #03a9f4);
      margin: 0;
    }

    .add-button {
      padding: 8px 16px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      border: none;
      border-radius: 999px;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: filter 120ms ease;
    }
    .add-button:hover {
      filter: brightness(1.1);
    }
    .add-button:disabled {
      opacity: 0.5;
      cursor: default;
      filter: none;
    }
    .add-button--secondary {
      background: transparent;
      color: var(--primary-color, #03a9f4);
      border: 1px solid var(--primary-color, #03a9f4);
    }

    /* --- Search & add modal --- */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 48px 16px;
      z-index: 1000;
      overflow-y: auto;
    }
    .modal {
      width: 100%;
      max-width: 560px;
      background: var(--card-background-color, #fff);
      border-radius: 16px;
      box-shadow: 0 12px 48px rgba(0, 0, 0, 0.3);
      display: flex;
      flex-direction: column;
      max-height: calc(100vh - 96px);
      overflow: hidden;
    }
    .modal__head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .modal__head h2 {
      margin: 0;
      font-size: 1.2rem;
      font-weight: 500;
    }
    .modal__close {
      background: none;
      border: none;
      font-size: 1.1rem;
      cursor: pointer;
      color: var(--secondary-text-color, #757575);
      padding: 4px 8px;
      border-radius: 8px;
      line-height: 1;
    }
    .modal__close:hover {
      background: var(--divider-color, #e0e0e0);
    }
    .modal__searchbar {
      display: flex;
      gap: 8px;
      padding: 16px 20px;
    }
    .modal__searchinput {
      flex: 1;
      box-sizing: border-box;
      padding: 10px 14px;
      font-size: 0.95rem;
      color: var(--primary-text-color, #212121);
      background: var(--primary-background-color, #fafafa);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      outline: none;
    }
    .modal__searchinput:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .modal__status {
      padding: 8px 20px 20px;
      color: var(--secondary-text-color, #757575);
      font-size: 0.9rem;
    }
    .modal__status--error {
      color: var(--error-color, #f44336);
    }
    .modal__status--ok {
      color: var(--success-color, #4caf50);
    }
    .modal__engine {
      padding: 0 20px 8px;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--secondary-text-color, #9e9e9e);
    }
    .results-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .results-bar .modal__engine {
      padding-bottom: 0;
    }
    .results-bar__toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 0 20px 8px;
      font-size: 0.78rem;
      color: var(--secondary-text-color, #757575);
      cursor: pointer;
      white-space: nowrap;
    }
    .results-bar__toggle input {
      cursor: pointer;
    }
    .results {
      list-style: none;
      margin: 0;
      padding: 0 12px 16px;
      overflow-y: auto;
    }
    .results__row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 8px;
      border-radius: 12px;
    }
    .results__row:hover {
      background: var(--primary-background-color, #f5f5f5);
    }
    .results__thumb {
      flex: 0 0 48px;
      width: 48px;
      height: 48px;
      border-radius: 8px;
      overflow: hidden;
      background: var(--primary-background-color, #f0f0f0);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .results__thumb img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .results__thumb-ph {
      font-size: 22px;
      opacity: 0.5;
    }
    .results__info {
      flex: 1;
      min-width: 0;
    }
    .results__title {
      font-size: 0.9rem;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .results__title--link {
      display: block;
      color: inherit;
      text-decoration: none;
      cursor: pointer;
    }
    .results__title--link:hover {
      color: var(--primary-color, #03a9f4);
      text-decoration: underline;
    }
    .results__ext {
      font-size: 0.72rem;
      opacity: 0.6;
      margin-left: 2px;
    }
    .results__meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 2px;
      flex-wrap: wrap;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
    }
    .results__price {
      font-weight: 600;
      color: var(--primary-text-color, #212121);
    }
    .results__ship {
      font-size: 0.68rem;
      padding: 1px 6px;
      border-radius: 999px;
    }
    .results__ship--yes {
      background: rgba(76, 175, 80, 0.16);
      color: var(--success-color, #4caf50);
    }
    .results__ship--no {
      background: rgba(158, 158, 158, 0.18);
      color: var(--secondary-text-color, #9e9e9e);
    }
    .results__kind {
      font-size: 0.68rem;
      padding: 1px 6px;
      border-radius: 999px;
    }
    .results__kind--info {
      background: rgba(255, 152, 0, 0.16);
      color: var(--warning-color, #ff9800);
    }
    /* De-emphasize rows that are clearly not a store. */
    .results__row--muted .results__thumb,
    .results__row--muted .results__title {
      opacity: 0.6;
    }
    .results__notes {
      font-size: 0.76rem;
      color: var(--secondary-text-color, #9e9e9e);
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .results__add {
      flex: 0 0 auto;
      padding: 6px 14px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      border: none;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 500;
      cursor: pointer;
    }
    .results__add:hover {
      filter: brightness(1.1);
    }
    .results__actions {
      flex: 0 0 auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
      align-items: stretch;
    }
    .results__exclude {
      padding: 5px 12px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      font-size: 0.74rem;
      cursor: pointer;
      white-space: nowrap;
    }
    .results__exclude:hover:not(:disabled) {
      color: var(--error-color, #f44336);
      border-color: var(--error-color, #f44336);
    }
    .results__exclude:disabled {
      opacity: 0.6;
      cursor: default;
    }

    /* --- Track-this confirm form --- */
    .trackform {
      padding: 16px 20px 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .trackform__hint {
      font-size: 0.85rem;
      color: var(--secondary-text-color, #757575);
    }
    .trackform__field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
    }
    .trackform__field em {
      font-style: normal;
      opacity: 0.7;
    }
    .trackform__field input,
    .trackform__field select,
    .trackform__field textarea {
      box-sizing: border-box;
      width: 100%;
      padding: 9px 12px;
      font-size: 0.9rem;
      font-family: inherit;
      color: var(--primary-text-color, #212121);
      background: var(--primary-background-color, #fafafa);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 10px;
      outline: none;
    }
    .trackform__field input:focus,
    .trackform__field select:focus,
    .trackform__field textarea:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .provider__textarea {
      resize: vertical;
      min-height: 56px;
    }
    .provider__advtoggle {
      align-self: flex-start;
      background: none;
      border: none;
      padding: 2px 0;
      font-size: 0.82rem;
      font-weight: 500;
      color: var(--primary-color, #03a9f4);
      cursor: pointer;
    }
    .provider__check {
      align-self: flex-start;
    }
    .trackform__actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 4px;
    }
    .trackform__cancel {
      padding: 8px 16px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      font-size: 0.875rem;
      cursor: pointer;
    }
    .trackform__cancel:hover {
      background: var(--primary-background-color, #f5f5f5);
    }

    /* --- Advanced price-selector editor --- */
    .sel__intro {
      margin: 0 0 4px;
      font-size: 0.85rem;
      line-height: 1.45;
      color: var(--secondary-text-color, #757575);
    }
    .sel__intro kbd,
    .sel__bm-body kbd {
      font-family: monospace;
      font-size: 0.78rem;
      padding: 1px 5px;
      border: 1px solid var(--divider-color, #d0d0d0);
      border-radius: 4px;
      background: var(--primary-background-color, #f5f5f5);
    }
    .sel__url {
      font-family: monospace;
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      padding: 4px 8px;
      background: var(--primary-background-color, #f5f5f5);
      border-radius: 6px;
    }
    .sel__test-row {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .sel__test-btn {
      padding: 7px 14px;
      background: var(--primary-color, #1976d2);
      color: #fff;
      border: none;
      border-radius: 999px;
      font-size: 0.85rem;
      cursor: pointer;
    }
    .sel__test-btn:disabled {
      opacity: 0.5;
      cursor: default;
    }
    .sel__hint {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #9e9e9e);
    }
    .sel__cookies-set {
      font-size: 0.72rem;
      font-style: normal;
      font-weight: 600;
      color: var(--success-color, #4caf50);
      margin-left: 0.4rem;
    }
    .sel__hint code,
    .sel__result code,
    .sel__warn code {
      font-family: monospace;
      font-size: 0.78rem;
      background: var(--primary-background-color, #f0f0f0);
      padding: 0 3px;
      border-radius: 3px;
    }
    .sel__result {
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .sel__result-head {
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--secondary-text-color, #9e9e9e);
    }
    .sel__page-title {
      text-transform: none;
      letter-spacing: 0;
    }
    .sel__result-row {
      display: flex;
      align-items: baseline;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 0.85rem;
    }
    .sel__result-label {
      flex: 0 0 44px;
      color: var(--secondary-text-color, #757575);
    }
    .sel__result-ok strong {
      font-size: 1.05rem;
      color: var(--success-color, #2e7d32);
    }
    .sel__result-bad {
      color: var(--error-color, #c62828);
    }
    .sel__raw {
      font-family: monospace;
      font-size: 0.78rem;
      color: var(--primary-text-color, #212121);
      word-break: break-all;
    }
    .sel__warn {
      margin: 0;
      font-size: 0.78rem;
      color: var(--secondary-text-color, #757575);
      line-height: 1.4;
    }
    .sel__bm {
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      padding: 0 12px;
    }
    .sel__bm summary {
      cursor: pointer;
      padding: 10px 0;
      font-size: 0.85rem;
      font-weight: 600;
    }
    .sel__bm-body {
      padding-bottom: 12px;
      font-size: 0.82rem;
      line-height: 1.45;
      color: var(--secondary-text-color, #757575);
    }
    .sel__bm-body p {
      margin: 0 0 8px;
    }
    .sel__bm-link {
      display: inline-block;
      padding: 6px 12px;
      background: var(--primary-background-color, #f0f0f0);
      border: 1px dashed var(--primary-color, #1976d2);
      border-radius: 8px;
      color: var(--primary-color, #1976d2);
      text-decoration: none;
      font-weight: 600;
      cursor: grab;
    }
    .sel__bm-code {
      width: 100%;
      box-sizing: border-box;
      font-family: monospace;
      font-size: 0.7rem;
      resize: vertical;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      padding: 6px;
    }
    .sel__actions {
      justify-content: space-between;
    }

    /* --- Variant picker --- */
    .var__groups {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .var__select {
      width: 100%;
      box-sizing: border-box;
      padding: 8px 10px;
      font: inherit;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #c0c0c0);
      border-radius: 8px;
    }
    .var__preview {
      margin-top: 14px;
      padding: 12px 14px;
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 10px;
      display: flex;
      align-items: baseline;
      gap: 10px;
      min-height: 24px;
    }
    .var__price {
      font-size: 1.4rem;
      font-weight: 600;
      line-height: 1.1;
    }
    .var__oos {
      font-size: 0.8rem;
      color: var(--error-color, #c62828);
    }
    .var__hint {
      color: var(--secondary-text-color, #757575);
      font-size: 0.9rem;
    }
    .var__hint--warn {
      color: var(--warning-color, #f57c00);
    }

    /* --- Alert ("notify me") dialog --- */
    .alert__section-label {
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--secondary-text-color, #757575);
      margin: 14px 0 6px;
    }
    .alert__triggers {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .alert__trigger {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 10px;
      cursor: pointer;
    }
    .alert__trigger--on {
      border-color: var(--primary-color, #03a9f4);
      background: rgba(3, 169, 244, 0.07);
    }
    .alert__trigger--disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .alert__trigger input {
      margin-top: 3px;
    }
    .alert__trigger-body {
      display: flex;
      flex-direction: column;
      gap: 1px;
    }
    .alert__trigger-label {
      font-size: 0.92rem;
      font-weight: 500;
    }
    .alert__trigger-hint {
      font-size: 0.78rem;
      color: var(--secondary-text-color, #757575);
    }
    .alert__targets {
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-height: 180px;
      overflow-y: auto;
    }
    .alert__target {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 2px;
      font-size: 0.9rem;
      cursor: pointer;
    }

    /* --- Summary stat bar --- */
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .stat {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 12px 16px;
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 12px;
      border-left-width: 4px;
    }
    .stat__value {
      font-size: 1.5rem;
      font-weight: 600;
      line-height: 1.1;
    }
    .stat__label {
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .stat--total {
      border-left-color: var(--primary-color, #03a9f4);
    }
    .stat--stock {
      border-left-color: var(--success-color, #4caf50);
    }
    .stat--target {
      border-left-color: var(--warning-color, #ff9800);
    }
    .stat--disc {
      border-left-color: var(--secondary-text-color, #9e9e9e);
    }

    /* --- Toolbar --- */
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .toolbar__search {
      flex: 1 1 240px;
      min-width: 180px;
    }
    .toolbar__search input {
      width: 100%;
      box-sizing: border-box;
      padding: 8px 12px;
      font-size: 0.875rem;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 999px;
      outline: none;
    }
    .toolbar__search input:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .toolbar__controls {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }
    .sort-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      color: var(--secondary-text-color, #757575);
      white-space: nowrap;
    }
    .sort-label select {
      padding: 6px 10px;
      font-size: 0.8rem;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 8px;
      cursor: pointer;
      outline: none;
    }
    .sort-label select:focus {
      border-color: var(--primary-color, #03a9f4);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }

    .empty,
    .error,
    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      padding: 48px 16px;
      text-align: center;
      color: var(--secondary-text-color, #757575);
    }
    .empty__icon {
      font-size: 64px;
    }
    .error__icon {
      font-size: 48px;
      color: var(--error-color, #f44336);
    }
    .empty h2 {
      margin: 0;
      font-size: 1.25rem;
      color: var(--primary-text-color, #212121);
    }
    .empty p,
    .error p,
    .loading p {
      margin: 0;
    }
  `;
}

// Guarded registration instead of @customElement — see card.ts for the
// rationale. A re-import of this bundle must not throw on a duplicate
// customElements.define, or the whole panel module aborts and renders blank.
if (!customElements.get("price-watch-panel")) {
  customElements.define("price-watch-panel", PriceWatchPanel);
}

declare global {
  interface HTMLElementTagNameMap {
    "price-watch-panel": PriceWatchPanel;
  }
}
