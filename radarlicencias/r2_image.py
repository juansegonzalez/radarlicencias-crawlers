"""Download an image from a URL, process in memory, upload WebP to Cloudflare R2."""

import io
import logging
import os
from typing import Final, List, Optional, Tuple

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

logger = logging.getLogger(__name__)

_MAX_WIDTH: Final = 1000

_R2_ENV = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
)


def _missing_r2_env() -> List[str]:
    return [name for name in _R2_ENV if not (os.environ.get(name) or "").strip()]


def r2_env_configured() -> bool:
    """True when all R2-related environment variables are set."""
    return not _missing_r2_env()


def _r2_client_and_bucket() -> Tuple[Optional[object], Optional[str]]:
    """Return (boto3 S3 client, bucket name) or (None, None) if env is incomplete."""
    if not r2_env_configured():
        return None, None
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"].strip(),
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"].strip(),
        region_name="auto",
    )
    bucket = os.environ["R2_BUCKET_NAME"].strip()
    return client, bucket


def r2_object_exists(object_key: str) -> bool:
    """
    Return True if the object exists in R2 (head_object succeeds).
    On missing credentials, not found, or API error: log when appropriate and return False.
    """
    client, bucket = _r2_client_and_bucket()
    if not client:
        logger.error(
            "R2 head_object skipped: missing env vars: %s",
            ", ".join(_missing_r2_env()),
        )
        return False
    try:
        client.head_object(Bucket=bucket, Key=object_key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        logger.error(
            "R2 head_object failed listing_id_key=%s: %s",
            object_key,
            e,
        )
        return False
    except BotoCoreError as e:
        logger.error(
            "R2 head_object failed listing_id_key=%s: %s",
            object_key,
            e,
        )
        return False


def download_and_upload_image_to_r2(image_url: str, object_key: str) -> bool:
    """Download image_url, resize to max width, encode WebP, upload to R2. Returns False on any failure."""
    missing = _missing_r2_env()
    if missing:
        logger.error("Missing environment variable(s): %s", ", ".join(missing))
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

    try:
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if w > _MAX_WIDTH:
            new_h = max(1, int(round(h * (_MAX_WIDTH / w))))
            img = img.resize((_MAX_WIDTH, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="WEBP")
        body = buf.getvalue()
    except Exception as e:
        logger.error("Image processing failed: %s", e)
        return False

    client, bucket = _r2_client_and_bucket()
    if not client or not bucket:
        logger.error("R2 client unavailable after env check")
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
