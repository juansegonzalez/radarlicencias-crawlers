# Scrapy + Zyte API Architecture Audit

**Auditor role:** Senior Scrapy + Zyte API architect / code reviewer  
**Scope:** Full codebase audit for efficiency, robustness, scalability, cost-effectiveness.  
**Evidence:** All findings are tied to specific files and line references.

---

## A. Executive Summary

### Top 10 Biggest Weaknesses

1. **No tests** — Zero unit tests, no parser tests, no fixtures. Every selector/change is a production gamble.
2. **Secrets in repo risk** — `local_config.py` is gitignored but `local_config.py.example` documents loading; if anyone commits `local_config.py` or logs request URLs with tokens, keys leak. No env-only enforcement.
3. **Consejo: every page is a full browser session** — Page 300 = load page, click Buscar, click Siguiente 299 times. One Zyte browser request per page. Maximum cost and latency; no HTTP fallback even for list content that might be fetchable.
4. **Airbnb: no errbacks** — Failed or banned detail requests are only retried by Scrapy; no logging of final failure URL, no re-queue, no distinction between 403/429 and 5xx. You lose items silently.
5. **Monolithic spiders** — 400+ lines in `airbnb_mallorca.py` (extraction, URL building, dedup, loading municipalities, regexes). No shared “list + detail” base, no extractors module. Adding a third spider will copy-paste again.
6. **Pipeline normalizes every string including URLs** — `RadarlicenciasPipeline` runs `_normalize_string` on all fields. For `url` and `ficha_url` this is redundant and risky (if a URL ever contained spaces, `" ".join(s.split())` would alter it). No field allowlist.
7. **No DOWNLOAD_TIMEOUT** — Relying on default 180s. Zyte browser requests can hang; no explicit timeout or errback means long stalls and no clear failure signal.
8. **Duplicate filtering is ad hoc** — Airbnb uses in-memory `_seen_listing_keys`; no persistence. A crash or stop loses state; re-run re-scrapes all details. No Scrapy job persistence (e.g. JOBDIR) documented or enforced.
9. **Default settings module has empty FEEDS** — `radarlicencias.settings` (package) pulls from `base.py` where `FEEDS = {}`. Running `scrapy crawl` without `-o` or `SCRAPY_SETTINGS_MODULE=...local` produces no output. Easy to “run” and get nothing.
10. **License pattern loading swallows errors** — `_get_license_code()` uses bare `except Exception: pass`. If `license_patterns.py` is corrupt or has a syntax error, you silently fall back to built-in; no log, no alert.

### Top 10 Highest-Impact Improvements

1. Add **parser tests** with HTML fixtures (Consejo table row, Airbnb detail snippet) so selectors and regexes are regression-tested without Zyte.
2. **Never load secrets from repo files** — Use only `os.environ.get("ZYTE_API_KEY")` in code; document that Scrapy Cloud sets it. Remove or minimize `local_config.py` import so a mistaken commit cannot leak keys.
3. **Add errbacks** to critical requests (Airbnb detail, Consejo list retry); log and optionally re-queue or write failed URLs to a file for re-run.
4. **Refactor extractors** — Move license regexes, location extraction, and Consejo row parsing into `radarlicencias/extractors/` (or similar) and call from spiders. Enables testing and reuse.
5. **Pipeline: do not normalize URL fields** — Apply `_normalize_string` only to fields that are text for matching (e.g. `signature`, `address`, `municipality`, `registration_number`). Skip `url`, `ficha_url`, `scraped_at`, `listing_id` where normalization is wrong or pointless.
6. **Set DOWNLOAD_TIMEOUT** in base (e.g. 90–120s) and document that Zyte browser requests may need higher; consider per-request timeout in meta for very long actions.
7. **Document and recommend JOBDIR** for long Airbnb runs so that interrupt/resume preserves `_seen_listing_keys` (via request fingerprinting and scheduler persistence).
8. **Consejo: evaluate HTTP for list** — If the list table is ever returned in a non-JS response (e.g. API or server render), use `httpResponseBody` for list and keep browser only for pages that truly need it. Measure and document.
9. **Explicit default FEEDS** — In `base.py`, set a safe default (e.g. `stdout` or a clearly named path) or fail fast if FEEDS is empty and no `-o` is given, so “no output” is obvious.
10. **Log and optionally raise** when `license_patterns.py` fails to load — At least `logger.warning("...")` so you know you are on built-in patterns; optionally make missing/corrupt file a startup error in production.

