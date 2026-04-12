# Airbnb listing detail page: extraction notes

The `airbnb_mallorca` spider requests each room detail page (see [AIRBNB_MALLORCA_ENTRY_POINT.md](AIRBNB_MALLORCA_ENTRY_POINT.md) for discovery). Several fields are parsed from the rendered HTML or embedded JSON. This document records **how we choose sources of truth** so downstream data stays aligned with what guests see on Airbnb.

---

## `latitude` and `longitude` (approximate map coordinates)

**Goal:** Persist **numeric coordinates** when Airbnb exposes them on the room detail page, so downstream steps can validate municipality or boundaries **without** relying on the human-readable `location` string (e.g. “Palma, Spain”), which can be ambiguous.

### Extraction priority (`_extract_coordinates` in `airbnb_mallorca.py`)

1. **Map marker attributes (preferred)**  
   Scan the raw HTML for `position="lat,lng"` or `position='lat,lng'` (including on elements such as `gmp-advanced-marker`). The listing map pin is treated as the clearest signal tied to the map UI. **First** attribute value that parses as a valid pair is kept.

2. **Embedded JSON / script payloads (fallback)**  
   If no marker match validates, search the page text for adjacent JSON-style pairs, in order:  
   `"latitude"` / `"longitude"` (either key order), then `"lat"` / `"lng"` (either key order). **First** regex match per pattern that validates is used.

### Validation

Each candidate pair must parse as floats with **latitude** in **[-90, 90]** and **longitude** in **[-180, 180]**. Non-numeric values, wrong arity (not exactly two comma-separated parts for `position`), or out-of-range numbers are **skipped**; the extractor continues until a valid pair is found or gives up and yields **`null`/`None`** for both fields.

### Relationship to `location`

We still populate **`location`** from the visible label (XPath / regex / JSON-LD address) as secondary metadata. **`latitude` / `longitude` are preferred for geospatial checks**; they are not derived from place names in this crawler.

### Tests

See `tests/test_airbnb_coordinates.py` (marker `position`, missing coordinates, malformed values, JSON fallback).

---

## `max_guests` (maximum occupancy)

**Goal:** Store the capacity shown in the **listing overview row** under the title (e.g. “6 guests · 4 bedrooms · …”), not incidental numbers in the long description (e.g. “events for up to 50 guests”).

### Why not a single regex on the full page?

A pattern like `\b(\d+)\s+guests?\b` over the **entire** HTML/JSON will often match the **first** occurrence in document order. The description and marketing copy can mention unrelated guest counts before or after the real overview line, so the first match is **not** a reliable capacity.

### Extraction priority (implemented in `airbnb_mallorca.py`)

1. **DOM — overview section (preferred)**  
   Airbnb renders the stats row inside a stable container:
   - `data-section-id="OVERVIEW_DEFAULT_V2"` (current PDP layout), or  
   - `data-section-id="OVERVIEW_DEFAULT"` (fallback id).  

   Inside that block we read **`ol > li`** items (guests, bedrooms, beds, baths) and take the **first** text that matches the guest pattern. If list markup differs, we still search **only** within that section’s text.

2. **Fallback — limited regex**  
   If the overview section is missing or has no guest line:
   - Prefer matching **only in text before** likely body sections (`DESCRIPTION…`, `ABOUT_DEFAULT`, etc.), so long-form description is excluded when those markers exist.
   - If no such cut point exists, search only the **first ~32k characters** of the response (header-sized slice), not unbounded megabyte payloads.

Return type remains a **string** of digits (or empty), consistent with `AirbnbListingItem.max_guests`.

### Tests

See `tests/test_airbnb_max_guests.py` for cases such as: overview “6 guests” vs description “50 guests”, `OVERVIEW_DEFAULT`, fallback before a description section, and malformed HTML without crashes.

### Provenance (`max_guests_source` and `max_guests_validation_status`)

The spider sets **`max_guests_source`** and **`max_guests_validation_status`** on each item.

**`max_guests_source`**

| Value | Meaning |
|--------|--------|
| `overview_dom` | Parsed from `OVERVIEW_DEFAULT_V2` / `OVERVIEW_DEFAULT` only. |
| `embedded_json` | Listing capacity from structured JSON keys in the initial payload (e.g. `personCapacity`, `guestCapacity`) — not description prose. |
| `limited_regex` | Header slice before DESCRIPTION / ABOUT (or first ~32k chars) — still avoids full description. |
| `none` | No capacity found. |

**`max_guests_validation_status`**

| Value | Meaning |
|--------|--------|
| `valid` | Capacity from overview or embedded JSON, within Airbnb’s per-listing guest limit (16). |
| `fallback_used` | Capacity from limited regex only, within limit. |
| `above_airbnb_limit` | A number was found but rejected (&gt; 16); **`max_guests` is empty**. |
| `missing` | No capacity after all steps. |

Values above **16** are never emitted in **`max_guests`**.

---

## `registration_number` and `registration_number_source`

**Extraction** is implemented in `radarlicencias/extractors/license.py` (`extract_registration_number_with_source`).

Priority (unchanged):

1. Mallorca regional registration block / structured patterns (`mallorca_regional_label`).
2. Standalone ETV/ETVPL in description or page text, excluding tokens embedded in Spain national strings (`description_standalone`).
3. Spain national `ESFCTU…` recovery (`spain_national_derived`).

The normalized **`registration_number`** string format is unchanged. **`registration_number_source`** is for audits and feed quality checks.

See `tests/test_license_registration.py`.

---

## Listing title and host (PDP)

- **`property_name` / `property_name_source`**: Prefer `data-section-id="TITLE_DEFAULT"` (h1), then listing-specific JSON keys such as `listingTitle`, then legacy `name`/`title` scan and `<title>`. See `_extract_property_name_with_source` in `airbnb_mallorca.py` and `tests/test_airbnb_property_host.py`.
- **`host_*` / `host_source`**: Prefer DOM sections `HOST_OVERVIEW_DEFAULT` and `MEET_YOUR_HOST` (primary host before co-host markers), then `PdpHostOverviewDefaultSection` JSON. See same tests.

---

## Related fields (pointers)

| Field / area | Notes |
|--------------|--------|
| Coordinates (`latitude` / `longitude`) | Section above; `_extract_coordinates` in `airbnb_mallorca.py`; `tests/test_airbnb_coordinates.py` |
| Hero image URL | `radarlicencias/extractors/airbnb_picture.py`, `tests/test_airbnb_picture.py` |
| Registration number | `radarlicencias/extractors` (license patterns), description text; provenance in `registration_number_source` |
| Discovery (quadtree + risky pagination) | `airbnb_mallorca.py`, `docs/AIRBNB_MALLORCA_ENTRY_POINT.md`; payload tests in `tests/test_airbnb_discovery.py` |
