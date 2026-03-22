# Scrapy Cloud overrides.
# Use with: SCRAPY_SETTINGS_MODULE=radarlicencias.settings.cloud
# Or configure feeds/job-specific settings in Scrapy Cloud UI.

from .base import *  # noqa: F401, F403

# Scrapy Cloud often sets feed URI via job configuration.
# Example: feed URI to project storage or S3.
# FEEDS = {
#     "s3://bucket/%(name)s_%(time)s.jsonl": {"format": "jsonlines"},
# }