---

## B. Detailed Findings

### B.1 Architecture & structure

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 1 | Logic lives in spiders, not in shared layers | High | Adding a third spider will duplicate extraction, URL building, and Zyte meta. Hard to test and change. | `airbnb_mallorca.py` holds ~55 lines of regex patterns, location normalization, license loading, URL building, and 160+ lines of municipality list. Consejo has action building and row parsing inline. | Introduce `radarlicencias/extractors/airbnb.py` and `consejo.py` (or a single `parsers` module). Spiders call `extract_listing_item(response, municipality)`, `parse_consejo_row(row, response)`. Move `_search_url_for_municipality`, `_listing_key`, `_normalize_registration` into a shared or extractor module. | Maintainability, testability, reuse. |
| 2 | No base spider or mixins | Medium | Common behavior (Zyte meta, error handling, logging) is repeated. | Both spiders define their own `custom_settings`, pass `zyte_api` / `zyte_api_automap` in meta, and handle `response.status != 200` in callbacks. | Add `radarlicencias/spiders/base.py` with a `ZyteBrowserMixin` or base class that sets common Zyte defaults and optional `errback` for failed requests. Spiders inherit and override only what’s different. | Less duplication, consistent behavior. |
| 3 | 53 municipalities hardcoded in spider | Medium | List can get out of sync with `mallorca_municipalities.txt`; bloats spider file. | `MALLORCA_MUNICIPALITIES` is a 53-element tuple in `airbnb_mallorca.py` (lines 109–165). File also loads from `_MUNICIPALITIES_FILE`. | Keep a single source of truth: either only the file (and fail if missing) or only the constant in a `data` module. Remove the other. Consider loading from a small Python module generated from the file so Scrapy Cloud always has it. | Single source of truth, smaller spider. |
| 4 | `scrapy.cfg` points to package; default has no FEEDS | High | Running `scrapy crawl airbnb_mallorca` without `SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local` uses `radarlicencias.settings` (base). Base has `FEEDS = {}`, so no output. | `radarlicencias/settings/__init__.py` does `from .base import *`; `base.py` has `FEEDS = {}`. | In base, either set a default feed (e.g. `"stdout"` with format jsonlines) or add a startup check that warns/fails when FEEDS is empty and no `-o` is provided. Document in README that local runs must use `radarlicencias.settings.local` or `-o`. | Prevents “run succeeded but no file” confusion. |
| 5 | setup.py and scrapinghub.yml both define project | Low | Minor inconsistency. | `setup.py`: `name='project'`, `entry_points = {'scrapy': ['settings = radarlicencias.settings']}`. `scrapinghub.yml`: `project: 853585`. | Use a consistent project name (e.g. `radarlicencias`) in setup.py; keep scrapinghub.yml for deploy. | Clarity. |

