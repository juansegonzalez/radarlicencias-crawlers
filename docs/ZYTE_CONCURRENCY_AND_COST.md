# Zyte API: Concurrency, Cost, and Session Notes

## Concurrency and RPM

- **CONCURRENT_REQUESTS** (base: 32) is the global cap. **CONCURRENT_REQUESTS_PER_DOMAIN** is overridden per spider (Consejo: 6, Airbnb: 12).
- **DOWNLOAD_SLOTS**: Scrapy’s default slot count is driven by concurrency. With scrapy-zyte-api, Zyte requests use a dedicated slot prefix (`zyte-api@`). No need to set DOWNLOAD_SLOTS explicitly unless you tune for a specific Zyte plan.
- **Align with Zyte RPM**: Your plan has a requests-per-minute (RPM) limit. Keep `(CONCURRENT_REQUESTS_PER_DOMAIN * 60 / avg_latency_seconds)` under that RPM. Our values (6 and 12) are conservative; increase only if you rarely see 429s.

## browserHtml vs httpResponseBody

- **Consejo**: The list table is filled by JavaScript (Handlebars). The initial HTML has only a template; the table appears after JS runs. So **browserHtml is required** for every list/page request. Using httpResponseBody would return HTML without the table.
- **Airbnb**: List/pagination use **browserHtml** (Airbnb search results are JS-rendered; HTTP returns no links). Detail uses **httpResponseBody** (registration in initial HTML). Cheapest viable mix.
- **When to use httpResponseBody**: Use it only for URLs that return the data you need in the raw HTTP response (e.g. some APIs or server-rendered pages). For this project, both spiders need browser rendering for the target pages.

## Session stability

- **ZYTE_API_SESSION_ENABLED** is not set (default False). We do **not** use Zyte’s session feature.
- Each request is independent: Consejo sends one request per page (same URL, different actions in meta); Airbnb sends one request per list page and one per listing. There is no shared browser session, so no “unnecessary new sessions” — we simply don’t use sessions.
- If you enabled sessions, you’d set `ZYTE_API_SESSION_ENABLED = True` and optionally `ZYTE_API_SESSION_PARAMS` / `ZYTE_API_SESSION_LOCATION`. For our flow (many different URLs and action sequences), session reuse would not apply in the same way; the current design is appropriate.

## Transparent mode and reactor

- **ZYTE_API_TRANSPARENT_MODE = True**: All Scrapy requests go through Zyte API unless a request has `zyte_api_automap: False` to bypass. We use transparent mode and set **zyte_api** (manual) or **zyte_api_automap** (automap) in meta so each request gets the right Zyte parameters.
- **TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"**: Required by scrapy-zyte-api for its async Zyte client. Already set in base settings.
