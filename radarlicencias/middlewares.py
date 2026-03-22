# Radarlicencias crawlers - Middlewares
# Zyte API is configured via scrapy-zyte-api (see settings).
# Add custom downloader or spider middlewares here if needed.

from scrapy import signals
from scrapy.http import HtmlResponse


class RadarlicenciasDownloaderMiddleware:
    """Placeholder for custom downloader middleware."""

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls()
        crawler.signals.connect(mw.spider_opened, signal=signals.spider_opened)
        return mw

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s", spider.name)

    def process_request(self, request, spider):
        return None

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        pass