### B.2 Scrapy fundamentals

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 6 | No errbacks on requests | High | When a request fails after retries, you get no callback and no structured handling. You don’t log which URL failed or why. | `airbnb_mallorca.py` and `consejo_mallorca.py` never pass `errback` to `scrapy.Request`. | Add `errback=self.handle_request_error` (or similar) to detail and list requests. In the errback, log `request.url`, `failure`, and optionally write to a “failed_urls.txt” or re-queue with different meta. | Observability, retry/recovery, debugging. |
| 7 | Pagination strategy is correct but expensive (Consejo) | High | Each page is a separate Zyte browser request with N clicks. Page 300 = one request with 299 “Siguiente” clicks. | `_actions_for_page(next_page, ...)` builds a long action list; one request per page. No use of direct URL if the site ever supports it. | Keep current approach if the site has no URL-based pagination. Document cost (one browser request per page). Consider batching (e.g. request pages 1–5 in parallel with different action lengths) to reduce total time; measure Zyte concurrency limits. | Cost and latency transparency; possible speedup. |
| 8 | Duplicate filtering not persistent (Airbnb) | High | `_seen_listing_keys` is in-memory. If the spider stops or crashes, the set is lost. Re-run re-scrapes all listing details. | `start_requests` sets `self._seen_listing_keys = set()`; no JOBDIR or disk-backed set. | Document and recommend `scrapy crawl airbnb_mallorca -s JOBDIR=data/jobs/airbnb` so the scheduler persists. Note: dedup is by URL (listing id); with JOBDIR, request fingerprints prevent re-scheduling the same URL. The in-memory set still resets on restart, so consider persisting seen keys to a file and loading on start, or rely on Scrapy’s dupefilter for URLs (but then you must not use `dont_filter=True` for details, or use a custom dupefilter that knows listing id). | Resume safety, no duplicate detail requests after resume. |
| 9 | Retry logic only in Scrapy defaults | Medium | You rely on RETRY_TIMES and RETRY_HTTP_CODES. No custom retry for “empty body” or “blocked” (e.g. 403 with captcha page). | Base has `RETRY_TIMES = 3`, `RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]`. No retry on 403. No middleware that detects “blocked” content. | For production, consider a small middleware or errback that detects known block/captcha patterns in response body and either retries with different Zyte params or logs and drops. Keep 403 out of RETRY_HTTP_CODES unless you have evidence retrying helps. | Fewer silent blocks, clearer failures. |
| 10 | Concurrency and AutoThrottle are reasonable but undocumented | Low | Future changes might break tuning. | Consejo: 6 per domain, AutoThrottle 6/8. Airbnb: 12 per domain, AutoThrottle 12/16. No comment on why these numbers. | Add one-line comments in custom_settings: “Zyte rotates IPs; 6 concurrent pages for Consejo to avoid overloading their server”; “12 for Airbnb to maximize throughput without 429.” | Maintainability. |

### B.3 Zyte API integration

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 11 | Every Consejo request uses browserHtml | High | List pages might be server-rendered or have a lighter API. Using browser for everything maximizes cost. | All Consejo requests pass `"browserHtml": True` and actions. There is no attempt to use `httpResponseBody` for the list. | Test once: request START_URL with only `httpResponseBody` (no actions). If the table is in the response, use HTTP for page 1 and optionally more; use browser only if needed for pagination. If table is always JS-rendered, document “Consejo requires browserHtml for table” and keep as is. | Potential cost reduction. |
| 12 | Airbnb list and detail both use browser when not use_http | Medium | List pages might be usable with HTTP in some regions; you only try when user passes `use_http=1`. | Default path uses `browserHtml` for list and detail. `use_http=1` is documented as “often blocked.” | Keep default as browser. Optionally add a “list_http_only” mode: HTTP for list (cheap), browser for detail (needed for “Show more”). Test and document success rate. | Cost vs. completeness trade-off. |
| 13 | No explicit DOWNLOAD_TIMEOUT | Medium | Zyte browser requests can take a long time. Default 180s may be too high or too low; unset is implicit. | base.py does not set DOWNLOAD_TIMEOUT. | Set `DOWNLOAD_TIMEOUT = 120` in base (or 90). For very long action sequences (Consejo page 300), consider requesting a higher timeout in request meta if the middleware supports it. Document. | Predictable timeouts, fewer hangs. |
| 14 | zyte_api_automap vs zyte_api usage | Low | Consistency and correctness. | List requests use `zyte_api_automap`; detail requests use `zyte_api` with explicit `browserHtml` and `actions`. This matches scrapy-zyte-api’s pattern (automap for convention, zyte_api for override). | No change needed. Add a short comment in spider: “List: automap (browserHtml). Detail: explicit zyte_api with actions for Show more.” | Clarity. |
| 15 | Session and fingerprinting | Low | Scrapy-Zyte-API uses custom fingerprinting so same URL with different actions is not deduplicated. | You use `dont_filter=True` on Consejo pagination and Airbnb detail so duplicate filter does not drop them. Custom fingerprinting (ScrapyZyteAPIRequestFingerprinter) is in use via addon. | Ensure you don’t rely on default fingerprinting for “same URL, different meta” — the addon should take meta into account. No code change if already correct. | Correct dedup. |

