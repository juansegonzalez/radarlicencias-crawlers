# Airbnb Mallorca spider — production reference

This document summarizes how the `airbnb_mallorca` spider behaves in production (Scrapy Cloud + Zyte), what each exported field means, and how to deploy.

## Discovery

- **Primary:** `StaysSearch` GraphQL (persisted query) over the Mallorca bounding box + **quadtree** splitting when a full page of results (18) is returned.
- **Truncation-risk leaves:** When the tree cannot subdivide further (max depth or minimum cell size) but the API still returns a full page, the spider logs a warning and may issue **additional `itemsOffset` requests** to recover more listing IDs (deduplicated globally).
- **Disable pagination:** `scrapy crawl airbnb_mallorca -a disable_risky_leaf_pagination=true` (default: enabled).

See [AIRBNB_MALLORCA_ENTRY_POINT.md](AIRBNB_MALLORCA_ENTRY_POINT.md) for URLs and context.

## Detail pages

- Requests use Zyte with **`httpResponseBody`** (raw HTML) for listing pages.
- Parsing combines **DOM** (where present), **embedded JSON** in the initial payload, and **conservative regex fallbacks** (never unbounded description scans for sensitive fields).

Full field logic: [AIRBNB_DETAIL_EXTRACTION.md](AIRBNB_DETAIL_EXTRACTION.md).

## `AirbnbListingItem` — important fields

| Field | Notes |
|--------|--------|
| `url`, `listing_id` | Listing identity |
| `location` | Visible location label |
| `latitude`, `longitude` | From map marker / JSON; preferred over text for geo checks |
| `registration_number`, `registration_number_source` | Mallorca license extraction with provenance (`mallorca_regional_label`, `description_standalone`, `spain_national_derived`, `none`) |
| `max_guests`, `max_guests_source`, `max_guests_validation_status` | See below |
| `property_name`, `property_name_source` | Title; A/B test tokens (e.g. `treatment`) are rejected |
| `picture_url` | Hero / CDN; banned patterns filtered |
| Host fields + `host_source` | DOM preferred, JSON fallback |
| `rating`, `review_count` | From JSON / visible HTML |

## `max_guests` (capacity)

**Order of extraction**

1. **Overview DOM** — `OVERVIEW_DEFAULT_V2` / `OVERVIEW_DEFAULT` guest line.
2. **Embedded JSON** — structured keys only (e.g. `personCapacity`, `guestCapacity`, …), not description prose.
3. **Limited regex** — header-sized slice before DESCRIPTION / ABOUT (or first ~32k chars).

**Platform rule:** values **greater than 16** are **never** emitted in `max_guests` (Airbnb listing cap). Such extractions set `max_guests_validation_status` to `above_airbnb_limit` and leave `max_guests` empty.

**`max_guests_source`:** `overview_dom` | `embedded_json` | `limited_regex` | `none`

**`max_guests_validation_status`:** `valid` | `fallback_used` | `above_airbnb_limit` | `missing`

In production (`httpResponseBody`), capacity often comes from **`embedded_json`** when overview markup is absent from the initial HTML.

## Observability (stats)

Stats are prefixed with `airbnb_mallorca/` — including discovery counters, `max_guests_*`, registration counts, and risky-leaf pagination metrics. See spider `closed()` logging.

## Tests

- `tests/test_airbnb_*.py`, `tests/test_license_registration.py` cover extraction rules.

## Deploying to production

1. **Repository:** merge to `main` and push (CI / review as per your process).
2. **Scrapy Cloud:** from the project root, `shub deploy` (see [DEPLOY.md](../DEPLOY.md)).
3. **Secrets:** `ZYTE_API_KEY` in Scrapy Cloud project settings (not in the repo).
4. **Feeds:** configure JSON Lines (or your format) on the job / project.

## Related docs

- [AIRBNB_MALLORCA_ENTRY_POINT.md](AIRBNB_MALLORCA_ENTRY_POINT.md) — discovery entry points
- [AIRBNB_DETAIL_EXTRACTION.md](AIRBNB_DETAIL_EXTRACTION.md) — detail-page extraction rules
- [LICENSE_PATTERNS_FROM_CONSEJO.md](LICENSE_PATTERNS_FROM_CONSEJO.md) — registration pattern generation
