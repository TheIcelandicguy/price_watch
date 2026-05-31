/**
 * <price-watch-card>
 *
 * A single product card. Stateless (re-renders entirely from its
 * `product` property), purely presentational. The parent panel is
 * responsible for deciding which products to show and in what order.
 */

import { LitElement, html, css, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import type { Alternative, Listing, TrackedProduct } from "./types.js";
import { filterOutliers, formatPrice, formatRelative, sparklinePath } from "./utils.js";

@customElement("price-watch-card")
export class PriceWatchCard extends LitElement {
  @property({ attribute: false }) product!: TrackedProduct;
  // Optional callback for clicks on the card body. Used by the panel
  // to open the source URL in a new tab. Kept as a property rather
  // than a custom event so the parent doesn't have to wire up
  // listeners per-card.
  @property({ attribute: false }) onOpen?: (product: TrackedProduct) => void;
  // Optional callback fired when the user clicks the "Refresh
  // alternatives" button. The panel owner is responsible for
  // calling the price_watch.find_alternatives service. The card
  // doesn't track its own loading state — when the service call
  // completes, the sensor's alternatives_fetched_at updates and
  // the parent rebuilds, which feeds a fresh product object back
  // down to us. While in-flight, the parent should set the
  // `refreshingAlternatives` property to show a spinner.
  @property({ attribute: false })
  onRefreshAlternatives?: (product: TrackedProduct) => void;
  @property({ type: Boolean, attribute: false })
  refreshingAlternatives = false;
  // When true, alternatives the backend marked as NOT shipping to the
  // user's region (shipsToUserRegion === false) are filtered out of the
  // list. Unknown shipping (null) is always kept — we only hide the ones
  // we're confident won't ship. Driven by a panel-wide toggle.
  @property({ type: Boolean, attribute: false })
  hideNonShipping = false;
  // Optional callback fired when the user clicks "Remove" on a
  // secondary listing's row. The panel owner is responsible for the
  // confirmation dialog (handled in the card via window.confirm) and
  // for calling the price_watch.remove_listing service. After the
  // service returns, the sensor entities for that listing are
  // unregistered server-side, the registry-updated event fires, the
  // panel re-fetches the registry, and the card re-renders without
  // the removed row.
  @property({ attribute: false })
  onRemoveListing?: (product: TrackedProduct, listing: Listing) => void;
  // Optional callback fired when the user clicks "Add as listing" on an
  // alternative row. The panel owner calls price_watch.add_listing with
  // the alternative's URL (plus retailer/currency hints). After the
  // service returns, the entry reloads, the registry-updated event
  // fires, the panel re-fetches, and the new listing appears in the
  // Listings section. Alternatives the user has already added as a
  // listing are detected by URL (see `listingUrls`) and show a checked,
  // disabled state instead of the add button.
  @property({ attribute: false })
  onAddListing?: (product: TrackedProduct, alt: Alternative) => void;
  // Optional callback fired when the user clicks the ✎ (edit) button on a
  // listing row. The panel owner opens the advanced price-selector editor
  // for that listing — capture a CSS selector via F12 / the bookmarklet,
  // Test it server-side, then save via price_watch.edit_listing. Allowed on
  // every listing including the primary (unlike remove, which is
  // secondary-only). After the service reloads the entry the new parser
  // takes effect on the next poll.
  @property({ attribute: false })
  onEditListing?: (product: TrackedProduct, listing: Listing) => void;
  // Optional callback fired when the user clicks the per-card "Refresh
  // now" button. The panel owner calls price_watch.refresh_now. While
  // in flight the parent sets `refreshingNow` so we spin the icon.
  @property({ attribute: false })
  onRefreshNow?: (product: TrackedProduct) => void;
  @property({ type: Boolean, attribute: false })
  refreshingNow = false;
  // Optional callback fired when the user commits an inline target-price
  // edit. A null target clears it. The panel owner calls
  // price_watch.set_target.
  @property({ attribute: false })
  onSetTarget?: (product: TrackedProduct, target: number | null) => void;
  // Optional callback fired when the user toggles the pause control. The
  // panel owner calls price_watch.set_paused.
  @property({ attribute: false })
  onSetPaused?: (product: TrackedProduct, paused: boolean) => void;

  /**
   * The currency we show next to the headline price. Prefer the local
   * currency when available — it's what the user actually thinks in.
   * Falls back to the source currency otherwise.
   */
  private get headlinePrice(): { value: number | null; currency: string | null } {
    const { product } = this;
    if (product.priceLocal != null && product.localCurrency) {
      return { value: product.priceLocal, currency: product.localCurrency };
    }
    if (product.discontinued && product.lastKnownPrice != null) {
      return {
        value: product.lastKnownPrice,
        currency: product.lastKnownCurrency ?? product.currency,
      };
    }
    return { value: product.price, currency: product.currency || null };
  }

  private get sourcePriceLine(): string | typeof nothing {
    const { product } = this;
    // Only show a second line when the headline is the local-currency
    // value AND the source currency is different. Avoids redundancy.
    if (product.priceLocal == null || !product.localCurrency) return nothing;
    if (product.currency === product.localCurrency) return nothing;
    return formatPrice(product.price, product.currency);
  }

  /**
   * Delta between the current price and the most recent prior
   * observation at a DIFFERENT value. Walks back through history
   * skipping same-value observations — three polls at 2,230 NOK
   * before the price moves to 2,200 means we still want to show
   * "↓ 30" not "↓ 0".
   *
   * Computed in SOURCE currency (product.price + history[].price
   * are always source-currency; we don't track a priceLocal
   * history). Returned in absolute value with a direction tag so
   * the renderer can pick the colour + arrow.
   *
   * Returns null when there's no movement to indicate — either
   * because history has only one distinct value, or because no
   * history exists yet.
   */
  private get priceDelta(): { amount: number; direction: "up" | "down" } | null {
    const { product } = this;
    if (product.price == null) return null;
    const current = product.price;
    // Walk backward, skipping same-value observations. The first
    // different value is the previous distinct price; the delta is
    // current - that.
    for (let i = product.history.length - 1; i >= 0; i--) {
      const past = product.history[i].price;
      if (past !== current) {
        return {
          amount: Math.abs(current - past),
          direction: current > past ? "up" : "down",
        };
      }
    }
    return null;
  }

  /**
   * Render the price delta as a small inline pill. Returns
   * `nothing` when there's nothing meaningful to show, so callers
   * can splat the result into a template unconditionally.
   *
   * Arrow + amount only (no currency code) — placed next to the
   * source-currency price so currency context is implicit.
   */
  private renderDelta() {
    const delta = this.priceDelta;
    if (delta == null) return nothing;
    const arrow = delta.direction === "up" ? "↑" : "↓";
    const cls =
      delta.direction === "up"
        ? "delta delta--up"
        : "delta delta--down";
    // Pass null currency so formatPrice gives us "20.00" not "USD 20.00"
    return html`<span class=${cls}>${arrow} ${formatPrice(delta.amount, null)}</span>`;
  }

  private renderImage() {
    const { product } = this;
    // Prefer the HA image proxy URL (same-origin, served via the
    // price_watch image entity). It bypasses retailer hotlink
    // protection and CDN bot-checks because we fetched the bytes
    // server-side with curl_cffi when the coordinator last ran.
    //
    // If the photo entity exists but is unavailable (imageBroken),
    // don't fall back to the raw imageUrl — that's almost certainly
    // broken for the same reason the bytes fetch failed (404, etc).
    // Showing a placeholder is cleaner than a broken-image icon.
    //
    // The raw imageUrl fallback only kicks in for older product
    // entries that pre-date the image entity (rare; mostly belt-and-
    // suspenders).
    const src = product.imageProxyUrl ?? (product.imageBroken ? null : product.imageUrl);
    if (!src) {
      return html`<div class="image image--placeholder" role="img" aria-label="No image">
        <ha-icon icon="mdi:tag-search"></ha-icon>
      </div>`;
    }
    return html`<img
      class="image"
      src=${src}
      alt=${product.title}
      loading="lazy"
    />`;
  }

  private renderSparkline() {
    const { product } = this;
    if (product.history.length < 2) return nothing;
    const width = 280;
    const height = 48;
    const d = sparklinePath(product.history, width, height);
    if (!d) return nothing;
    // The viewBox lets the SVG scale into the card's actual width
    // (~card width minus padding). Stroke kept thin and using the
    // primary color so it integrates with whatever theme HA's
    // applying.
    return html`<svg
      class="sparkline"
      viewBox="0 0 ${width} ${height}"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d=${d} fill="none" stroke="currentColor" stroke-width="1.5" />
    </svg>`;
  }

  private renderStatusChips() {
    const { product } = this;
    const chips: ReturnType<typeof html>[] = [];

    if (product.paused) {
      chips.push(html`<span class="chip chip--paused" title="Polling paused">
        Paused
      </span>`);
    }

    if (product.discontinued) {
      chips.push(html`<span class="chip chip--warn" title=${product.discontinuedReason ?? ""}>
        Discontinued
      </span>`);
    } else if (product.inStock === false) {
      chips.push(html`<span class="chip chip--warn">Out of stock</span>`);
    } else if (product.inStock === true) {
      chips.push(html`<span class="chip chip--ok">In stock</span>`);
    }

    if (product.stockCount != null && product.stockCount > 0) {
      chips.push(html`<span class="chip">${product.stockCount} units</span>`);
    }

    if (product.retailer) {
      chips.push(html`<span class="chip chip--retailer">${product.retailer}</span>`);
    }

    return chips.length ? html`<div class="chips">${chips}</div>` : nothing;
  }

  /**
   * Lowest and highest values to display in the stat row.
   *
   * The lowest/highest *sensors* on the coordinator track the raw
   * min/max across all history including outliers. When a custom
   * parser has produced bad fetches (matching the wrong field, etc.)
   * the sensor values become useless — Lowest $1.30 / Highest $48,500
   * for a $350 product is technically correct but not helpful.
   *
   * If we have enough history (≥4 points), compute min/max from the
   * outlier-filtered series instead. The sensor still reports the raw
   * values for anyone consuming them programmatically; this is purely
   * a display choice.
   *
   * Returns `null` for either value if no estimate is available.
   */
  private get cleanedExtremes(): { low: number | null; high: number | null } {
    const { product } = this;
    if (product.history.length >= 4) {
      const cleaned = filterOutliers(product.history);
      if (cleaned.length >= 2) {
        const prices = cleaned.map((p) => p.price);
        return { low: Math.min(...prices), high: Math.max(...prices) };
      }
    }
    return { low: product.lowest, high: product.highest };
  }

  /**
   * Render the alternatives section: header row with count + refresh
   * button + last-fetched timestamp, then a list of alt rows.
   *
   * Hidden entirely when there are no alternatives AND no error AND
   * no fetched_at — the user hasn't engaged the feature yet, so
   * showing nothing keeps the card uncluttered. As soon as they
   * click refresh once (even if it fails), the section becomes
   * persistent: future cards always show the header so the refresh
   * button is reachable.
   */
  private renderAlternatives() {
    const { product } = this;
    const hasError = product.alternativesError != null;
    const everFetched = product.alternativesFetchedAt != null;

    // Apply the "hide non-shipping" filter. Only alternatives the
    // backend is confident won't ship (shipsToUserRegion === false) get
    // dropped; unknown shipping (null) is always kept. hiddenCount drives
    // a small note so the user knows the list was trimmed (and isn't
    // confused by a shorter count than they expected).
    const visibleAlts = this.hideNonShipping
      ? product.alternatives.filter((a) => a.shipsToUserRegion !== false)
      : product.alternatives;
    const hiddenCount = product.alternatives.length - visibleAlts.length;
    const hasAny = visibleAlts.length > 0;

    // We always render this section, including the un-engaged state
    // (no fetch yet) — without that the refresh button is hidden by
    // the same condition that needs the discovery affordance. The
    // empty case is intentionally minimal: just the header row with
    // a refresh icon, then "Click refresh to find alternatives."

    return html`
      <section class="alts">
        <div class="alts__header">
          <span class="alts__title">
            ${hasAny
              ? html`Alternatives <span class="alts__count">${visibleAlts.length}</span>`
              : html`Alternatives`}
          </span>
          <span class="alts__meta">
            ${everFetched ? formatRelative(product.alternativesFetchedAt) : ""}
          </span>
          <button
            class="alts__refresh"
            type="button"
            ?disabled=${this.refreshingAlternatives}
            @click=${this.handleRefresh}
            aria-label="Refresh alternatives"
            title="Refresh alternatives"
          >
            <ha-icon
              icon=${this.refreshingAlternatives ? "mdi:loading" : "mdi:refresh"}
              class=${this.refreshingAlternatives ? "alts__refresh-spin" : ""}
            ></ha-icon>
          </button>
        </div>
        ${hasError
          ? html`<p class="alts__error">${product.alternativesError}</p>`
          : nothing}
        ${hasAny
          ? html`<ul class="alts__list">
              ${visibleAlts.map((alt) => this.renderAlternative(alt))}
            </ul>`
          : !hasError && !this.refreshingAlternatives
          ? html`<p class="alts__empty">
              ${everFetched
                ? hiddenCount > 0
                  ? "All alternatives were hidden (don't ship to your region)."
                  : "No alternatives found."
                : "Click refresh to search for alternatives."}
            </p>`
          : nothing}
        ${hasAny && hiddenCount > 0
          ? html`<p class="alts__hidden-note">
              ${hiddenCount} hidden (don't ship to your region)
            </p>`
          : nothing}
      </section>
    `;
  }

  /**
   * Render a single alternative row. Click anywhere on the row
   * opens the URL in a new tab.
   *
   * Delta colour: if the alternative's price is lower than the
   * current tracked price (in either source or local currency,
   * depending on which we have), highlight green. Higher → red-ish.
   * Same currency only — cross-currency comparison without FX is
   * misleading.
   */
  /**
   * Set of URLs already tracked as listings on this product, used to
   * mark alternatives the user has already added so we show a checked,
   * disabled state instead of an active "Add" button. Trailing slashes
   * are normalised away so `…/p/123` and `…/p/123/` match.
   */
  private get listingUrls(): Set<string> {
    const norm = (u: string | null | undefined) =>
      (u ?? "").trim().replace(/\/+$/, "").toLowerCase();
    const urls = new Set<string>();
    for (const l of this.product.listings) {
      const n = norm(l.url);
      if (n) urls.add(n);
    }
    return urls;
  }

  private renderAlternative(alt: Alternative) {
    const { product } = this;
    let delta: number | null = null;
    let priceClass = "alts__price";
    if (alt.price != null && product.price != null && alt.currency === product.currency) {
      delta = alt.price - product.price;
      if (delta < 0) priceClass = "alts__price alts__price--cheaper";
      else if (delta > 0) priceClass = "alts__price alts__price--pricier";
    }
    const altUrlNorm = (alt.url ?? "").trim().replace(/\/+$/, "").toLowerCase();
    const alreadyListed = altUrlNorm !== "" && this.listingUrls.has(altUrlNorm);
    return html`
      <li class="alts__row">
        <a
          class="alts__link"
          href=${alt.url}
          target="_blank"
          rel="noopener noreferrer"
          @click=${(e: Event) => e.stopPropagation()}
          title=${alt.notes || alt.title}
        >
          <div class="alts__info">
            <span class="alts__row-title">${alt.title}</span>
            <span class="alts__row-meta">
              ${alt.retailer ? html`<span>${alt.retailer}</span>` : nothing}
              ${alt.confidence > 0
                ? html`<span class="alts__confidence" title="Match confidence">
                    ${Math.round(alt.confidence * 100)}%
                  </span>`
                : nothing}
              ${alt.shipsToUserRegion === true
                ? html`<span class="alts__ships alts__ships--yes" title="Likely ships to your region">
                    ✓ ships
                  </span>`
                : alt.shipsToUserRegion === false
                ? html`<span class="alts__ships alts__ships--no" title="Likely does not ship to your region">
                    ✗ no ship
                  </span>`
                : nothing}
            </span>
          </div>
          <div class=${priceClass}>
            ${alt.price != null
              ? formatPrice(alt.price, alt.currency)
              : html`<span class="alts__price-unknown">—</span>`}
          </div>
        </a>
        ${this.onAddListing
          ? alreadyListed
            ? html`<span
                class="alts__add alts__add--done"
                title="Already tracked as a listing"
                aria-label="Already a listing"
                >✓</span
              >`
            : html`<button
                class="alts__add"
                type="button"
                @click=${(e: Event) => this.handleAddListing(e, alt)}
                aria-label=${`Add ${alt.retailer || "this alternative"} as a listing`}
                title="Track this as a listing"
              >
                +
              </button>`
          : nothing}
      </li>
    `;
  }

  /**
   * Click handler for an alternative row's "+" button. Stops
   * propagation (so the card's open-source handler doesn't fire),
   * confirms intent, and delegates to onAddListing. Mirrors
   * handleRemoveListing's window.confirm approach for consistency.
   */
  private handleAddListing(event: Event, alt: Alternative): void {
    event.stopPropagation();
    event.preventDefault();
    const label = alt.retailer
      ? `Track the ${alt.retailer} listing for ${this.product.title}?`
      : `Track this alternative as a listing on ${this.product.title}?`;
    if (!window.confirm(label)) return;
    this.onAddListing?.(this.product, alt);
  }

  private handleRefresh = (event: Event): void => {
    // Stop the click from bubbling to the card's open-source handler.
    event.stopPropagation();
    if (this.refreshingAlternatives) return;
    this.onRefreshAlternatives?.(this.product);
  };

  private renderStatRow() {
    const { product } = this;
    const cells: ReturnType<typeof html>[] = [];

    // Lowest and Highest cells were removed in favor of the inline
    // price delta indicator next to the headline price. The
    // `cleanedExtremes` getter is kept (used by sparkline scaling).
    if (product.targetPrice != null) {
      const diffClass =
        product.targetDiff != null && product.targetDiff <= 0
          ? "stat__value stat__value--good"
          : "stat__value";
      cells.push(html`<div class="stat">
        <span class="stat__label">Target</span>
        <span class=${diffClass}>${formatPrice(product.targetPrice, product.currency)}</span>
      </div>`);
    }

    return cells.length ? html`<div class="stats">${cells}</div>` : nothing;
  }

  /**
   * Render the Listings section: header + a row per listing.
   *
   * Listings = URLs the user explicitly tracks (vs Alternatives,
   * which are AI-discovered). Each row shows retailer, current
   * price, a mini per-listing sparkline, an in-stock indicator,
   * and a last-check timestamp. The primary listing gets a small
   * "primary" badge and no remove button (you can't remove a
   * product's last listing). Secondaries get a × button that
   * fires onRemoveListing after a window.confirm.
   *
   * Always rendered when the product has at least one listing
   * (which is always, since a product without listings would have
   * been filtered out earlier). Single-listing products still show
   * the section — keeps the UI consistent and surfaces that more
   * listings can be added via the add_listing service.
   */
  private renderListings() {
    const { product } = this;
    if (product.listings.length === 0) return nothing;

    // Apply the "hide non-shipping" filter, same as alternatives. The
    // primary listing is ALWAYS kept regardless — the card's headline
    // price/image are built around it, so hiding it would leave a
    // confusing gap (and you can't remove a product's last listing
    // anyway). Only secondary listings the heuristic is confident won't
    // ship (shipsToUserRegion === false) get dropped.
    const visible = this.hideNonShipping
      ? product.listings.filter(
          (l) => l.isPrimary || l.shipsToUserRegion !== false
        )
      : product.listings;
    const hiddenCount = product.listings.length - visible.length;

    return html`
      <section class="listings">
        <div class="listings__header">
          <span class="listings__title">
            Listings <span class="listings__count">${visible.length}</span>
          </span>
        </div>
        <ul class="listings__list">
          ${visible.map((l) => this.renderListingRow(l))}
        </ul>
        ${hiddenCount > 0
          ? html`<p class="alts__hidden-note">
              ${hiddenCount} hidden (don't ship to your region)
            </p>`
          : nothing}
      </section>
    `;
  }

  /**
   * Render one Listing row.
   *
   * The whole row except the remove button is a click-through to
   * the listing URL (when present) — same pattern as alternatives.
   * The × button sits outside the anchor so its click doesn't
   * navigate, and stops propagation to also prevent the card's
   * own open-source handler from firing.
   *
   * Mini-sparkline: 80×24px, rendered only when history has ≥2
   * points (otherwise the SVG would be empty). The same outlier
   * filter (MAD) sparklinePath uses applies, so a single bad
   * fetch doesn't ruin the row.
   */
  private renderListingRow(listing: Listing) {
    const sparkW = 80;
    const sparkH = 24;
    const sparkD = sparklinePath(listing.history, sparkW, sparkH, 2);

    const stockChip =
      listing.discontinued
        ? html`<span class="listings__chip listings__chip--warn">disc.</span>`
        : listing.inStock === false
        ? html`<span class="listings__chip listings__chip--warn">out</span>`
        : listing.inStock === true
        ? html`<span class="listings__chip listings__chip--ok">in stock</span>`
        : nothing;

    // Per-listing thumbnail. Prefer the proxied image bytes; show a
    // neutral placeholder when the listing has no photo or the entity is
    // unavailable (a broken-image icon would be uglier and the raw URL is
    // usually blocked anyway — that's why the byte fetch failed).
    const thumb = listing.imageProxyUrl
      ? html`<img
          class="listings__thumb"
          src=${listing.imageProxyUrl}
          alt=""
          loading="lazy"
        />`
      : html`<span
          class="listings__thumb listings__thumb--placeholder"
          aria-hidden="true"
        ></span>`;

    const body = html`
      ${thumb}
      <div class="listings__info">
        <span class="listings__row-retailer">
          ${listing.retailer ?? "Unknown"}
          ${listing.isPrimary
            ? html`<span class="listings__badge">primary</span>`
            : nothing}
        </span>
        <span class="listings__row-meta">
          ${stockChip}
          <span class="listings__last-check">
            ${formatRelative(listing.lastCheck)}
          </span>
        </span>
      </div>
      ${sparkD
        ? html`<svg
            class="listings__sparkline"
            viewBox="0 0 ${sparkW} ${sparkH}"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d=${sparkD} fill="none" stroke="currentColor" stroke-width="1.25" />
          </svg>`
        : html`<span class="listings__sparkline listings__sparkline--empty"></span>`}
      <div class="listings__price">
        ${formatPrice(listing.price, listing.currency || null)}
      </div>
    `;

    return html`
      <li class="listings__row">
        ${listing.url
          ? html`<a
              class="listings__link"
              href=${listing.url}
              target="_blank"
              rel="noopener noreferrer"
              @click=${(e: Event) => e.stopPropagation()}
              title=${listing.retailer ?? listing.url}
            >
              ${body}
            </a>`
          : html`<div class="listings__link listings__link--noUrl">${body}</div>`}
        <div class="listings__actions">
          ${this.onEditListing
            ? html`<button
                class="listings__edit"
                type="button"
                @click=${(e: Event) => this.handleEditListing(e, listing)}
                aria-label=${`Edit price selector for ${
                  listing.retailer ?? "listing"
                }`}
                title="Advanced: set a custom price selector"
              >
                ✎
              </button>`
            : nothing}
          ${listing.isPrimary
            ? nothing
            : html`<button
                class="listings__remove"
                type="button"
                @click=${(e: Event) => this.handleRemoveListing(e, listing)}
                aria-label=${`Remove ${listing.retailer ?? "listing"}`}
                title=${`Remove ${listing.retailer ?? "this listing"}`}
              >
                ×
              </button>`}
        </div>
      </li>
    `;
  }

  /**
   * Click handler for a row's ✎ button. Stops propagation (so the card's
   * open-source handler doesn't fire) and delegates to onEditListing,
   * which opens the panel's advanced selector editor for this listing.
   */
  private handleEditListing(event: Event, listing: Listing): void {
    event.stopPropagation();
    event.preventDefault();
    this.onEditListing?.(this.product, listing);
  }

  /**
   * Click handler for a row's × button. Stops propagation (so the
   * card's open-source handler doesn't fire), shows a native
   * confirmation, and delegates to onRemoveListing on confirm.
   *
   * window.confirm is intentionally minimal — feels heavy compared
   * to a slick custom modal but it's reliable across themes and
   * doesn't pull in modal-state plumbing. Easy to upgrade later if
   * we want a nicer UX.
   */
  private handleRemoveListing(event: Event, listing: Listing): void {
    event.stopPropagation();
    event.preventDefault();
    if (listing.isPrimary) return;  // Defensive — button shouldn't render
    const label = listing.retailer
      ? `Remove the ${listing.retailer} listing from ${this.product.title}?`
      : `Remove this listing from ${this.product.title}?`;
    if (!window.confirm(label)) return;
    this.onRemoveListing?.(this.product, listing);
  }

  private handleRefreshNow = (event: Event): void => {
    event.stopPropagation();
    if (this.refreshingNow) return;
    this.onRefreshNow?.(this.product);
  };

  private handleTogglePaused = (event: Event): void => {
    event.stopPropagation();
    this.onSetPaused?.(this.product, !this.product.paused);
  };

  /**
   * Commit an inline target-price edit. Parses the input value: empty
   * (or non-numeric) clears the target (null); a valid number sets it.
   * No-ops when the value hasn't changed so we don't fire redundant
   * service calls on every blur.
   */
  private handleTargetCommit = (event: Event): void => {
    event.stopPropagation();
    const input = event.target as HTMLInputElement;
    const raw = input.value.trim();
    const next = raw === "" ? null : Number(raw);
    if (next !== null && Number.isNaN(next)) {
      // Invalid input — restore the displayed value and bail.
      input.value =
        this.product.targetPrice != null ? String(this.product.targetPrice) : "";
      return;
    }
    const current = this.product.targetPrice;
    if (next === current) return;
    this.onSetTarget?.(this.product, next);
  };

  private handleTargetKeydown = (event: KeyboardEvent): void => {
    event.stopPropagation();
    if (event.key === "Enter") {
      (event.target as HTMLInputElement).blur();
    }
  };

  /**
   * Per-card action bar: inline target-price editor, a pause/resume
   * toggle, and a "Refresh now" button. Only rendered when the parent
   * wired at least one of the callbacks (so the card stays purely
   * presentational when used standalone, e.g. in tests).
   */
  private renderActions() {
    if (!this.onRefreshNow && !this.onSetTarget && !this.onSetPaused) {
      return nothing;
    }
    const { product } = this;
    return html`
      <div class="actions" @click=${(e: Event) => e.stopPropagation()}>
        ${this.onSetTarget
          ? html`<label class="actions__target" title="Notify when price drops to or below this">
              <span class="actions__target-label">Target</span>
              <input
                class="actions__target-input"
                type="number"
                inputmode="decimal"
                step="0.01"
                min="0"
                placeholder="—"
                .value=${product.targetPrice != null ? String(product.targetPrice) : ""}
                @change=${this.handleTargetCommit}
                @keydown=${this.handleTargetKeydown}
                @click=${(e: Event) => e.stopPropagation()}
              />
            </label>`
          : nothing}
        <div class="actions__spacer"></div>
        ${this.onSetPaused
          ? html`<button
              class="actions__btn"
              type="button"
              @click=${this.handleTogglePaused}
              aria-label=${product.paused ? "Resume polling" : "Pause polling"}
              title=${product.paused ? "Resume polling" : "Pause polling"}
            >
              <ha-icon icon=${product.paused ? "mdi:play" : "mdi:pause"}></ha-icon>
            </button>`
          : nothing}
        ${this.onRefreshNow
          ? html`<button
              class="actions__btn"
              type="button"
              ?disabled=${this.refreshingNow}
              @click=${this.handleRefreshNow}
              aria-label="Refresh price now"
              title="Refresh price now"
            >
              <ha-icon
                icon=${this.refreshingNow ? "mdi:loading" : "mdi:refresh"}
                class=${this.refreshingNow ? "actions__btn-spin" : ""}
              ></ha-icon>
            </button>`
          : nothing}
      </div>
    `;
  }

  private handleClick(event: MouseEvent) {
    // Ignore clicks on the explicit "Open at retailer" link — the
    // link does its own thing.
    if ((event.target as HTMLElement).closest("a")) return;
    this.onOpen?.(this.product);
  }

  render() {
    const { product } = this;
    const { value, currency } = this.headlinePrice;
    const sub = this.sourcePriceLine;

    return html`
      <article
        class="card ${product.discontinued ? "card--faded" : ""}"
        @click=${this.handleClick}
        tabindex="0"
        role="button"
        aria-label=${`Open ${product.title}`}
      >
        ${this.renderImage()}
        <div class="body">
          <header class="header">
            <h3 class="title">${product.title}</h3>
            ${this.renderStatusChips()}
          </header>

          <div class="price-block">
            <div class="price">${formatPrice(value, currency)}</div>
            ${
              // Delta placement depends on whether we're showing a
              // separate source-currency line. With FX (sub != nothing),
              // the delta goes inside .price-sub so it sits next to the
              // source price it actually refers to. Without FX, the
              // headline IS the source price, so the delta goes inline
              // in the .price-block (after .price).
              sub === nothing
                ? this.renderDelta()
                : html`<div class="price-sub">${sub} ${this.renderDelta()}</div>`
            }
          </div>

          ${this.renderSparkline()}
          ${this.renderStatRow()}
          ${this.renderListings()}
          ${this.renderAlternatives()}

          ${product.discontinued && product.discontinuedReason
            ? html`<p class="discontinued-reason">${product.discontinuedReason}</p>`
            : nothing}

          ${this.renderActions()}

          <footer class="footer">
            <span class="last-check">
              Last check: ${formatRelative(product.lastCheck)}
            </span>
            ${product.url
              ? html`<a class="link" href=${product.url} target="_blank" rel="noopener">
                  Open at retailer ↗
                </a>`
              : nothing}
          </footer>
        </div>
      </article>
    `;
  }

  static styles = css`
    :host {
      display: block;
    }

    .card {
      display: flex;
      flex-direction: column;
      background: var(--card-background-color, #fff);
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.08));
      overflow: hidden;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease;
      color: var(--primary-text-color, #212121);
    }
    .card:hover,
    .card:focus-visible {
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
      outline: none;
    }
    .card--faded {
      opacity: 0.65;
    }
    .card--faded:hover {
      opacity: 0.85;
    }

    .image {
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: contain;
      background: var(--secondary-background-color, #f5f5f5);
      display: block;
    }
    .image--placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--secondary-text-color, #757575);
      --mdc-icon-size: 48px;
    }

    .body {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      flex: 1;
    }

    .header {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .title {
      margin: 0;
      font-size: 1rem;
      font-weight: 500;
      line-height: 1.3;
      /* Clamp very long titles (Amazon-style "CORSAIR Dominator Titanium ..."
         that go on for 100 chars) so card heights stay consistent. */
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--secondary-background-color, #f0f0f0);
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
    }
    .chip--ok {
      background: var(--success-color, #43a047);
      color: #fff;
    }
    .chip--warn {
      background: var(--warning-color, #ffa726);
      color: #fff;
    }
    .chip--retailer {
      background: transparent;
      border: 1px solid var(--divider-color, #e0e0e0);
      color: var(--secondary-text-color, #757575);
    }
    .chip--paused {
      background: var(--secondary-text-color, #9e9e9e);
      color: #fff;
    }

    /* --- Per-card action bar --- */
    .actions {
      display: flex;
      align-items: center;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--divider-color, #e0e0e0);
    }
    .actions__spacer {
      flex: 1 1 auto;
    }
    .actions__target {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
    }
    .actions__target-label {
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .actions__target-input {
      width: 84px;
      box-sizing: border-box;
      padding: 4px 8px;
      font-size: 0.8rem;
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color, #e0e0e0);
      border-radius: 6px;
      outline: none;
    }
    .actions__target-input:focus {
      border-color: var(--primary-color, #03a9f4);
    }
    .actions__btn {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      cursor: pointer;
      color: var(--secondary-text-color, #757575);
      --mdc-icon-size: 18px;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .actions__btn:hover:not(:disabled) {
      color: var(--primary-color, #03a9f4);
      background: var(--secondary-background-color, #f5f5f5);
      border-color: var(--divider-color, #e0e0e0);
    }
    .actions__btn:disabled {
      cursor: wait;
      opacity: 0.6;
    }
    .actions__btn-spin {
      animation: alts-spin 1.2s linear infinite;
    }

    .price-block {
      display: flex;
      align-items: baseline;
      gap: 8px;
    }
    .price {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--primary-text-color, #212121);
    }
    .price-sub {
      font-size: 0.875rem;
      color: var(--secondary-text-color, #757575);
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
    }

    /* Price-movement indicator: red ↑ for an increase, green ↓ for
       a drop. Sits inline next to whichever line displays the
       source-currency price. Compact font so it doesn't compete
       with the headline. */
    .delta {
      font-size: 0.85rem;
      font-weight: 600;
      white-space: nowrap;
      padding: 1px 6px;
      border-radius: 4px;
    }
    .delta--up {
      color: var(--error-color, #d32f2f);
      background: var(--error-color-faded, rgba(211, 47, 47, 0.1));
    }
    .delta--down {
      color: var(--success-color, #43a047);
      background: var(--success-color-faded, rgba(67, 160, 71, 0.1));
    }

    .sparkline {
      width: 100%;
      height: 48px;
      color: var(--primary-color, #03a9f4);
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
      gap: 8px;
    }
    .stat {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .stat__label {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--secondary-text-color, #757575);
    }
    .stat__value {
      font-size: 0.875rem;
      font-weight: 500;
    }
    .stat__value--good {
      color: var(--success-color, #43a047);
    }

    .discontinued-reason {
      margin: 0;
      font-size: 0.8rem;
      font-style: italic;
      color: var(--warning-color, #ffa726);
    }

    .footer {
      margin-top: auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
    }
    .link {
      color: var(--primary-color, #03a9f4);
      text-decoration: none;
    }
    .link:hover {
      text-decoration: underline;
    }

    /* --- Alternatives section --- */
    .alts {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--divider-color, #e0e0e0);
    }
    .alts__header {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .alts__title {
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--primary-text-color, #212121);
      flex: 0 0 auto;
    }
    .alts__count {
      display: inline-block;
      min-width: 18px;
      padding: 0 6px;
      font-size: 0.7rem;
      font-weight: 600;
      text-align: center;
      border-radius: 999px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
      margin-left: 4px;
    }
    .alts__meta {
      flex: 1 1 auto;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
    }
    .alts__refresh {
      flex: 0 0 auto;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 4px;
      cursor: pointer;
      color: var(--secondary-text-color, #757575);
      --mdc-icon-size: 18px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .alts__refresh:hover:not(:disabled) {
      color: var(--primary-color, #03a9f4);
      background: var(--secondary-background-color, #f5f5f5);
      border-color: var(--divider-color, #e0e0e0);
    }
    .alts__refresh:disabled {
      cursor: wait;
      opacity: 0.6;
    }
    @keyframes alts-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .alts__refresh-spin {
      animation: alts-spin 1.2s linear infinite;
    }
    .alts__list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .alts__row {
      display: flex;
      align-items: center;
      gap: 4px;
      margin: 0;
      padding: 0;
    }
    .alts__link {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 6px 8px;
      border-radius: 6px;
      text-decoration: none;
      color: inherit;
      transition: background 120ms ease;
    }
    .alts__add {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .alts__add:hover {
      color: var(--success-color, #2e7d32);
      background: rgba(46, 125, 50, 0.08);
      border-color: rgba(46, 125, 50, 0.25);
    }
    .alts__add:focus-visible {
      outline: 2px solid var(--success-color, #2e7d32);
      outline-offset: 1px;
    }
    .alts__add--done {
      cursor: default;
      color: var(--success-color, #2e7d32);
    }
    .alts__add--done:hover {
      background: transparent;
      border-color: transparent;
    }
    .alts__link:hover {
      background: var(--secondary-background-color, #f5f5f5);
    }
    .alts__info {
      flex: 1 1 auto;
      min-width: 0;  /* allow truncation in flex children */
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .alts__row-title {
      font-size: 0.8rem;
      line-height: 1.3;
      color: var(--primary-text-color, #212121);
      /* Single-line clamp; rely on title attr for the full text. */
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .alts__row-meta {
      display: flex;
      gap: 8px;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
    }
    .alts__confidence {
      font-variant-numeric: tabular-nums;
    }
    .alts__ships {
      font-size: 0.7rem;
      padding: 1px 6px;
      border-radius: 999px;
      font-weight: 600;
      white-space: nowrap;
    }
    .alts__ships--yes {
      background: rgba(46, 125, 50, 0.15);
      color: var(--success-color, #2e7d32);
    }
    .alts__ships--no {
      background: rgba(120, 120, 120, 0.18);
      color: var(--secondary-text-color, #757575);
      text-decoration: line-through;
    }
    .alts__price {
      flex: 0 0 auto;
      font-size: 0.85rem;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
    }
    .alts__price--cheaper {
      color: var(--success-color, #43a047);
    }
    .alts__price--pricier {
      color: var(--warning-color, #ffa726);
    }
    .alts__price-unknown {
      color: var(--secondary-text-color, #757575);
      font-weight: 400;
    }
    .alts__empty {
      margin: 4px 0 0;
      font-size: 0.75rem;
      color: var(--secondary-text-color, #757575);
      font-style: italic;
    }
    .alts__hidden-note {
      margin: 2px 0 0;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
      font-style: italic;
    }
    .alts__error {
      margin: 0;
      font-size: 0.75rem;
      color: var(--error-color, #c62828);
      padding: 6px 8px;
      background: var(--secondary-background-color, #f5f5f5);
      border-radius: 6px;
    }

    /* --- Listings section ---
       Renders all user-tracked listings of this product as rows.
       Visually echoes the alts section so the two read as siblings
       (both are "other URLs" surfaced beneath the headline), but
       uses dashed top border + neutral count badge to distinguish
       "explicitly tracked" listings from "discovered" alternatives. */
    .listings {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding-top: 8px;
      border-top: 1px dashed var(--divider-color, #e0e0e0);
    }
    .listings__header {
      display: flex;
      align-items: center;
    }
    .listings__title {
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--primary-text-color, #212121);
    }
    .listings__count {
      display: inline-block;
      min-width: 18px;
      padding: 0 6px;
      font-size: 0.7rem;
      font-weight: 600;
      text-align: center;
      border-radius: 999px;
      background: var(--secondary-background-color, #e0e0e0);
      color: var(--secondary-text-color, #757575);
      margin-left: 4px;
    }
    .listings__list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .listings__row {
      display: flex;
      align-items: center;
      gap: 4px;
      margin: 0;
      padding: 0;
    }
    .listings__link {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 8px;
      border-radius: 6px;
      text-decoration: none;
      color: inherit;
      transition: background 120ms ease;
    }
    .listings__link:hover {
      background: var(--secondary-background-color, #f5f5f5);
    }
    .listings__link--noUrl {
      cursor: default;
    }
    .listings__link--noUrl:hover {
      background: transparent;
    }
    .listings__thumb {
      flex: 0 0 auto;
      width: 32px;
      height: 32px;
      border-radius: 5px;
      object-fit: cover;
      background: var(--secondary-background-color, #f0f0f0);
    }
    .listings__thumb--placeholder {
      display: inline-block;
      border: 1px solid var(--divider-color, #e0e0e0);
      box-sizing: border-box;
    }
    .listings__info {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .listings__row-retailer {
      font-size: 0.8rem;
      line-height: 1.3;
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .listings__badge {
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 1px 6px;
      border-radius: 999px;
      background: var(--primary-color, #03a9f4);
      color: var(--text-primary-color, #fff);
    }
    .listings__row-meta {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.7rem;
      color: var(--secondary-text-color, #757575);
    }
    .listings__chip {
      font-size: 0.65rem;
      padding: 1px 6px;
      border-radius: 999px;
      font-weight: 600;
      white-space: nowrap;
      background: var(--secondary-background-color, #f0f0f0);
      color: var(--secondary-text-color, #757575);
    }
    .listings__chip--ok {
      background: rgba(46, 125, 50, 0.15);
      color: var(--success-color, #2e7d32);
    }
    .listings__chip--warn {
      background: rgba(211, 47, 47, 0.12);
      color: var(--error-color, #c62828);
    }
    .listings__last-check {
      white-space: nowrap;
    }
    .listings__sparkline {
      flex: 0 0 80px;
      width: 80px;
      height: 24px;
      color: var(--primary-color, #03a9f4);
    }
    .listings__sparkline--empty {
      /* Placeholder takes the same space when history < 2 points
         so the columns line up across rows. */
      display: inline-block;
    }
    .listings__price {
      flex: 0 0 auto;
      font-size: 0.85rem;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--primary-text-color, #212121);
      white-space: nowrap;
    }
    .listings__remove {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .listings__remove:hover {
      color: var(--error-color, #c62828);
      background: rgba(211, 47, 47, 0.08);
      border-color: rgba(211, 47, 47, 0.2);
    }
    .listings__remove:focus-visible {
      outline: 2px solid var(--error-color, #c62828);
      outline-offset: 1px;
    }
    .listings__actions {
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      gap: 2px;
    }
    .listings__edit {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--secondary-text-color, #757575);
      font-size: 14px;
      line-height: 1;
      cursor: pointer;
      transition: color 120ms ease, background 120ms ease, border-color 120ms ease;
    }
    .listings__edit:hover {
      color: var(--primary-color, #1976d2);
      background: rgba(25, 118, 210, 0.08);
      border-color: rgba(25, 118, 210, 0.2);
    }
    .listings__edit:focus-visible {
      outline: 2px solid var(--primary-color, #1976d2);
      outline-offset: 1px;
    }
  `;
}

declare global {
  interface HTMLElementTagNameMap {
    "price-watch-card": PriceWatchCard;
  }
}