### B.4 Data extraction quality

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 16 | Consejo column order is positional | High | If the site adds/removes a column, indices 0,1,4,5 break silently. | `texts[0], texts[1], texts[4], texts[5]` for signature, commercial_name, municipality, address. | Prefer thead-based mapping: parse `<th>` texts, find column index by label (e.g. “Signatura”, “Municipio”), then use indices for that run. Or at least assert len(texts) and log when the structure changes. | Robustness to site changes. |
| 17 | Airbnb location: broad XPath then filter | Medium | `//*[contains(., ', Spain')]` can match huge nodes; getall() returns many candidates. | `_extract_location` tries several xpaths and iterates parts. No limit on how many nodes are considered. | Restrict to likely containers (e.g. `//span`, `//a`, `//p`) and/or use more specific selectors (e.g. section with “Location” or map container). Cap the number of candidates (e.g. first 20). | Performance and stability. |
| 18 | No validation or schema for items | Medium | Malformed or missing required fields are not caught before export. | Items define fields but pipelines only normalize strings. No check that `signature` or `registration_number` is non-empty when expected. | Add a validation pipeline (e.g. `RequiredFieldsPipeline`) that logs or drops items missing required fields. Optionally use ItemAdapter and a small schema (e.g. “url must be present and look like a URL”). | Data quality for downstream. |
| 19 | License pattern loading swallows errors | High | If `license_patterns.py` is broken, you silently use built-in; no visibility. | `_get_license_code()` has `except Exception: pass` and returns `_BUILTIN_LICENSE_CODE`. | Catch specific exceptions (e.g. FileNotFoundError, SyntaxError). Log warning with message: “Could not load license_patterns.py: …; using built-in.” Optionally in production, fail if file exists but fails to load. | Observability, correctness. |
| 20 | Regexes for license are in spider | Medium | Hard to test and reuse. | All REGISTRATION_* and _normalize_registration live in airbnb_mallorca.py. | Move to `radarlicencias/extractors/license.py` (or similar). Spider imports and calls `extract_registration_number(text)`. Enables unit tests with snippets. | Testability, reuse. |

