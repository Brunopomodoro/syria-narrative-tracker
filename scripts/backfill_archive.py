#!/usr/bin/env python3
"""One-off: build the permanent archive (data/archive/) from every earlier version of data/latest.json
and data/headlines.json in the git history, then rebuild the per-day index and the monthly downloads.

Safe to run again: runs are matched by their time, headlines by id.
Needs the full git history (git fetch --unshallow if the checkout is shallow).

Usage:  python scripts/backfill_archive.py
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
from pipeline import load_config  # noqa: E402

ROOT = archive.ROOT


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def versions(path: str):
    """Every version of a file in the history, oldest first, parsed as JSON (skipping unreadable ones)."""
    for sha in reversed(git("log", "--format=%H", "--", path).split()):
        try:
            yield json.loads(git("show", f"{sha}:{path}"))
        except (subprocess.CalledProcessError, ValueError):
            continue


def main() -> int:
    cfg = load_config()
    runs, seen = 0, set()
    for latest in versions("data/latest.json"):
        t = latest.get("generated_at")
        if not t or t in seen or not latest.get("narratives"):
            continue   # the same analysis re-saved with a newer checked_at, or an empty run
        seen.add(t)
        for n in latest["narratives"]:
            n.setdefault("key", archive.story_key(n))
        archive.add_run(latest)
        runs += 1
    heads = {}
    for version in versions("data/headlines.json"):
        for h in version if isinstance(version, list) else []:
            heads.setdefault(h.get("id"), h)
    days = archive.merge_headlines(list(heads.values()))
    archive.update_index(cfg, None)
    months = sorted({d[:7] for d in archive.all_days()})
    archive.write_exports(cfg, months)
    print(f"Archived {runs} runs and {len(heads)} headlines ({len(days)} days of headlines changed); "
          f"{len(archive.all_days())} days in the archive; exports for {', '.join(months)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
