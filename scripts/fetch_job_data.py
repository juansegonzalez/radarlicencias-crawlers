#!/usr/bin/env python3
"""
Fetch job data from Scrapy Cloud / Zyte Storage API for inspection.
Saves items, logs, and item stats for a given job.

Usage:
  export SHUB_API_KEY="your_scrapy_cloud_api_key"
  python scripts/fetch_job_data.py [project_id] [spider_id] [job_id]

Defaults (from URL https://app.zyte.com/p/853585/1/13/items):
  project_id=853585, spider_id=1, job_id=13

Output: data/job_<project>_<spider>_<job>/ with items.jl, logs.jl, stats.json
"""

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://storage.zyte.com"
COUNT = 500  # items per request (pagination)


def get_auth():
    """
    Resolve Scrapy Cloud API key in this order:
    1) SHUB_API_KEY env
    2) SCRAPY_CLOUD_API_KEY env
    3) radarlicencias/local_config.SCRAPY_CLOUD_API_KEY (local, gitignored)
    """
    key = os.environ.get("SHUB_API_KEY", "").strip() or os.environ.get("SCRAPY_CLOUD_API_KEY", "").strip()
    if not key:
        # Try local_config in this project (without requiring PYTHONPATH to be set)
        try:
            project_root = Path(__file__).resolve().parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            import importlib

            local_cfg = importlib.import_module("radarlicencias.local_config")
            key = getattr(local_cfg, "SCRAPY_CLOUD_API_KEY", "").strip()
        except Exception:
            key = ""
    if not key:
        print(
            "Set SHUB_API_KEY or SCRAPY_CLOUD_API_KEY env, or define "
            "SCRAPY_CLOUD_API_KEY in radarlicencias/local_config.py (not committed).",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def _request(url: str, api_key: str, params: dict | None = None) -> str:
    if params:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{q}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{api_key}:".encode()).decode())
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8")


def fetch_items(project_id: int, spider_id: int, job_id: int, out_path: Path, api_key: str) -> int:
    url = f"{BASE}/items/{project_id}/{spider_id}/{job_id}"
    total = 0
    start_after = None
    with open(out_path, "w", encoding="utf-8") as f:
        while True:
            params = {"count": COUNT}
            if start_after is not None:
                params["startafter"] = start_after
            text = _request(url, api_key, params)
            lines = text.strip().split("\n") if text else []
            if not lines:
                break
            for line in lines:
                if line.strip():
                    f.write(line.rstrip("\n") + "\n")
                    total += 1
            if len(lines) < COUNT:
                break
            last_key = json.loads(lines[-1]).get("_key") if lines else None
            if not last_key:
                break
            start_after = last_key
    return total


def fetch_logs(project_id: int, spider_id: int, job_id: int, out_path: Path, api_key: str) -> int:
    url = f"{BASE}/logs/{project_id}/{spider_id}/{job_id}/"
    text = _request(url, api_key)
    lines = text.strip().split("\n") if text else []
    with open(out_path, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip():
                f.write(line.rstrip("\n") + "\n")
    return len(lines)


def fetch_stats(project_id: int, spider_id: int, job_id: int, out_path: Path, api_key: str) -> dict:
    url = f"{BASE}/items/{project_id}/{spider_id}/{job_id}/stats"
    text = _request(url, api_key)
    data = json.loads(text)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def main():
    parser = argparse.ArgumentParser(description="Fetch Scrapy Cloud job data for inspection.")
    parser.add_argument("project_id", nargs="?", type=int, default=853585)
    parser.add_argument("spider_id", nargs="?", type=int, default=1)
    parser.add_argument("job_id", nargs="?", type=int, default=13)
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory (default: data/job_P_S_J)")
    args = parser.parse_args()

    api_key = get_auth()
    out_dir = Path(args.output_dir) if args.output_dir else Path("data") / f"job_{args.project_id}_{args.spider_id}_{args.job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching job {args.project_id}/{args.spider_id}/{args.job_id} -> {out_dir}")

    # Stats first (small)
    try:
        stats = fetch_stats(args.project_id, args.spider_id, args.job_id, out_dir / "stats.json", api_key)
        print(f"  stats.json: {stats.get('totals', {}).get('input_values', 'N/A')} items")
    except Exception as e:
        print(f"  stats: {e}", file=sys.stderr)

    # Items (paginated)
    try:
        n = fetch_items(args.project_id, args.spider_id, args.job_id, out_dir / "items.jl", api_key)
        print(f"  items.jl: {n} items")
    except Exception as e:
        print(f"  items: {e}", file=sys.stderr)

    # Logs
    try:
        n = fetch_logs(args.project_id, args.spider_id, args.job_id, out_dir / "logs.jl", api_key)
        print(f"  logs.jl: {n} lines")
    except Exception as e:
        print(f"  logs: {e}", file=sys.stderr)

    print(f"Done. Inspect files in {out_dir}")


if __name__ == "__main__":
    main()
