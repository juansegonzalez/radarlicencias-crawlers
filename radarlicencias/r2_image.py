"""Download an image from a URL, process in memory, upload WebP to Cloudflare R2."""

import io
import logging
import os
from typing import Any, Dict, Final, List, Optional, Tuple

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

logger = logging.getLogger(__name__)

_MAX_WIDTH: Final = 1000
_MIN_WIDTH: Final = 300
_MIN_HEIGHT: Final = 200

_R2_ENV = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
)

# One boto3 client per process; invalidated when resolved config fingerprint changes.
_r2_cached_client: Optional[object] = None
_r2_cached_bucket: Optional[str] = None
_r2_cached_fingerprint: Optional[str] = None


def _pick_r2_value(name: str, settings: Any) -> Tuple[str, Optional[str]]:
    """Return (value, source) where source is 'env' or 'settings' or None if empty."""
    ev = (os.environ.get(name) or "").strip()
    if ev:
        return ev, "env"
    if settings is not None:
        sv = (settings.get(name) or "").strip()
        if sv:
            return sv, "settings"
    return "", None


def r2_resolve(settings: Any = None) -> Tuple[Optional[Dict[str, str]], List[str], str]:
    """
    Merge R2 config: per key, os.environ first, then Scrapy settings.

    Returns:
        (config_dict or None if any key missing, missing_names, source_label)
        source_label: 'env' | 'scrapy_settings' | 'mixed_env_and_scrapy_settings' | 'missing'
    """
    out: Dict[str, str] = {}
    sources: List[Optional[str]] = []
    for name in _R2_ENV:
        val, src = _pick_r2_value(name, settings)
        out[name] = val
        sources.append(src)
    missing = [n for n in _R2_ENV if not out[n]]
    if missing:
        return None, missing, "missing"
    active = {s for s in sources if s}
    if active == {"env"}:
        label = "env"
    elif active == {"settings"}:
        label = "scrapy_settings"
    else:
        label = "mixed_env_and_scrapy_settings"
    return out, [], label


def r2_env_configured(settings: Any = None) -> bool:
    """True when all four R2 values resolve from env and/or settings."""
    cfg, _, _ = r2_resolve(settings)
    return cfg is not None


def r2_missing_env_names(settings: Any = None) -> List[str]:
    """Names of R2 keys still empty after env + settings merge."""
    _, missing, _ = r2_resolve(settings)
    return missing


def _config_fingerprint(cfg: Dict[str, str]) -> str:
    return "|".join(cfg[n] for n in _R2_ENV)


def _r2_client_and_bucket(settings: Any = None) -> Tuple[Optional[object], Optional[str]]:
    global _r2_cached_client, _r2_cached_bucket, _r2_cached_fingerprint

    cfg, missing, _ = r2_resolve(settings)
    if not cfg:
        return None, None
    fp = _config_fingerprint(cfg)
    if _r2_cached_client is None or fp != _r2_cached_fingerprint:
        _r2_cached_fingerprint = fp
        _r2_cached_client = boto3.client(
            "s3",
            endpoint_url=cfg["R2_ENDPOINT_URL"],
            aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
        _r2_cached_bucket = cfg["R2_BUCKET_NAME"]
    return _r2_cached_client, _r2_cached_bucket


def r2_object_exists(object_key: str, settings: Any = None) -> Optional[bool]:
    """
    True if the object exists (head_object succeeds).
    False if definitely missing (404 / NoSuchKey / NotFound).
    None if existence cannot be determined (missing config, transient or unexpected API error).
    """
    client, bucket = _r2_client_and_bucket(settings)
    if not client:
        _, missing, _ = r2_resolve(settings)
        logger.error(
            "R2 head_object skipped: missing config keys: %s",
            ", ".join(missing) if missing else "(unknown)",
        )
        return None
    try:
        client.head_object(Bucket=bucket, Key=object_key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        logger.error(
            "R2 head_object inconclusive object_key=%s: %s",
            object_key,
            e,
        )
        return None
    except BotoCoreError as e:
        logger.error(
            "R2 head_object inconclusive object_key=%s: %s",
            object_key,
            e,
        )
        return None


def download_and_upload_image_to_r2(image_url: str, object_key: str, settings: Any = None) -> bool:
    """Download image_url, resize to max width, encode WebP, upload to R2. Returns False on any failure."""
    cfg, missing, _ = r2_resolve(settings)
    if not cfg:
        logger.error("Missing R2 config: %s", ", ".join(missing))
        return False

    try:
        resp = requests.get(image_url, timeout=60)
    except requests.RequestException as e:
        logger.error("Download failed: %s", e)
        return False

    if resp.status_code != 200:
        logger.error("Download failed: HTTP %s", resp.status_code)
        return False

    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if not ctype.startswith("image/"):
        logger.error("Invalid Content-Type: %s", ctype or "(empty)")
        return False

    try:
        img = Image.open(io.BytesIO(resp.content))
        img.load()
    except Exception as e:
        logger.error("Invalid image: %s", e)
        return False

    w, h = img.size
    if w < _MIN_WIDTH or h < _MIN_HEIGHT:
        logger.error(
            "Image too small: %sx%s (minimum %sx%s)",
            w,
            h,
            _MIN_WIDTH,
            _MIN_HEIGHT,
        )
        return False

    try:
        if img.mode != "RGB":
            img = img.convert("RGB")

        if w > _MAX_WIDTH:
            new_h = max(1, int(round(h * (_MAX_WIDTH / w))))
            img = img.resize((_MAX_WIDTH, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP")
        body = buf.getvalue()
    except Exception as e:
        logger.error("Image processing failed: %s", e)
        return False

    client, bucket = _r2_client_and_bucket(settings)
    if not client or not bucket:
        logger.error("R2 client unavailable after config check")
        return False

    try:
        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=body,
            ContentType="image/webp",
        )
    except (ClientError, BotoCoreError) as e:
        logger.error("R2 upload failed: %s", e)
        return False

    return True
