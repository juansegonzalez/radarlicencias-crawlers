#!/usr/bin/env python3
"""
Scan JSONL (or line-delimited JSON) exports for picture URLs that match banned CDN patterns.

Use this to find listings whose stored picture_url (or mirrored R2 URL) should be re-crawled
after fixing extraction. Patterns match radarlicencias.extractors.airbnb_picture.

Examples:
  python scripts/audit_banned_picture_urls.py data/airbnb_mallorca_20260101.jsonl
  python scripts/audit_banned_picture_urls.py --keys picture_url,r2_image_url export.jsonl
  cat export.jsonl | python scripts/audit_banned_picture_urls.py --stdin
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from radarlicencias.extractors.airbnb_picture import (
    BANNED_PICTURE_URL_SUBSTRINGS,
    is_banned_picture_url,
)


def _looks_like_url(s: str) -> bool:
    s = s.strip()
    return s.startswith("http://") or s.startswith("https://")


def _values_for_keys(obj: dict, keys: set[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k, v in obj.items():
        if k in keys and isinstance(v, str) and v:
            out.append((k, v))
    return out


def _scan_record(obj: dict, keys: set[str], scan_all_url_strings: bool) -> list[tuple[str, str]]:
    flagged: list[tuple[str, str]] = []
    if scan_all_url_strings:
        for k, v in obj.items():
            if isinstance(v, str) and _looks_like_url(v) and is_banned_picture_url(v):
                flagged.append((k, v))
        return flagged
    for k, v in _values_for_keys(obj, keys):
        if is_banned_picture_url(v):
            flagged.append((k, v))
    return flagged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="JSONL file (one JSON object per line). Omit with --stdin.",
    )
    parser.add_argument(
        "--keys",
        default="picture_url,image_url,r2_url,r2_image_url,primary_image_url",
        help="Comma-separated object keys to check (default: common picture/R2 fields).",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSONL from stdin instead of a file.",
    )
    parser.add_argument(
        "--scan-all-url-like-strings",
        action="store_true",
        help="Flag any string value that looks like a URL and matches banned patterns (slower, broader).",
    )
    parser.add_argument(
        "--print-banned-patterns",
        action="store_true",
        help="Print banned substrings and exit.",
    )
    args = parser.parse_args(argv)

    if args.print_banned_patterns:
        for p in BANNED_PICTURE_URL_SUBSTRINGS:
            print(p)
        return 0

    key_set = {k.strip() for k in args.keys.split(",") if k.strip()}

    def lines():
        if args.stdin:
            yield from sys.stdin
        else:
            if not args.path:
                parser.error("path required unless --stdin")
            with args.path.open(encoding="utf-8", errors="replace") as f:
                yield from f

    bad_lines = 0
    for lineno, line in enumerate(lines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"{lineno}: JSON decode error: {e}", file=sys.stderr)
            continue
        if not isinstance(obj, dict):
            continue
        hits = _scan_record(obj, key_set, args.scan_all_url_like_strings)
        if not hits:
            continue
        bad_lines += 1
        url_field = obj.get("url") or obj.get("listing_url") or ""
        listing_id = obj.get("listing_id", "")
        parts = [f"line={lineno}"]
        if listing_id:
            parts.append(f"listing_id={listing_id}")
        if url_field:
            parts.append(f"url={url_field}")
        for key, val in hits:
            parts.append(f"{key}={val!r}")
        print(" ".join(parts))

    if bad_lines:
        print(
            f"Summary: {bad_lines} line(s) with banned pattern(s) in selected field(s).",
            file=sys.stderr,
        )
        return 1
    print("No banned patterns found in selected field(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
