# Price Watch

Track product prices across the web from inside Home Assistant. Paste a URL, get sensors and a price history. Works **free** on most major retailers (no API key) — with an optional AI fallback for the tricky ones.

> **Beta — testers welcome.** Please report retailers that do/don't work and any bugs on the [issue tracker](https://github.com/TheIcelandicguy/price_watch/issues).

## Highlights

- **Free by default** — reads price/stock from Schema.org / Open Graph data, which most major retailers expose. No account, no key, no cost.
- **A sidebar panel** — add, search, compare and manage everything from one screen. No YAML.
- **Compare across retailers** — track the same item at several shops, converted to your home currency, and find it cheaper with the built-in "Search & add" discovery.
- **Per-product sensors** — price, local-currency price, lowest/highest seen, target diff, stock — plus a rolling history.
- **Smart alerts** — Home Assistant events on price drops, target hits, new lows, restocks and "on sale".
- **Optional AI** — Anthropic (Claude) or any OpenAI-compatible endpoint including local **Ollama**, used as a fallback for pages free mode can't read.

Free to run. An optional Anthropic key costs roughly $0.50–$2/month for typical use; a local Ollama model is free.
