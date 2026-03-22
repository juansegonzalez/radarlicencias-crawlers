# Local development overrides.
# Use with: SCRAPY_SETTINGS_MODULE=radarlicencias.settings.local
# Zyte API key: prefer environment variable ZYTE_API_KEY (never commit secrets). Optional fallback: local_config.py.

from .base import *  # noqa: F401, F403

import logging
import os

# Prefer env so keys are never in repo. Fallback to local_config only if env is empty (optional local dev).
ZYTE_API_KEY = os.environ.get("ZYTE_API_KEY", "").strip()
if not ZYTE_API_KEY:
    try:
        from radarlicencias.local_config import ZYTE_API_KEY as _key  # noqa: F401
        ZYTE_API_KEY = (_key or "").strip()
        if ZYTE_API_KEY:
            logging.getLogger(__name__).warning(
                "ZYTE_API_KEY loaded from local_config.py. Prefer export ZYTE_API_KEY=... for security."
            )
    except ImportError:
        pass

# No automatic file storage: items go to stdout (same as base). Pass -o path/to/file.jsonl to save a run.
# Scrapy Cloud stores job output in the cloud; no local data/ writes unless you use -o.
