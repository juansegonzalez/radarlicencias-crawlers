# Airbnb Mallorca: Best Entry Point for Crawling

## Summary

**Airbnb does not provide a directory or sitemap of all listings.** The only way to get (almost) all properties in Mallorca is to **start from the search results** and paginate. There is no single “list all” URL.

---

## What Exists on Airbnb

| What you see | What it is | Use for crawling? |
|--------------|------------|--------------------|
| **Search bar** | User types a place; backend runs a search | No direct URL to “all listings” |
| **`/majorca-spain/stays`** | **Region landing page** (curated) | Not a directory. Shows featured listings + links to search. |
| **`/s/Majorca--Spain/homes?...`** | **Search results** for “Majorca, Spain” | **Yes — this is the entry point.** |
| **Sitemap** | `/sitemaps/` exists but lists no listing URLs | Not useful for “all Mallorca” |

So: **start from the search URL**, then paginate. Do **not** rely on `/majorca-spain/stays` as a directory.

---

## Recommended Entry Point (Option B)

Use the **search results URL** that targets the whole island via Airbnb’s place ID for “Majorca, Spain”:

```
https://www.airbnb.com/s/Majorca--Spain/homes?place_id=ChIJKcEGZna4lxIRwOzSAv-b67c&refinement_paths[]=/homes
```

- **`/s/Majorca--Spain/homes`** — search path for “Majorca, Spain”.
- **`place_id=ChIJKcEGZna4lxIRwOzSAv-b67c`** — Google Place ID for the island (stable, locale‑independent).
- **`refinement_paths[]=/homes`** — restricts to “Homes” (stays), not Experiences.

**Pagination:** add `items_offset` (20 results per page):

- Page 1: `...&items_offset=0`
- Page 2: `...&items_offset=20`
- Page 3: `...&items_offset=40`
- Continue until a page returns fewer than 20 results (or zero).

So the crawler should:

1. **Start from** the URL above (with `items_offset=0`).
2. **Parse** the search results page (needs **browser rendering** — Zyte `browserHtml`) to get listing links or listing IDs.
3. **Follow pagination** by generating the same URL with `items_offset=20`, `40`, `60`, … until no more results.
4. Optionally **visit each listing detail page** for full data (or use data from the listing cards to save requests).

---

## Alternative (Option A): Simple search query

If you prefer not to depend on `place_id`, you can use the text search:

```
https://www.airbnb.com/s/Mallorca/homes
```

or

```
https://www.airbnb.co.uk/s/Mallorca/homes
```

Same idea: this is a **search results** page. Paginate with `items_offset=0`, 20, 40, …  
Results should be the same island; `place_id` is slightly more explicit and stable across locales.

---

## Why not start from `/majorca-spain/stays`?

- It is a **marketing/landing page**, not a listing index.
- It shows a **curated subset** (e.g. “Top-rated”, “Guest favourite”, “Apartment rentals with wifi”).
- It does **not** list all Mallorca properties.
- It *does* contain links to the **search** URL with `place_id=ChIJKcEGZna4lxIRwOzSAv-b67c`, which we use as the entry point above.

So we use the **search URL** as the single starting point and paginate; we do **not** crawl the stays page as if it were a directory.

---

## Practical recommendation

- **Best place to initiate crawling:** the **search URL**.
- **Method:** request search URLs with **Zyte browser rendering** (`browserHtml: true`), parse listing links/IDs from the DOM, then paginate by `items_offset`.
- **Production strategy:** the spider uses **per-municipality search regions** (see `radarlicencias/data/search_regions_mallorca.txt`) so coverage stays bounded and predictable.
- **No directory:** there is no “directory” or sitemap that lists all Mallorca properties; search + pagination is the only way.

---

## Current `airbnb_mallorca` implementation (StaysSearch + quadtree)

The spider does **not** crawl HTML search pages for discovery. It POSTs Airbnb’s **`StaysSearch`** GraphQL operation (persisted query) with a **map bounding box** over Mallorca, then:

1. **Quadtree:** If a response returns a **full page** of results (18 items, `STAYSSEARCH_PAGE_SIZE`), the bbox is split into four children and each child is queried. If the response returns **fewer than 18** results, the node is a **leaf** (no further splitting).
2. **Truncation-risk leaves:** If the quadtree **cannot** subdivide further (**max depth** reached or **minimum cell size**), but the API still returns a **full page (≥ 18)**, that leaf may be **truncating** listings. The spider logs this and, by default, issues **additional StaysSearch requests** with **`itemsOffset`** in `rawParams` to recover more listing IDs (deduped globally). Disable with:  
   `scrapy crawl airbnb_mallorca -a disable_risky_leaf_pagination=true`

End-of-run logs include counters such as `stayssearch_nodes_visited`, `truncation_risk_leaves`, `risky_leaf_pagination_*`, and `duplicate_listing_ids_skipped`. See `parse_stayssearch_node` / `parse_stayssearch_risky_pagination` in `radarlicencias/spiders/airbnb_mallorca.py`.

---

## See also

- **[AIRBNB_DETAIL_EXTRACTION.md](AIRBNB_DETAIL_EXTRACTION.md)** — how listing **detail** pages are parsed (e.g. `max_guests` from the overview block, not arbitrary text on the page).
