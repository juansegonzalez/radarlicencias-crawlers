# Code review notes

## “20” in the spider (RESULTS_PER_PAGE)

**Not a limit.** `RESULTS_PER_PAGE = 20` is **Airbnb’s page size** (how many results they show per page). The spider uses it to:

1. **Build the next page URL** – offset 0, then 20, then 40, then 60, …
2. **Decide whether to keep paginating** – if the current page has **at least** 20 listing links, we request the next page; when a page has **fewer than 20**, we stop for that municipality.

So we **keep paginating until there are no more results**. If Airbnb ever shows more than 20 per page (e.g. 24 or 30), you can update the constant and redeploy; the logic stays the same.

## What was checked

- **Settings**: Entry point is `radarlicencias.settings` (package `__init__.py` loads `base`). No `settings.py` file that could shadow the package.
- **Spider discovery**: `scrapy list` shows `airbnb_mallorca` and `consejo_mallorca`.
- **Pagination**: No cap on total listings; we stop only when a page returns &lt; 20 links.
- **Items**: `AirbnbListingItem` has `url`, `municipality`, `registration_number`, `listing_id`, `scraped_at`. Pipeline passes items through.
- **Consejo spider**: Stub only; needs `start_url` or `start_urls` when you add the Consell URL and parsing.
- **Data file**: `radarlicencias/data/mallorca_municipalities.txt` is loaded from the package path; works locally and on Scrapy Cloud.

## If Airbnb changes page size

If they switch to e.g. 24 or 30 results per page, set `RESULTS_PER_PAGE` to that value in `airbnb_mallorca.py` and redeploy. Pagination logic does not need to change.

## Latest improvements (final pass)

- **List/detail status**: List and detail pages with non-200 responses are skipped (logged); only successful fetches produce items. Failed requests are retried by Scrapy.
- **Registration number**: Fallback regex allows optional space (e.g. `ETV/ 9714`); all captured values are normalized (inner spaces removed) for consistent matching.
- **Same listing, multiple municipalities**: Detail requests use `dont_filter=True` so the same listing can be requested once per municipality where it appears in search; you get one item per (listing, municipality) for full matching info.
- **Consejo spider**: Logs a clear warning when no start URL is set so it’s obvious why the spider does nothing.
- **Pipeline**: Defensive check for `None` item.
- **Local settings**: Removed unused variable; data path unchanged.
