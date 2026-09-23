#!/usr/bin/env python3
"""One-off: rebuild data/snapshots/ for past hours from earlier versions of data/latest.json in git,
so the website can show the full analysis of hours recorded before snapshots existed.

Usage (needs the full git history: git fetch --unshallow):
  python scripts/backfill_snapshots.py
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pipeline import DATA, SNAPSHOTS, parse_iso, snapshot_of  # noqa: E402


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=DATA.parent, check=True, capture_output=True, text=True).stdout


history = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
wanted = {h["time"]: h for h in history if not h.get("snapshot")}
SNAPSHOTS.mkdir(parents=True, exist_ok=True)
found = 0
for sha in git("log", "--format=%H", "--", "data/latest.json").split():
    try:
        latest = json.loads(git("show", f"{sha}:data/latest.json"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        continue
    h = wanted.pop(latest.get("generated_at"), None)
    if not h or not latest.get("narratives"):
        continue
    name = parse_iso(h["time"]).strftime("%Y%m%dT%H%MZ") + ".json"
    (SNAPSHOTS / name).write_text(json.dumps(snapshot_of(latest), ensure_ascii=False, separators=(",", ":")),
                                  encoding="utf-8")
    h["snapshot"] = name
    found += 1
(DATA / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Rebuilt {found} snapshots; {len(wanted)} past hours had no saved version.")