### B.5 Reliability and failure handling

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 21 | No errbacks (see B.2 #6) | High | Already in top 10. | — | — | — |
| 22 | 4xx responses only logged, no retry or file | Medium | 403/404 on a listing URL: you log and return; the item is never produced. No list of failed URLs. | `parse_detail` and `parse_list` do `if response.status != 200: self.logger.warning(...); return`. | In errback (and optionally in callback), append failed URL to a set or file (e.g. `self._failed_urls` and write to `data/failed_airbnb_YYYYMMDD.txt` in spider_closed). | Recovery, re-run list. |
| 23 | Consejo 0-row retry is good; no retry for partial rows | Low | Sometimes a page might return 30 rows instead of 50 (transient). | You retry when 0 rows. You don’t retry when 0 < len(rows) < 50 on a non-last page. | Optional: if page_number > 1 and 0 < len(rows) < ROWS_PER_PAGE and next_button present, schedule a retry for the same page (with page_retry) to try to get a full page. Document as best-effort. | Completeness. |
| 24 | Logging is INFO; no request_id or job_id | Low | In Scrapy Cloud, correlating logs with requests/jobs is harder. | Standard Scrapy logging. No custom log format with request URL or job id. | Add a logging filter or middleware that adds request URL (or a short hash) to the log record for failed requests. Optional: log item count periodically (e.g. every 100 items). | Debugging in production. |

### B.6 Performance and efficiency

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|---------------|---------------|--------|
| 25 | Airbnb: 53 municipalities × N pages each; all list URLs are browser | High | List pages are likely cheaper than detail (no “Show more” actions). You’re already using browser for list. | Every list request uses browserHtml. Detail uses browserHtml + actions. No separation of “cheapest possible list” vs “full browser for detail.” | If you introduce list_http (see #12), you reduce list cost. Otherwise, keep as is but document “one browser request per list page + one per unique listing.” | Cost clarity; optional savings. |
| 26 | Dedup is in-memory (see B.2 #8) | High | Already in top 10. | — | — | — |
| 27 | No batching of Consejo pages | Medium | You could request multiple pages in parallel (different action lengths). Currently you rely on CONCURRENT_REQUESTS_PER_DOMAIN and scheduler. | Each request is one page. Scheduler already runs several in parallel (6). So you do have parallelism. Batching would mean one request returning multiple pages — Zyte doesn’t support that. So no change. | Document that “Consejo parallelism = 6 concurrent page requests.” | Clarity. |
| 28 | Pipeline runs on every item | Low | Normalizing all string fields is O(fields) per item; trivial. | RadarlicenciasPipeline iterates item.fields and normalizes. No heavy work. | Only skip URL-like fields (see B.7) to avoid any risk. | Correctness, minor perf. |

### B.7 Item modeling and pipelines

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 29 | Pipeline normalizes URL fields | High | `_normalize_string` does `" ".join(s.strip().split())`. For URLs this usually changes nothing, but if a URL had a space it would be altered. Also redundant. | `RadarlicenciasPipeline` applies to all string fields: `url`, `ficha_url`, `scraped_at`, `listing_id`, etc. | Only normalize fields that are used for matching: e.g. `signature`, `commercial_name`, `municipality`, `address`, `location`, `registration_number`. Skip `url`, `ficha_url`, `listing_id`, `scraped_at`. E.g. `TEXT_FIELDS_FOR_NORMALIZE = {"signature", "commercial_name", "municipality", "address", "location", "registration_number"}` and only process those. | Safety, clarity. |
| 30 | No ItemLoader or input processors | Medium | Manual get/default and string ops in spiders. Loaders would give you a single place for cleanup and composability. | Spiders build items by hand (e.g. `registration_number or ""`, `_normalize_registration(...)`). | Optional: introduce ItemLoader for Airbnb and Consejo with input processors (MapCompose, strip, take_first). Use for new spiders. Low priority if team is small. | Consistency, less ad hoc code. |
| 31 | scraped_at is set in spider | Low | Fine; could be middleware. | `datetime.now(timezone.utc).isoformat()` in parse_detail. | No change, or move to a pipeline that adds scraped_at if missing. | Minor. |

### B.8 Configuration and settings

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 32 | ZYTE_API_KEY from local_config.py | Critical | If local_config.py is ever committed or copied into a image, the key is in the repo. | `local.py` does `from radarlicencias.local_config import ZYTE_API_KEY` with ImportError fallback to env. | Do not import from local_config in code that is committed. Use only `os.environ.get("ZYTE_API_KEY")` in settings. Document: “Set ZYTE_API_KEY in your environment or in Scrapy Cloud.” Provide a `.env.example` with `ZYTE_API_KEY=` and use python-dotenv in local.py if you want file-based local dev without committing secrets. | Security. |
| 33 | cloud.py is minimal | Low | Scrapy Cloud often needs feed and ZYTE_API_KEY. | cloud.py only imports base and comments FEEDS. | Document in README/DEPLOY that ZYTE_API_KEY must be set in Scrapy Cloud project settings and feed configured in job. No code change required. | Operability. |
| 34 | No REQUEST_FINGERPRINTER_CLASS in base | Low | scrapy-zyte-api may set it. | base.py doesn’t set it. Spiders don’t set it. Addon likely injects ScrapyZyteAPIRequestFingerprinter. | Verify in docs; if addon sets it, no change. If not, set it in base so same URL + different meta are not deduplicated. | Correct fingerprinting. |

### B.9 Testing and QA

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 35 | Zero tests | Critical | Every change can break parsing or extraction; no regression signal. | No tests/ directory, no pytest, no fixtures. | Add `tests/` with `test_airbnb_parsing.py` and `test_consejo_parsing.py`. Use HTML fixtures (saved snippets from real responses, anonymized). Test: parse_detail with a fixture returns expected item fields; parse_list extracts correct number of links; license regex matches/doesn’t match given strings. Run with `pytest tests/` without Zyte. | Regression protection, safe refactors. |
| 36 | No way to run spiders without Zyte | Medium | You can’t do a “dry run” or test callbacks with mock responses without hitting the API. | All requests go through Zyte (transparent mode). | Add a test that builds a Scrapy response from a fixture file and calls parse_list/parse_detail. No network. Optionally a setting to bypass Zyte for testing (e.g. use a custom download handler that returns fixture). | Cost-free testing. |
| 37 | Fixtures and contracts | Medium | Selectors are not documented as contracts. | No “expected selectors” doc or test that asserts presence of key elements in a fixture. | For each spider, add one “contract” test: load fixture HTML, assert that the main selector (e.g. table.lista-elementos tbody tr, a[href*="/rooms/"]) returns at least one node. | Early detection of site changes. |

### B.10 Production readiness

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 38 | No idempotency or incremental strategy | Medium | Re-running from scratch every time. No “only new/changed” mode. | Both spiders are full crawls. No timestamp or version in output for downstream to deduplicate. | Add scraped_at to all items (you have it for Airbnb). For Consejo, add scraped_at in pipeline or spider. Downstream can use (signature/url, scraped_at) to detect changes. Optional: document “full crawl monthly; downstream handles dedup.” | Data lifecycle. |
| 39 | Resume and JOBDIR (see B.2 #8) | High | Already covered. | — | — | — |
| 40 | Monitoring and alerting | Medium | No built-in way to alert on “zero items” or “high failure rate.” | Scrapy logs stats at the end. No hook that fails the job or sends a message when item_scraped_count is 0 or below a threshold. | In spider_closed, check spider.crawler.stats.get("item_scraped_count", 0). If 0 (or below threshold), log error and optionally raise or send to a webhook. Document how to wire this in Scrapy Cloud. | Operational safety. |

### B.11 Code quality

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 41 | Deprecated start_requests | Low | Scrapy 2.13+ prefers start() (async). | Both spiders define start_requests(). Warning is logged. | When you’re ready, migrate to async def start(self) and yield from super().start() or yield requests. Low priority. | Future compatibility. |
| 42 | Dead code in middlewares | Low | RadarlicenciasDownloaderMiddleware is a no-op and may not be enabled. | middlewares.py has a placeholder that process_request returns None, process_response returns response. Not referenced in settings. | Remove the middleware from the file or add it to DOWNLOADER_MIDDLEWARES if you plan to use it. Otherwise delete. | Clarity. |
| 43 | Type hints and docstrings | Low | Some functions have no types or docs. | _get_license_code, _normalize_registration, _actions_for_page have minimal or no type hints. | Add return types and one-line docstrings for public helpers. | Maintainability. |
| 44 | Magic numbers | Low | 53, 50, 20, 1.5, 8, etc. | ROWS_PER_PAGE=50, RESULTS_PER_PAGE=20, timeouts 1.5 and 8. | Most are named constants. Good. Document why 50 and 20 (site page sizes). | Clarity. |

### B.12 Security and compliance

| # | Title | Severity | Why it matters | What is wrong | Concrete fix | Impact |
|---|--------|----------|----------------|----------------|---------------|--------|
| 45 | Secrets (see B.8 #32) | Critical | Already in top 10. | — | — | — |
| 46 | Logging of URLs | Medium | If you log full URLs, they can contain tokens or session ids. | Spiders log response.url and request.url in warnings. Usually safe. | Avoid logging query strings that might contain tokens. Strip or redact in log formatter if needed. | Safety. |
| 47 | robots.txt | Low | Airbnb spider sets ROBOTSTXT_OBEY = False. | You’ve chosen to ignore robots for Airbnb (required for scraping). | Document the decision and that you’re not fetching more than needed (e.g. one request per listing). | Compliance transparency. |

---

## C. Architecture Recommendations

### Refactor now

1. **Pipeline:** Only normalize text fields used for matching; skip `url`, `ficha_url`, `listing_id`, `scraped_at`.
2. **Secrets:** Stop loading ZYTE_API_KEY from `local_config.py` in committed code; use env only and document.
3. **Extractors:** Move license regexes and _normalize_registration to a module; have spider call a single `extract_registration_number(text)`. Same idea for Consejo row parsing (function that takes row + response, returns dict or item).
4. **Errbacks:** Add one errback for Airbnb detail and Consejo list; log failure and optionally write failed URLs to a file.
5. **License loading:** Log a warning when license_patterns.py fails to load; do not silently fall back.

### Leave alone for now

1. **Consejo “one request per page” with long actions** — No simpler option if the site has no URL pagination. Document cost.
2. **Airbnb browser for list and detail** — Required for JS and “Show more.” Keep use_http as an optional experiment.
3. **Single pipeline** — One pipeline is enough; just fix which fields it normalizes.
4. **custom_settings in spiders** — Fine; no need to push everything into a “spider config” layer yet.

### Will become a problem later if ignored

1. **No tests** — As you add spiders or change selectors, regressions will ship.
2. **In-memory dedup** — At 15k+ listings, long runs will be interrupted; without JOBDIR or persistent seen set, re-runs re-fetch everything.
3. **Positional column parsing (Consejo)** — One site redesign and all indices break; thead-based or defensive checks are needed.
4. **Monolithic spider files** — Third spider will copy-paste again; extractors and shared helpers pay off quickly.

---

## D. Scrapy + Zyte API Efficiency Recommendations

### Reduce Zyte API cost

- **Consejo:** Test whether the first page (or any page) can be fetched with `httpResponseBody` only (no browser). If yes, use HTTP for list and browser only when you need to click (e.g. pagination). If no, document “all requests require browser.”
- **Airbnb:** You already deduplicate detail requests by listing id. Keep it. Optional: try `httpResponseBody` for list pages in a test run; if success rate is acceptable for your region, offer “list_http” mode.
- **Avoid redundant requests:** Ensure you never schedule the same (url, meta) twice. Consejo uses same URL with different page_number in meta; fingerprinting must include that. Airbnb uses dont_filter=True for details; dedup is manual. Both are correct if the addon fingerprints by (url, zyte_api params).
- **Shorten timeouts where safe:** waitForSelector 8s is reasonable; 1.5s wait after Siguiente might be reduced to 1s after testing. Fewer seconds per request = lower cost per request if Zyte bills by time.

### Improve throughput

- **Consejo:** You already run 6 concurrent requests (6 pages at a time). Do not increase much without testing; the site may throttle.
- **Airbnb:** 12 concurrent is reasonable. AutoThrottle will back off on 429. Consider 16 target concurrency if you rarely see 429.
- **Request scheduling:** Both spiders yield requests as they parse; no artificial batching. Good. Ensure the scheduler is not starved (e.g. don’t block in callbacks).

### Reduce failures and bans

- **Errbacks and logging:** So you know which URLs failed (network, 4xx, timeout) and can re-run or adjust.
- **Retry:** Keep 429 in RETRY_HTTP_CODES; consider increasing RETRY_TIMES to 4 for Zyte requests if timeouts are frequent.
- **Timeout:** Set DOWNLOAD_TIMEOUT so hung requests eventually fail and retry or errback.

### Improve extraction quality

- **Consejo:** Use thead to derive column indices; add a sanity check (e.g. signature matches known pattern).
- **Airbnb:** Validate registration_number format (e.g. must match LICENSE_CODE) before yielding; log when fallback pattern is used.
- **Both:** Add a validation pipeline that drops or flags items with missing required fields.

---

## E. Code Change Examples

### E.1 Pipeline: do not normalize URL fields

```python
# radarlicencias/pipelines.py

# Fields that are free text for matching; normalize these only.
TEXT_FIELDS_FOR_NORMALIZE = frozenset({
    "signature", "commercial_name", "municipality", "address",
    "location", "registration_number",
})

def _normalize_string(value):
    if value is None or not isinstance(value, str):
        return value
    return " ".join(value.strip().split())

class RadarlicenciasPipeline:
    def process_item(self, item, spider=None):
        if item is None:
            return item
        for key in item.fields:
            if key not in TEXT_FIELDS_FOR_NORMALIZE:
                continue
            if key in item and item[key] and isinstance(item[key], str):
                item[key] = _normalize_string(item[key])
        return item
```

### E.2 License loading: log warning on failure

```python
# In airbnb_mallorca.py, _get_license_code()

def _get_license_code() -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "license_patterns.py")
    if os.path.isfile(path):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("license_patterns", path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return getattr(mod, "LICENSE_CODE", _BUILTIN_LICENSE_CODE)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Could not load license_patterns.py: %s; using built-in patterns.", e
            )
    return _BUILTIN_LICENSE_CODE
```

### E.3 Errback for Airbnb detail requests

```python
# In airbnb_mallorca.py spider

def handle_detail_error(self, failure, request=None):
    url = request.url if request else "unknown"
    self.logger.error("Detail request failed: url=%s reason=%s", url, failure.getTraceback())
    # Optionally: append url to self._failed_urls and write in spider_closed

# In parse_list, when yielding detail request:
yield scrapy.Request(
    detail_url,
    callback=self.parse_detail,
    errback=self.handle_detail_error,
    dont_filter=True,
    meta={...},
)
```

### E.4 Base settings: default FEEDS or warn

```python
# radarlicencias/settings/base.py

FEEDS = {}
# Optional: fail fast when no -o and no feed
# from scrapy.utils.project import get_project_settings
# in a startup hook, if FEEDS is empty and 'output' not in sys.argv, log critical and exit
```

Or set a safe default:

```python
FEEDS = {
    "stdout": {"format": "jsonlines"},  # so `scrapy crawl X` prints items
}
# local.py overrides with file path
```

---

## F. Final Score

| Area | Score (1–10) | Notes |
|------|----------------|------|
| **Architecture** | 4 | Two spiders, no shared extractors or base, logic in the wrong place. Settings split (base/cloud/local) is good. |
| **Efficiency** | 5 | Dedup on Airbnb is good. Consejo one-browser-request-per-page is costly but likely unavoidable. No HTTP where it might work. |
| **Reliability** | 4 | No errbacks, no persistent dedup, no tests. Retries and empty-page retry (Consejo) help. |
| **Cost control** | 5 | You’re aware of cost (browser vs HTTP). No measurement or logging of “requests by type.” Pipeline and extraction could be cheaper only with HTTP where possible. |
| **Maintainability** | 4 | Monolithic spiders, no tests, magic numbers documented only in comments. Refactors are risky. |
| **Production readiness** | 4 | Runs on Scrapy Cloud and locally, but no tests, no resume story, no alerting, secrets handling is risky. |

**Overall:** **4.2 / 10** — Works for a two-spider, monthly full crawl, but is brittle, untested, and will not scale well in code or operations without the improvements above.

---

*End of audit.*
