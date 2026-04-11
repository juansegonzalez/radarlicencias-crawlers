# Base settings shared by all environments.
# Zyte API + scrapy-zyte-api; feed export; concurrency defaults.

BOT_NAME = "radarlicencias"
SPIDER_MODULES = ["radarlicencias.spiders"]
NEWSPIDER_MODULE = "radarlicencias.spiders"

# Crawl responsibly: respect robots.txt
ROBOTSTXT_OBEY = True

# Zyte API (scrapy-zyte-api)
# On Scrapy Cloud, ZYTE_API_KEY is set in project settings. Locally: use env (see local.py).
ADDONS = {
    "scrapy_zyte_api.Addon": 500,
}
# Transparent mode: all requests go through Zyte API. Spiders use zyte_api (manual params) or zyte_api_automap.
ZYTE_API_TRANSPARENT_MODE = True
# Session: disabled. Our spiders use one request per page (Consejo) or per listing (Airbnb); no session reuse.
# ZYTE_API_SESSION_ENABLED is False by default; leaving it unset avoids extra session init cost.

# Required by scrapy-zyte-api for async Zyte API client.
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Concurrency: keep effective RPM under your Zyte plan. Spiders override CONCURRENT_REQUESTS_PER_DOMAIN.
CONCURRENT_REQUESTS = 48
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0  # Throttling delegated to Zyte; AutoThrottle when enabled (per spider) resets delay for zyte-api@ slots.

# Timeout: avoid hung requests; Zyte browser requests can take 60–120s for long action sequences.
DOWNLOAD_TIMEOUT = 120

# Retries
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Pipelines (normalize text fields for cross-referencing; see pipelines.py)
# Airbnb R2 image pipeline runs after text normalization; only touches AirbnbListingItem.
ITEM_PIPELINES = {
    "radarlicencias.pipelines.RadarlicenciasPipeline": 300,
    "radarlicencias.pipelines.AirbnbImageR2Pipeline": 400,
}

# Default feed: stdout so "scrapy crawl <spider>" produces output. Override in local.py (file) or Scrapy Cloud (job).
FEEDS = {
    "stdout": {"format": "jsonlines"},
}
FEED_EXPORT_ENCODING = "utf-8"

# Logging
LOG_LEVEL = "INFO"
