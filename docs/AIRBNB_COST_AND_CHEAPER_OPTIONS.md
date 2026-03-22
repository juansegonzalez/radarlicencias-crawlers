# Airbnb spider: cost and cheaper options

## Why it used to cost more

Zyte charges per request. **Browser requests** (with `browserHtml` and `actions`) cost roughly **7–15× more** than **HTTP requests** (httpResponseBody).

We used to use browser + "Show more" on detail pages to reveal the registration number. It turns out the full description (including registration) is already in the initial HTML — it’s only visually truncated with CSS (`-webkit-line-clamp`, `overflow: hidden`). So we don’t need browser or clicks for detail.

## What we do now (cheapest that works)

In practice Airbnb **loads search results via JavaScript**: with **httpResponseBody** alone, list pages return 200 but **no** listing links (0 items per run). So we use:

- **List and pagination**: **browserHtml** (required to get any listing URLs from search).
- **Detail**: **httpResponseBody** (registration is in the initial HTML; no browser or "Show more" needed).

So list/pagination cost more per request, but detail — the majority of requests by count — stays cheap.

Plus **one detail request per listing** (deduplication by listing ID), so the same listing is never requested twice even when it appears in multiple search results.

## Summary

- **List/pagination**: browserHtml (required). **Detail**: httpResponseBody. Deduplication: one detail per listing.
- **Caveat**: If Airbnb ever serves the description only after JS (or behind a real "Show more" that loads content), extraction would drop; then we’d need to consider browser again for detail only.

To reduce cost further you can run less often, cap listings per region (e.g. `-a max_items=100`), or use fewer regions (`-a max_regions=53`).
