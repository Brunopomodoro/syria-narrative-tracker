#!/usr/bin/env python3
"""The tracker's health over the last days, compared with the days before: updates and gaps, the sample, sources
that failed or went quiet, stories, retries, Arabic completeness and cost. Reads data/quality.json (one line per
update, written by pipeline.py) and, for days before that log existed, the archive. Prints Markdown. Free.

Usage:  python scripts/quality_report.py [DAYS]      (default 7)
"""
import datetime as dt
import json
import pathlib
import re
import statistics
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UTC = dt.timezone.utc
ARABIC = re.compile(r"[؀-ۿ]")


def when(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def arabic_gaps(run: dict) -> int:
    """Arabic fields of a published update that hold no Arabic although the English one has text."""
    gaps = 0
    ov = run.get("overall") or {}
    for k in ("brief", "mood"):
        if ov.get(k) and not ARABIC.search(str(ov.get(k + "_ar") or "")):
            gaps += 1
    for n in run.get("narratives") or []:
        for k in ("title", "summary"):
            if n.get(k) and not ARABIC.search(str(n.get(k + "_ar") or "")):
                gaps += 1
    return gaps


def from_archive(day_files: list) -> tuple[list, dict]:
    """Rows in the quality.json layout from archived updates (published ones only), and Arabic gaps per update."""
    rows, gaps = [], {}
    for f in day_files:
        for r in json.loads(f.read_text(encoding="utf-8")).get("runs") or []:
            st, src = r.get("stats") or {}, r.get("sources") or []
            sent, pub = st.get("unique_posts") or 0, st.get("public_posts") or 0
            total = st.get("posts_analyzed") or 0
            shares = sorted((float(n.get("share") or 0) for n in r.get("narratives") or []), reverse=True)
            rows.append({"time": r["generated_at"], "outcome": "published", "collected": st.get("collected", 0),
                         "relevant": st.get("relevant", 0), "sent": sent,
                         "outlet_share": round(1 - pub / total, 3) if total else None,
                         "languages": st.get("languages") or {}, "sources_ok": st.get("sources_ok", 0),
                         "sources_total": st.get("sources_total", 0),
                         "failed": sorted(s["name"] for s in src if not s.get("ok")),
                         "quiet": sorted(s["name"] for s in src if s.get("ok") and not s.get("recent", s.get("fetched"))),
                         "stories": len(r.get("narratives") or []), "top_share": shares[0] if shares else None,
                         "retried": None, "arabic_filled": None, "cost_usd": r.get("cost_usd") or 0.0,
                         "model": r.get("model", ""), "_archive": True})
            gaps[r["generated_at"]] = arabic_gaps(r)
    return rows, gaps


def load(start: dt.datetime, end: dt.datetime) -> tuple[list, dict]:
    logged = [r for r in json.loads((DATA / "quality.json").read_text(encoding="utf-8"))] if (DATA / "quality.json").exists() else []
    first_logged = min((when(r["time"]) for r in logged), default=end)
    days = sorted(f for f in (DATA / "archive").glob("????-??-??.json") if start.date() <= dt.date.fromisoformat(f.stem) <= end.date())
    archived, gaps = from_archive(days)
    rows = [r for r in logged if start <= when(r["time"]) < end]
    rows += [r for r in archived if start <= when(r["time"]) < min(end, first_logged)]
    return sorted(rows, key=lambda r: r["time"]), gaps


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def summary(rows: list, gaps: dict, start: dt.datetime, end: dt.datetime) -> dict:
    pub = [r for r in rows if r["outcome"] == "published"]
    times = [start] + [when(r["time"]) for r in pub] + [end]
    biggest = max((b - a for a, b in zip(times, times[1:])), default=dt.timedelta(0))
    n = len(pub) or 1
    fail, quiet = Counter(), Counter()
    for r in pub:
        fail.update(r.get("failed") or [])
        quiet.update(r.get("quiet") or [])
    langs = Counter()
    for r in pub:
        langs.update(r.get("languages") or {})
    lang_total = sum(langs.values()) or 1
    return {
        "updates": len(pub), "outcomes": dict(Counter(r["outcome"] for r in rows)),
        "max_gap_h": round(biggest.total_seconds() / 3600, 1),
        "sent": mean([r.get("sent") for r in pub]), "relevant": mean([r.get("relevant") for r in pub]),
        "outlet_share": mean([r.get("outlet_share") for r in pub]),
        "outlet_range": (min((r["outlet_share"] for r in pub if r.get("outlet_share") is not None), default=None),
                         max((r["outlet_share"] for r in pub if r.get("outlet_share") is not None), default=None)),
        "languages": {k: round(v / lang_total, 3) for k, v in langs.most_common()},
        "sources_ok": mean([r.get("sources_ok") for r in pub]), "sources_total": max((r.get("sources_total", 0) for r in pub), default=0),
        "fail": fail, "quiet": quiet, "n": n,
        "stories": mean([r.get("stories") for r in pub]), "top_share": mean([r.get("top_share") for r in pub]),
        "retries": sum(1 for r in rows if r.get("retried")),
        "arabic_filled": sum(r.get("arabic_filled") or 0 for r in pub),
        "arabic_gaps": sum(gaps.get(r["time"], 0) for r in pub),
        "cost": round(sum(r.get("cost_usd") or 0 for r in rows), 2),
        "models": sorted({r.get("model") for r in pub if r.get("model")}),
    }


def fmt(x, pct=False):
    if x is None:
        return "–"
    return f"{x * 100:.0f}%" if pct else f"{round(x) if x >= 10 else round(x, 1):g}"


def main() -> int:
    days = int(sys.argv[1]) if sys.argv[1:] else 7
    end = dt.datetime.now(UTC)
    start, prev_start = end - dt.timedelta(days=days), end - dt.timedelta(days=2 * days)
    rows, gaps = load(start, end)
    prev_rows, prev_gaps = load(prev_start, start)
    a, b = summary(rows, gaps, start, end), summary(prev_rows, prev_gaps, prev_start, start)
    print(f"# Tracker health, {start:%Y-%m-%d} to {end:%Y-%m-%d} ({days} days; the previous {days} days in brackets)\n")
    print(f"- Updates published: {a['updates']} ({b['updates']}); all runs by outcome: {a['outcomes']}")
    print(f"- Longest time without a new update: {a['max_gap_h']} h ({b['max_gap_h']} h)")
    print(f"- Posts per update: {fmt(a['relevant'])} relevant, {fmt(a['sent'])} sent to analysis ({fmt(b['sent'])})")
    lo, hi = a["outlet_range"]
    print(f"- Outlet share of the sample: {fmt(a['outlet_share'], True)} ({fmt(b['outlet_share'], True)}), range {fmt(lo, True)}–{fmt(hi, True)}; target at most 30%")
    print("- Languages: " + ", ".join(f"{k} {fmt(v, True)}" for k, v in a["languages"].items()))
    print(f"- Stories per update: {fmt(a['stories'])} ({fmt(b['stories'])}); largest story's share on average: {fmt(a['top_share'], True)} ({fmt(b['top_share'], True)})")
    print(f"- Empty replies retried: {a['retries']} ({b['retries']}); Arabic fields filled in afterwards: {a['arabic_filled']}; "
          f"Arabic still missing in published updates: {a['arabic_gaps']} ({b['arabic_gaps']})")
    print(f"- Cost: ${a['cost']} (${b['cost']}), about ${round(a['cost'] / days * 30, 2)} a month at this rate; model {', '.join(a['models']) or '–'}")
    print(f"- Sources working per update: {fmt(a['sources_ok'])} of {a['sources_total']} ({fmt(b['sources_ok'])})\n")
    flagged = [(s, c) for s, c in a["fail"].most_common() if c / a["n"] >= 0.25]
    print("## Sources failing in at least a quarter of updates\n")
    print("\n".join(f"- {s}: {c} of {a['n']} (before: {b['fail'].get(s, 0)} of {b['n']})" for s, c in flagged) or "- none")
    quiet = [(s, c) for s, c in a["quiet"].most_common() if c / a["n"] >= 0.5]
    print("\n## Sources working but with no recent post in at least half of updates\n")
    print("\n".join(f"- {s}: {c} of {a['n']} (before: {b['quiet'].get(s, 0)} of {b['n']})" for s, c in quiet) or "- none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
