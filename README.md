<p align="center">
  <img src="custom_components/price_watch/brand/logo.png" alt="Price Watch" width="540">
</p>

# Price Watch for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/davidh/price_watch.svg)](https://github.com/davidh/price_watch/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Track product prices from any e-commerce site. Paste a URL, get sensors. Powered by Claude AI for universal extraction.

## Features

- **Three extraction modes** — pick what fits your use case:
  - **Free / no API** — works on any site with Schema.org Product markup (most major retailers)
  - **Custom parser** — define CSS selectors / regex / JSONPath per site, also free
  - **AI-powered (Claude)** — universal fallback for sites without structured data, requires Anthropic API key
- **Paste a URL, get a device** — config flow auto-extracts product title, price, image, stock status
- **Built-in price history** — lowest seen, highest seen, current vs target diff, 30-entry history
- **Smart cost controls** — content-hash skipping, prompt caching, configurable intervals, monthly budget cap
- **Native HA events** — `price_watch_price_drop`, `price_watch_target_hit`, `price_watch_new_low`, `price_watch_back_in_stock`
- **Multi-currency** — auto-detects from page (NOK, ISK, EUR, USD, etc.)

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/davidh/price_watch` as **Integration**
3. Install **Price Watch**, restart HA
4. Settings → Devices & Services → Add Integration → **Price Watch**
5. Optionally add an Anthropic API key (or leave blank for free mode — works on any site with JSON-LD product data, plus user-defined custom parsers)

### Manual

Copy `custom_components/price_watch/` into your HA `config/custom_components/` directory and restart.

## Adding a product

Settings → Devices & Services → Price Watch → **Add product**

Paste any product URL. The integration fetches the page, extracts product info via Claude, and shows a preview. Confirm to create the device.

## Sensors per product

| Entity | Description |
|---|---|
| `sensor.<slug>_price` | Current price (main sensor) |
| `sensor.<slug>_lowest` | Lowest price seen since tracking began |
| `sensor.<slug>_highest` | Highest price seen since tracking began |
| `sensor.<slug>_target_diff` | Current minus target (negative = at/below target) |
| `binary_sensor.<slug>_in_stock` | Stock availability |

Each device exposes attributes: `product_url`, `image_url`, `retailer`, `currency`, `last_check`, `price_history` (last 30 entries with timestamps).

## Events

```yaml
# Example automation
alias: Notify on price drop
trigger:
  - platform: event
    event_type: price_watch_target_hit
action:
  - service: notify.mobile_app_davidh
    data:
      title: "💰 Target hit: {{ trigger.event.data.title }}"
      message: "{{ trigger.event.data.price }} {{ trigger.event.data.currency }} — was {{ trigger.event.data.target }}"
      data:
        url: "{{ trigger.event.data.url }}"
```

Event data for all events: `entry_id`, `title`, `url`, `retailer`, `price`, `currency`, `previous_price`, `target`, `image_url`.

## Cost

Default settings (6h interval, 10 products, content-hash skipping, prompt caching) typically cost **$0.50–$2/month** in Anthropic API usage. Hard daily/monthly caps are configurable.

For zero-cost tracking, define a custom parser (see [docs/custom_parsers.md](docs/custom_parsers.md)).

## Services

- `price_watch.refresh_now` — force immediate refresh of one or all products
- `price_watch.set_target` — update target price
- `price_watch.reset_history` — wipe price history for a product

## License

MIT © Davíð
