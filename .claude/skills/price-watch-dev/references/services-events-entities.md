# Services, events, and entities (verified against repo)

Authoritative as of v0.2.2 (2026-09-13); services and events re-checked against `services.yaml` and `const.py` on 2026-10-07. Eleven services.

## Services

| Service | Purpose |
|---|---|
| `price_watch.track_product` | Create a tracked product from a URL |
| `price_watch.add_listing` | Add a retailer listing under a product |
| `price_watch.remove_listing` | Remove a listing (cleans up its entities — no ghost rows) |
| `price_watch.edit_listing` | Set a custom parser, cookies, currency, unit price, or swap a listing's URL |
| `price_watch.set_target` | Update the target price |
| `price_watch.set_variant` | Pick a variant (size/length) on supported pages |
| `price_watch.set_paused` | Pause/resume polling (keeps the last known price) |
| `price_watch.find_alternatives` | Run a discovery search for one or all products |
| `price_watch.refresh_now` | Force an immediate refresh |
| `price_watch.reset_history` | Wipe a product's price history |
| `price_watch.untrack_product` | Stop tracking a product entirely (added in 0.2.1, alongside the panel's delete-product button) |

`request_cookies` passed via `add_listing` / `edit_listing` is stored inside `custom_parser.request_cookies` and accepts a header string, a `{name: value}` dict, or a list of cookie dicts.

## Events

All prefixed `price_watch_`. Build automations on these `event` triggers:

| Event | Fires when |
|---|---|
| `price_watch_price_drop` | Price decreased |
| `price_watch_target_hit` | Price reached/crossed the target |
| `price_watch_new_low` | New all-time low |
| `price_watch_back_in_stock` | Came back in stock |
| `price_watch_discount` | The retailer's own sale/strikethrough appeared |
| `price_watch_discontinued` | The product looks discontinued |

Event data: `entry_id`, `title`, `url`, `retailer`, `price`, `currency`, `previous_price`, `target`, `image_url`, `in_stock`; per-listing events also carry `listing_id`. `price_watch_discount` adds `original_price` / `discount_percent`; `price_watch_discontinued` adds `discontinued_at` / `discontinued_reason`, `last_known_price` / `last_known_currency` and `manual`. The panel's 🔔 dialog can write these automations.

## Entities per product

`<slug>` is the product slug.

| Entity | Description |
|---|---|
| `sensor.<slug>_price` | Current price (main sensor) |
| `sensor.<slug>_price_local` | Price converted to home currency |
| `sensor.<slug>_lowest_seen` | Lowest price since tracking began |
| `sensor.<slug>_highest_seen` | Highest price since tracking began |
| `sensor.<slug>_target_diff` | Current minus target (negative = at/below target) |
| `sensor.<slug>_stock_count` | Units in stock, where exposed |
| `binary_sensor.<slug>_in_stock` | Stock availability |
| `binary_sensor.<slug>_discontinued` | Looks discontinued |
| `image.<slug>_photo` | Product photo |
| `button.<slug>_refresh_now` | Refresh this product now |

The price sensor's attributes: `product_url`, `image_url`, `retailer`, `currency`, `last_check`, `price_history`, all-time low / "is at low", typical price, optional per-unit price (e.g. kr/m), and per-store stock where available.
