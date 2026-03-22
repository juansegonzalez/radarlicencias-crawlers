# Settings package: base, cloud (Scrapy Cloud), local (dev).
# This is loaded as radarlicencias.settings (scrapy.cfg). Do not add radarlicencias/settings.py
# or it will shadow this package. Use SCRAPY_SETTINGS_MODULE=radarlicencias.settings.cloud or
# radarlicencias.settings.local for env-specific overrides.
from .base import *  # noqa: F401, F403
