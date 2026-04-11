#!/usr/bin/env python3
"""Minimal Cloudflare R2 upload/download smoke test (boto3 S3-compatible API)."""

import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REQUIRED_ENV = (
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
)

OBJECT_KEY = "test/hello.txt"
BODY = b"hello world"
CONTENT_TYPE = "text/plain"


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not (os.environ.get(name) or "").strip()]
    if missing:
        print(
            "Missing or empty environment variables: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "Set them in your environment or in a .env file (install python-dotenv to load .env).",
            file=sys.stderr,
        )
        return 1

    endpoint_url = os.environ["R2_ENDPOINT_URL"].strip()
    bucket = os.environ["R2_BUCKET_NAME"].strip()
    access_key = os.environ["R2_ACCESS_KEY_ID"].strip()
    secret_key = os.environ["R2_SECRET_ACCESS_KEY"].strip()

    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
    except (BotoCoreError, ValueError) as e:
        print(f"Failed to create S3 client: {e}", file=sys.stderr)
        return 1

    print("Uploading file...")
    try:
        client.put_object(
            Bucket=bucket,
            Key=OBJECT_KEY,
            Body=BODY,
            ContentType=CONTENT_TYPE,
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        print(f"Upload failed ({code}): {msg}", file=sys.stderr)
        return 1
    except BotoCoreError as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return 1

    print("Upload successful")

    print("Downloading file...")
    try:
        resp = client.get_object(Bucket=bucket, Key=OBJECT_KEY)
        raw = resp["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        print(f"Download failed ({code}): {msg}", file=sys.stderr)
        return 1
    except BotoCoreError as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return 1

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"Downloaded bytes are not valid UTF-8: {e}", file=sys.stderr)
        return 1

    print(f"Content: {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
