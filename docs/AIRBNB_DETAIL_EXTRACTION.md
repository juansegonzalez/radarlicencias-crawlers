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

---

## Related fields (pointers)

| Field / area | Notes |
|--------------|--------|
| Coordinates (`latitude` / `longitude`) | Section above; `_extract_coordinates` in `airbnb_mallorca.py`; `tests/test_airbnb_coordinates.py` |
| Hero image URL | `radarlicencias/extractors/airbnb_picture.py`, `tests/test_airbnb_picture.py` |
| Registration number | `radarlicencias/extractors` (license patterns), description text |
