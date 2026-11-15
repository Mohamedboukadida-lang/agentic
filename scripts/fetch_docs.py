"""Download the pages listed in data/sources.yaml into data/raw/<name>.html.

    python scripts/fetch_docs.py            # fetch everything that is missing
    python scripts/fetch_docs.py --force    # fetch again, overwriting

data/raw is git-ignored on purpose: commit the URL list, not the pages. Check the licence
and terms of any site you add before you fetch it, and keep the delay polite.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources.yaml"
RAW = ROOT / "data" / "raw"
USER_AGENT = "ragent-study-project/0.1 (personal learning project)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    args = parser.parse_args()

    entries = yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or []
    names = [e["name"] for e in entries]
    if len(names) != len(set(names)):
        print("error: duplicate names in data/sources.yaml", file=sys.stderr)
        return 2
    RAW.mkdir(parents=True, exist_ok=True)
    failed = 0
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30
    ) as http:
        for entry in entries:
            target = RAW / f"{entry['name']}.html"
            if target.exists() and not args.force:
                print(f"skip   {entry['name']} (exists)")
                continue
            try:
                response = http.get(entry["url"])
                response.raise_for_status()
            except httpx.HTTPError as exc:
                failed += 1
                print(f"FAILED {entry['name']}: {exc}", file=sys.stderr)
                continue
            target.write_text(response.text, encoding="utf-8")
            print(f"saved  {entry['name']} ({len(response.text) // 1024} KB)")
            time.sleep(args.delay)
    print(f"done, {failed} failed" if failed else "done")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
