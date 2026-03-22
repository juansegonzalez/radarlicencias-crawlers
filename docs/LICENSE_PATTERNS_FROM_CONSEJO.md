# License patterns from Consejo de Mallorca census

The **Airbnb spider** extracts Mallorca registration numbers (e.g. ETV/12345, VT/474, TI/69) from listing descriptions. The set of valid formats (prefixes like ETV, VT, TI, ETVPL, ET) comes from the **official census** so we don’t rely on a hardcoded list.

## Flow

1. **Run the Consejo spider**  
   It crawls the full census (no filters) with all signature formats. Use `-a max_pages=N` to limit pages (e.g. for a sample to discover formats).

   ```bash
   PYTHONPATH=. SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl consejo_mallorca -o data/consejo_all_signatures.jsonl
   ```

2. **Build the license-pattern file**  
   From the JSONL output, extract unique signature prefixes and write `radarlicencias/data/license_patterns.py`:

   ```bash
   python scripts/build_license_patterns.py data/consejo_all_signatures.jsonl
   ```

3. **Run the Airbnb spider**  
   The Airbnb spider loads `license_patterns.py` if present and uses it to match registration numbers. If the file is missing (e.g. first run, or the file isn’t in the deployed package), it falls back to a built-in list of common formats.

## When to regenerate

- After the first setup, so the Airbnb spider uses the full set of census formats.
- Periodically (e.g. once a year) or whenever you notice new signature types in the census, re-run the Consejo no-filter crawl and `build_license_patterns.py`.

## Files

- **Consejo spider**  
  Always crawls the full census (no filters); all signature formats.

- **Script**  
  `scripts/build_license_patterns.py` reads the Consejo JSONL and writes `radarlicencias/data/license_patterns.py` (single constant `LICENSE_CODE`).

- **Airbnb spider**  
  Uses `radarlicencias/data/license_patterns.py` when present; otherwise uses the built-in pattern.
