# Radarlicencias crawlers — Project Architecture

## Overview

Two spiders running **once a month** on **Scrapy Cloud**, with data captured for **post-processing** elsewhere.

| Spider | Target | Purpose |
|--------|--------|---------|
| **Consejo Mallorca** | El Consejo de Mallorca (government) | Tourist licenses listing |
| **Airbnb Mallorca** | Airbnb (Mallorca only) | Properties in Mallorca |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Scrapy Cloud (Zyte)                          │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │ consejo_mallorca     │    │ airbnb_mallorca      │            │
│  │ (tourist licenses)   │    │ (Mallorca listings)  │            │
│  └──────────┬───────────┘    └──────────┬───────────┘            │
│             │                           │                         │
│             └───────────┬───────────────┘                         │
│                         ▼                                         │
│              Feed export (JSON/JSONL)                              │
│              → Scrapy Cloud storage / S3 / etc.                   │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
                              ▼
                    Your post-processing pipeline
                    (outside this repo)
```

- **Crawling**: Scrapy + Zyte API (anti-ban, proxies, optional browser).
- **Scheduling**: Scrapy Cloud periodic jobs (e.g. 1st of each month).
- **Output**: Structured items → feed (e.g. JSON Lines) for your downstream pipeline.

---

## Project Structure

```
radarlicencias-crawlers/
├── scrapy.cfg                    # Scrapy Cloud / deploy config
├── PROJECT_ARCHITECTURE.md       # This file
├── README.md
├── requirements.txt
└── radarlicencias/
    ├── __init__.py
    ├── items.py                  # MallorcaLicenseItem, AirbnbListingItem
    ├── pipelines.py              # Validation, optional dedup
    ├── middlewares.py            # Custom if needed
    ├── settings/
    │   ├── __init__.py
    │   ├── base.py               # Shared settings
    │   ├── cloud.py              # Scrapy Cloud overrides
    │   └── local.py              # Local dev overrides
    └── spiders/
        ├── __init__.py
        ├── consejo_mallorca.py   # Government tourist licenses
        └── airbnb_mallorca.py    # Airbnb Mallorca only
```

- **One Scrapy project**, two spiders.
- **Shared** items and pipelines where it makes sense; spider-specific logic stays in each spider.
- **Settings**: base (Zyte, concurrency, feeds) + cloud (Scrapy Cloud) + local (dev).

---

## Spider 1: El Consejo de Mallorca (Tourist Licenses)

### Role
Crawl the government site that lists tourist licenses in Mallorca.

### Assumptions (to confirm when you share the site)
- Likely **server-rendered HTML** (government sites often are).
- List page(s) + possibly detail pages; may have pagination or sitemap.
- **Politeness**: single domain, moderate concurrency, respect robots.txt.

### Technical choices
- **Zyte API**: Prefer **HTTP mode** (`httpResponseBody`) first; switch to **browser** only if pages need JavaScript.
- **Concurrency**: Low–medium (e.g. `CONCURRENT_REQUESTS_PER_DOMAIN = 2–4`, optional `DOWNLOAD_DELAY`) to be gentle on the government server.
- **Items**: One item class (e.g. `MallorcaLicenseItem`) with fields you define (you’ll provide later).
- **Output**: One feed per run (e.g. `data/consejo_mallorca_YYYYMMDD.jsonl`).

### Open points
- Exact base URL and structure (list vs detail).
- Field list for `MallorcaLicenseItem`.
- Whether JS is required (inspect one listing page).

---

## Spider 2: Airbnb Mallorca

### Role
Crawl only **Airbnb properties in Mallorca** (e.g. via search “Mallorca” or region URLs).

### Challenges
- **Anti-bot**: Rate limits, blocks, captchas.
- **JavaScript**: Listings and details are usually rendered in the browser.
- **ToS**: Airbnb’s ToS typically restricts scraping; you’re choosing to run this for your use case.
- **Scale**: “Mallorca only” keeps volume bounded (hundreds/low thousands of listings, not the whole site).

### Technical choices
- **Zyte API**: Use **browser mode** (`browserHtml: true`) for listing and listing-detail pages so we get the rendered DOM.
- **Entry URL**: Start from a Mallorca search, e.g.  
  `https://www.airbnb.co.uk/s/Mallorca/homes` (or `.com`, same idea). Pagination and exact URL format to be confirmed when we implement.
