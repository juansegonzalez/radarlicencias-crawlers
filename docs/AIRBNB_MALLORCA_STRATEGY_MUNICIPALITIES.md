# Strategy: Cover All Mallorca Listings via Municipalities

## The problem

A single island-wide search (`/s/Majorca--Spain/homes`) returns only **~15 pages × 20 ≈ 300 results**. Airbnb caps or samples that view, so we miss thousands of listings.

## Approach: One search per municipality

Mallorca has **53 municipalities** (official, same as in the Consell de Mallorca registry). If we run one search per municipality and paginate each, we get:

- **53 starting points** (manageable, stable list).
- **No dependency** on Airbnb offering a “directory” or full island view.
- **Alignment with the Consell**: your license data is per municipality, so comparing “licensed vs listed on Airbnb” by municipality is natural.
- **Reasonable scale**: 53 × (pages per municipality). Large ones (Palma, Calvià, etc.) may have many pages; small ones (Deià, Escorca) few. Total requests stay bounded and we can tune concurrency.

## Why municipalities over “cities and towns”

| | Municipalities (53) | Cities/towns (many more) |
|--|---------------------|---------------------------|
| **Count** | 53 | Hundreds (every village, district) |
| **Source** | Official (Consell), same as license registry | Would need another source and dedup |
| **Overlap** | Listings may appear in one or two municipalities near borders | Same listing can appear under town name, district, “near X” |
| **Deduplication** | By listing_id across 53 runs | Same, but more runs and more overlap |
| **Cost** | 53 start URLs + pagination | Many more start URLs + pagination |

**Recommendation: use municipalities.** Fewer seeds, same coverage in practice, and matches how you already segment data (licenses by municipality). If we see big gaps (e.g. a municipality with zero or very few results), we can add a small list of “extra places” (e.g. well-known resort names) later.

## Implementation outline

1. **List of 53 municipalities**  
   Use the official Mallorca list (e.g. from Consell or [Wikipedia](https://en.wikipedia.org/wiki/List_of_municipalities_in_Balearic_Islands) – filter by Island = Mallorca). Stored in the project (e.g. `data/mallorca_municipalities.txt` or a Python constant).

2. **Map municipality → Airbnb search**  
   For each municipality, build a search URL. Airbnb accepts:
   - **Search path**: `/s/{query}/homes` (e.g. `Palma de Mallorca`, `Sóller`, `Valldemossa`).
   - **Stays URL** (if it exists): `/{slug}-spain/stays` (e.g. `palma-de-mallorca-spain`, `soller-spain`).  
   Prefer the **search URL** so we don’t depend on Airbnb’s slug for every village. Use the municipality name plus “Mallorca” or “Spain” if needed (e.g. `Sóller Mallorca` or `Palma de Mallorca`) so we stay on the island.

3. **Spider behaviour**  
   - **Start requests**: one request per municipality (search URL with `items_offset=0`).
   - **Parse list**: extract listing IDs/URLs from the page; yield items (or follow to detail). Then:
     - If there are more results, yield the same search URL with `items_offset=20`, `40`, …
     - Stop when a page returns &lt; 20 results (or zero).
   - **Deduplication**: by listing_id when exporting or in post-processing (same listing can appear in two municipalities near the border).

4. **Name normalization (optional)**  
   Some names have accents or variants (e.g. Pollença vs Pollensa, Palma vs Palma de Mallorca). We can maintain a small dict `municipality → Airbnb search string` for the few that need it and use the official name for the rest.

## Data source for the 53 municipalities

- **Consell de Mallorca**: your license registry already has a municipality field; the set of distinct values is the canonical list.
- **Fallback**: use the Mallorca-only rows from the [list of municipalities in the Balearic Islands](https://en.wikipedia.org/wiki/List_of_municipalities_in_Balearic_Islands) (Island = Mallorca).

We’ve added `radarlicencias/data/mallorca_municipalities.txt` (and a Python list in the spider) so the spider can iterate over the same 53 names. You can replace this later with the list derived from the Consell registry if you prefer a single source of truth.

## Summary

- **Best strategy**: run one search per **municipality** (53 runs), paginate each, then deduplicate by listing_id.
- **Why not only “cities and towns”**: more seeds, more overlap, no clear gain over 53 municipalities for “all Mallorca” coverage.
- **Why municipalities**: stable, official, matches the Consell license data, and keeps the number of entry points small.
