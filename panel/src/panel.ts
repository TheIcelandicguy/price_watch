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

import { LitElement, html, css, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";

import "./card.js";
import type {
  HomeAssistant,
  HassState,
  Listing,
  TrackedProduct,
} from "./types.js";
import { buildProducts, type EntityRegistryIndex } from "./utils.js";

// Shape of the entity_registry/list response.
interface RegistryEntry {
  entity_id: string;
  unique_id: string;
  platform: string;
  config_entry_id: string | null;
}

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
  // auth field present but we don't use it
}

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

@customElement("price-watch-panel")
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

  // localStorage key for the "hide non-shipping alternatives" toggle.
  private static readonly HIDE_NONSHIP_KEY = "price-watch:hide-non-shipping";

  constructor() {
    super();
    // Restore the toggle preference. Wrapped in try/catch because
    // localStorage can throw in locked-down / private-mode contexts.
    try {
      this._hideNonShipping =
        localStorage.getItem(PriceWatchPanel.HIDE_NONSHIP_KEY) === "1";
    } catch {
      // Ignore — default (show everything) is a safe fallback.
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

  private _handleAddProduct = (): void => {
    const url = "/config/integrations/dashboard/add?domain=price_watch";
    window.history.pushState(null, "", url);
    window.dispatchEvent(new CustomEvent("location-changed"));
  };

  private _renderHeader() {
    const count = this._products.length;
    const discontinuedCount = this._products.filter((p) => p.discontinued).length;
    const activeCount = count - discontinuedCount;

    return html`
      <header class="panel-header">
        <div class="panel-header__title">
          <h1>Price Watch</h1>
          <div class="panel-header__counts">
            ${activeCount} active${discontinuedCount > 0
              ? html` · ${discontinuedCount} discontinued`
              : nothing}
          </div>
        </div>
        <div class="panel-header__actions">
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
          <button class="add-button" @click=${this._handleAddProduct}>
            + Add product
          </button>
        </div>
      </header>
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
    return html`
      <div class="grid">
        ${this._products.map(
          (p) => html`
            <price-watch-card
              .product=${p}
              .onOpen=${this._handleOpen}
              .onRefreshAlternatives=${this._handleRefreshAlternatives}
              .refreshingAlternatives=${this._refreshingEntries.has(p.entryId)}
              .hideNonShipping=${this._hideNonShipping}
              .onRemoveListing=${this._handleRemoveListing}
            ></price-watch-card>
          `
        )}
      </div>
    `;
  }

  render() {
    return html`
      <div class="panel">
        ${this._renderHeader()}
        ${this._registryError
          ? this._renderError()
          : !this._connected || !this._registry
          ? this._renderLoading()
          : this._products.length === 0
          ? this._renderEmptyState()
          : this._renderGrid()}
      </div>
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

declare global {
  interface HTMLElementTagNameMap {
    "price-watch-panel": PriceWatchPanel;
  }
}