- **Flow**:  
  1. Crawl search/listing pages.  
  2. Extract listing URLs.  
  3. Optionally crawl each listing detail page for full fields.  
  (We can also try to get enough from listing cards to avoid a detail page per listing and save cost.)
- **Sessions**: Enable Zyte **sessions** if we see blocks (same session = same IP for a short run).
- **Concurrency**: Moderate (e.g. 4–8 per domain) to reduce block risk while still finishing in a reasonable time.
- **Items**: One item class (e.g. `AirbnbListingItem`) with fields we define (id, url, title, location, price, etc.).
- **Output**: One feed per run (e.g. `data/airbnb_mallorca_YYYYMMDD.jsonl`).

### Open points
- Exact start URL(s) and pagination pattern (inspect in browser or with Zyte).
- Fields you need (from cards only vs cards + detail).
- Whether to use Zyte’s automatic extraction for product-style pages (if they support it for Airbnb).

---

## Zyte API & Scrapy Cloud Integration

- **scrapy-zyte-api**: All requests (or only those that need it) go through Zyte API.
  - **Consejo**: Prefer **automap** or **transparent** with default HTTP; override to `browserHtml` only if we find JS-only content.
  - **Airbnb**: Use **browserHtml** for listing/detail requests (via `zyte_api_automap` or `zyte_api` in `meta`).
- **Auth**: On Scrapy Cloud, `ZYTE_API_KEY` is usually set by the platform; locally, set in env or `settings`.
- **Cost**: HTTP requests are cheaper; browser requests cost more. Use browser only where necessary (Airbnb; Consejo only if needed).

---

## Scheduling (Scrapy Cloud)

- **Periodic jobs**: Create one periodic job per spider, e.g. “Run on the 1st of every month” (cron-style).
- **Docs**: [Scheduling Periodic Jobs (Zyte)](https://support.zyte.com/support/solutions/articles/22000200419-scheduling-periodic-jobs).
- **Output**: Configure job to write to Scrapy Cloud storage or to your cloud (e.g. S3). Your post-processing runs after each job (e.g. triggered by job completion or a monthly pipeline).

---

## Data Flow

1. **Crawl** (Scrapy Cloud, monthly):  
   `consejo_mallorca` and `airbnb_mallorca` produce items.
2. **Export**: Items written to feed (JSON/JSONL) in cloud storage or Scrapy Cloud.
3. **Post-processing** (your code, outside this repo):  
   You consume the feed(s), validate, store in DB, compare with previous runs, etc.

So the crawlers are **stateless** and **idempotent**: each run is a full snapshot for that month; diffing and history are in your pipeline.

---

## Settings Strategy

| Concern | Base (settings/base.py) | Consejo spider | Airbnb spider |
|--------|--------------------------|----------------|----------------|
| Zyte API | scrapy-zyte-api addon, key from env | — | — |
| Concurrency per domain | 8 | 2–4 | 4–8 |
| Download delay | 0 (Zyte handles throttling) | Optional small delay | 0 |
| Browser (Zyte) | Off (HTTP default) | Off | On for listing/detail |
| Retries | On (Scrapy + Zyte) | On | On |
| Feed export | Path/format for Scrapy Cloud | Per-spider filename | Per-spider filename |

---

## Next Steps

1. **Consejo Mallorca**: You share the base URL and (if possible) the list of fields you want → we define `MallorcaLicenseItem` and the parsing logic.
2. **Airbnb Mallorca**: We fix start URL(s) and pagination, then implement listing (and optionally detail) parsing and `AirbnbListingItem`.
3. **Scrapy Cloud**: Create project, connect repo or deploy via `shub`, set `ZYTE_API_KEY`, configure feeds and periodic jobs.
4. **Post-processing**: You wire job outputs into your pipeline (we only produce the feeds).

If you’re happy with this, next we can create the Scrapy project skeleton and placeholder spiders so you can run them locally and on Scrapy Cloud once the URLs and fields are set.
