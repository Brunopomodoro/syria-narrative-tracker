#!/usr/bin/env python3
"""Translate Arabic fields that past updates left empty (or wrote in English), in the archive, the hourly snapshots
and data/latest.json, then rebuild the affected pages. New updates fill such gaps themselves (pipeline.py,
fill_missing_arabic); this repairs the ones saved before that. A cent or two per update repaired.

Usage:  ANTHROPIC_API_KEY=... python scripts/backfill_arabic.py
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pages  # noqa: E402
import pipeline as P  # noqa: E402

ARABIC = re.compile(r"[؀-ۿ]")



def save_like(path: pathlib.Path, obj, original: str) -> None:
    """Write JSON in the same layout as the file had (indented or compact), so only the repaired fields change."""
    indented = original.lstrip().startswith("{\n")
    text = json.dumps(obj, ensure_ascii=False, indent=1) if indented else json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

def blank_non_arabic(run: dict) -> bool:
    """Empty every Arabic field that holds no Arabic (so fill_missing_arabic sees it as missing). Returns whether any."""
    found = False
    ov = run.get("overall") or {}
    for k in ("brief", "mood", "public_mood", "rest"):
        if ov.get(k) and not ARABIC.search(str(ov.get(k + "_ar") or "")):
            ov[k + "_ar"] = ""
            found = True
    for n in run.get("narratives") or []:
        for k in P.AR_FIELDS:
            v = n.get(k + "_ar")
            text = " ".join(v) if isinstance(v, list) else str(v or "")
            if n.get(k) and not ARABIC.search(text):
                n[k + "_ar"] = [] if isinstance(n.get(k), list) else ""
                found = True
    return found


def repair(cfg: dict, run: dict, usage: dict) -> int:
    if not blank_non_arabic(run):
        return 0
    run.setdefault("overall", {})
    return P.fill_missing_arabic(cfg, run["overall"], run.get("narratives") or [], usage)


def main() -> int:
    cfg = P.load_config()
    usage = {"input_tokens": 0, "output_tokens": 0}
    days, filled = set(), 0
    for date in archive.all_days():
        path = archive.DATA / "archive" / f"{date}.json"
        original = path.read_text(encoding="utf-8")
        day = json.loads(original)
        changed = 0
        for run in day.get("runs") or []:
            n = repair(cfg, run, usage)
            if n:
                print(f"{date} {run.get('generated_at', '')[11:16]}: {n} Arabic field(s) filled")
                changed += n
        if changed:
            save_like(path, day, original)
            days.add(date)
            filled += changed
    for path in sorted(P.SNAPSHOTS.glob("*.json")) + [P.DATA / "latest.json"]:
        original = path.read_text(encoding="utf-8")
        snap = json.loads(original)
        n = repair(cfg, snap, usage)
        if n:
            save_like(path, snap, original)
            print(f"{path.relative_to(P.ROOT)}: {n} Arabic field(s) filled")
            filled += n
    if not filled:
        print("No missing Arabic text found.")
        return 0
    if days:
        pages.write_daily_pages(cfg, sorted(days))
    latest = json.loads((P.DATA / "latest.json").read_text(encoding="utf-8"))
    pages.prerender_index(cfg, latest)
    print(f"{filled} field(s) filled; daily briefs rebuilt for {', '.join(sorted(days)) or 'no day'}; about ${P.estimate_cost(cfg.get('model', ''), usage)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
