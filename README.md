# Radarlicencias crawlers

Scrapy project: **Consejo de Mallorca** (tourist licenses) + **Airbnb Mallorca** (listings).  
Runs once a month on **Scrapy Cloud**; output is consumed by your post-processing pipeline.

**Goal:** Cross the two datasets to find Airbnb listings that lack a valid license or have other irregularities (e.g. license not in the official registry, address mismatch).

## Setup

**Use a virtual environment** so dependencies don’t mix with the rest of your system:

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

For local runs, set your Zyte API key:

```bash
export ZYTE_API_KEY=your_key_here
```

## Spiders

| Spider              | Command                         | Purpose                    |
|---------------------|----------------------------------|----------------------------|
| consejo_mallorca    | `scrapy crawl consejo_mallorca`  | Tourist licenses (Mallorca)|
| airbnb_mallorca     | `scrapy crawl airbnb_mallorca`   | Airbnb listings (Mallorca) |

## Local run (with local settings and feed to `data/`)

From the project root. If you get `ModuleNotFoundError: No module named 'radarlicencias'`, prefix with `PYTHONPATH=.`:

```bash
PYTHONPATH=. SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl consejo_mallorca -a start_url=https://...
PYTHONPATH=. SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl airbnb_mallorca
```

Both spiders crawl all data (Consejo: all pages until no more; Airbnb: **StaysSearch + quadtree** over Mallorca with optional risky-leaf `itemsOffset` pagination — see [docs/AIRBNB_MALLORCA_ENTRY_POINT.md](docs/AIRBNB_MALLORCA_ENTRY_POINT.md)).

### License patterns from Consejo (optional but recommended)

So the Airbnb spider recognises all registration formats from the official census, you can build the pattern file from an unfiltered Consejo run:

```bash
scrapy crawl consejo_mallorca -o data/consejo_all_signatures.jsonl
python scripts/build_license_patterns.py data/consejo_all_signatures.jsonl
```

See [docs/LICENSE_PATTERNS_FROM_CONSEJO.md](docs/LICENSE_PATTERNS_FROM_CONSEJO.md) for details.

## Scrapy Cloud and testing

The project is **ready to deploy** to Scrapy Cloud. For full steps (local test, deploy, feed, periodic jobs), see **[DEPLOY.md](DEPLOY.md)**.

- **Unit tests:** `PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py' -v` (use a venv with dependencies from `requirements.txt`).
- **Local test:** `SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local scrapy crawl airbnb_mallorca`
- **Airbnb:** disable risky-leaf StaysSearch pagination with `-a disable_risky_leaf_pagination=true` (default is enabled).
- **Deploy:** `pip install shub && shub login && shub deploy`
- Set **ZYTE_API_KEY** in project settings; configure feed in job/project settings.

## Architecture

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for design, settings, and open points (Consejo URL/fields, Airbnb pagination/fields).

For **Airbnb** behavior in production (discovery, item fields, deploy checklist), see **[docs/AIRBNB_PRODUCTION.md](docs/AIRBNB_PRODUCTION.md)**.

For **detail-page extraction** — **`max_guests`** (overview DOM → embedded JSON → limited regex; cap 16), **`latitude` / `longitude`**, registration provenance — see [docs/AIRBNB_DETAIL_EXTRACTION.md](docs/AIRBNB_DETAIL_EXTRACTION.md).
