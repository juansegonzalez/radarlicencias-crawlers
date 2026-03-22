# Airbnb Mallorca spider — StaysSearch JSON + quadtree strategy

This document describes the **current discovery strategy** used by `airbnb_mallorca`.

## Goals

- **Maximize unique Mallorca listings** discovered from Airbnb.
- Keep Zyte API usage **as cheap as possible** while maintaining coverage and data quality.
- Avoid brittle HTML list parsing and heavy `browserHtml` rendering.

## Request strategy (cost)

- **Discovery (list / map boxes)**: Airbnb’s internal `StaysSearch` JSON endpoint, requested via Zyte **`httpResponseBody`** (no browser).
- **Detail pages**: Airbnb listing HTML (`/rooms/<id>`) via Zyte **`httpResponseBody`**.

There is **no `browserHtml` in this spider anymore**. All requests are plain HTTP (proxied by Zyte).

## Discovery: adaptive quadtree over Mallorca

- The spider defines a rough Mallorca bounding box:
  - `MALLORCA_SW_LAT/LNG`, `MALLORCA_NE_LAT/LNG`
- It starts from this **root bbox** and calls the `StaysSearch` JSON endpoint once for that bbox.
- Each JSON response contains up to **18 results** (`STAYSSEARCH_PAGE_SIZE = 18`).

For any bbox:

- Let `searchResults` be the list of results from the JSON response.
- Let `n = len(searchResults)`.

We apply the agreed rule:

- **If `n == 18`** (full page):
  - The area is considered **dense / capped**.
  - We treat this bbox as an **internal node** in a **quadtree**:
    - Split it into 4 child bboxes (SW, SE, NW, NE).
    - Recursively call `StaysSearch` once per child bbox.
  - We **do not paginate** this bbox; we rely solely on splitting.

- **If `n < 18`**:
  - The area is considered a **leaf node**:
    - We assume all listings in that rectangle are visible in this single response.
    - We **do not split further** and **do not paginate** this bbox.
    - We extract listing IDs from `searchResults` and schedule detail requests.

We also enforce a minimum bbox size (`MIN_CELL_LAT_SPAN`, `MIN_CELL_LNG_SPAN`): if a bbox gets smaller than this, we stop splitting even if `n == 18` and treat it as a leaf (to avoid infinite splits in pathological cases).

### Why this approach

We considered and rejected:

- **Fixed HTML grid + pagination + `browserHtml`**:
  - Pros: simple conceptually.
  - Cons:
    - Requires headless browser rendering (expensive per request).
    - Needs HTML selectors that are brittle to UI changes.
    - Wastes many pages in sparse areas (large cells with only a few listings).

- **Fixed grid + `StaysSearch` JSON + pagination**:
  - Better than HTML, but still:
    - Wastes calls in sparse boxes.
    - Requires pagination logic (itemsOffset) and stopping rules.

Instead, the **quadtree + JSON** approach:

- Adapts to local density:
  - Dense areas are split into many small bboxes.
  - Sparse areas stop early with very few calls.
- Eliminates traditional pagination:
  - We never use `itemsOffset` for leaf nodes.
  - Each bbox is queried **once**.
- Keeps costs low:
  - No browsers.
  - Fewer total discovery calls for similar or better coverage.

## Deduplication (global)

Listings are deduplicated globally across **all bboxes**:

- From each `searchResults` entry we extract a stable listing ID.
- We keep a global set `_seen_listing_keys`:
  - If we have already seen an ID, we **skip** requesting its detail page again.
  - Otherwise we schedule a single detail request.

This is critical for cost: the same listing can appear in multiple neighboring bboxes.

## Output fields (unchanged)

The Airbnb item includes:

- `url`
- `listing_id`
- `location` (from detail HTML)
- `max_guests` (from detail HTML)
- `description_text` (full text extracted from embedded payload)
- `registration_number` (Mallorca regional registration number extracted from detail payload)

We **do not** emit a `municipality` field for Airbnb items; it can be derived later from `location` or via geocoding.

