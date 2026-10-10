#!/usr/bin/env python3
"""
Monthly review: once a new month has started, a written review of the month that just ended,
from the archive and the weekly digests, written by Claude in English and Arabic, with the month's
theme table, tone by week and the stories that carried coordination signals computed here.

  data/monthly/<YYYY-MM>.json   the review text and the month's numbers
  data/monthly/index.json       the list of reviews
  monthly/<lang>/<YYYY-MM>.html the pages (scripts/pages.py), feed-monthly.xml / feed-monthly-ar.xml
                                (the feeds carry the full text, so an RSS-to-email service can send
                                each review as a newsletter; GUIDE.md, "Monthly review and newsletter")

Called by scripts/pipeline.py after a run (maybe_generate) and by the Maintenance workflow (backfill).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pages  # noqa: E402
import weekly  # noqa: E402

DATA = archive.DATA
MONTHLY_DATA = DATA / "monthly"
UTC = dt.timezone.utc
MIN_DAYS = 10          # a month with fewer days of data gets no review
MIN_PREV_DAYS = 7      # the change against the previous month is shown only when that month has this many days
LEVEL_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def month_range(month: str) -> tuple[str, str]:
    y, m = int(month[:4]), int(month[5:7])
    first = dt.date(y, m, 1)
    last = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    return first.isoformat(), last.isoformat()


def prev_month(month: str) -> str:
    first = dt.date(int(month[:4]), int(month[5:7]), 1)
    return (first - dt.timedelta(days=1)).strftime("%Y-%m")


def _theme_table(cfg: dict, ds: list) -> dict:
    out = {}
    for tid in [t["id"] for t in archive.theme_catalog(cfg)]:
        rows = [d["themes"][tid] for d in ds if d.get("themes", {}).get(tid)]
        share = sum(d.get("themes", {}).get(tid, {}).get("share", 0) for d in ds) / len(ds) if ds else 0
        out[tid] = {"theme": tid, "share": round(share, 3), "stories": sum(r.get("stories", 0) for r in rows),
                    "volume": sum(r.get("volume", 0) for r in rows),
                    "public_sentiment": archive._mean([(r.get("public_sentiment"), r.get("public_volume", 0)) for r in rows]),
                    "outlet_sentiment": archive._mean([(r.get("outlet_sentiment"), r.get("volume", 0) - r.get("public_volume", 0)) for r in rows])}
    return out


def month_stats(cfg: dict, month: str) -> dict | None:
    """The month's numbers from the archive: themes with the change from the month before, tone by week,
    the stories of the month, the ones that carried coordination signals, and the weekly digests."""
    start, end = month_range(month)
    index = archive._load(archive.ARCHIVE / "index.json", {})
    days = [d for d in index.get("days") or [] if start <= d["date"] <= end and d.get("runs")]
    if len(days) < MIN_DAYS:
        return None
    p_start, p_end = month_range(prev_month(month))
    prev = [d for d in index.get("days") or [] if p_start <= d["date"] <= p_end and d.get("runs")]
    if len(prev) < MIN_PREV_DAYS:
        prev = []
    this, last = _theme_table(cfg, days), _theme_table(cfg, prev) if prev else {}
    themes = []
    for tid, row in this.items():
        if row["share"] <= 0 and not row["stories"]:
            continue
        row["change"] = round(row["share"] - last[tid]["share"], 3) if last else None
        themes.append(row)
    themes.sort(key=lambda r: r["share"], reverse=True)

    # tone by ISO week
    weeks: dict = {}
    for d in days:
        wk = weekly.week_of(dt.date.fromisoformat(d["date"]))
        w = weeks.setdefault(wk, {"week": wk, "days": [], "posts": 0, "runs": 0, "pub": [], "out": []})
        w["days"].append(d["date"]); w["posts"] += d.get("posts", 0); w["runs"] += d.get("runs", 0)
        w["pub"].append((d.get("public_sentiment"), d.get("public_posts") or 1))
        w["out"].append((d.get("outlet_sentiment"), d.get("outlet_posts") or 1))
    week_rows = [{"week": w["week"], "from": min(w["days"]), "to": max(w["days"]), "days": len(w["days"]), "posts": w["posts"], "runs": w["runs"],
                  "public_sentiment": archive._mean(w["pub"]), "outlet_sentiment": archive._mean(w["out"])} for w in weeks.values()]
    week_rows.sort(key=lambda w: w["week"])

    # the stories of the month, aggregated over every run
    stories: dict = {}
    for d in days:
        for r in archive.load_day(d["date"]).get("runs") or []:
            for n in r.get("narratives") or []:
                key = n.get("key") or archive.story_key(n)
                e = stories.setdefault(key, {"key": key, "runs": 0, "volume": 0, "max_share": 0, "first": d["date"], "last": d["date"],
                                             "signals": None})
                e.update({"title": n.get("title", ""), "title_ar": n.get("title_ar", ""), "theme": n.get("theme", "other"),
                          "summary": n.get("summary", ""), "public_reaction": n.get("public_reaction", ""),
                          "public_sentiment": n.get("public_sentiment"), "sentiment": n.get("sentiment"), "flags": n.get("flags", [])})
                e["runs"] += 1
                e["volume"] += int(n.get("volume") or 0)
                e["max_share"] = max(e["max_share"], float(n.get("share") or 0))
                e["first"], e["last"] = min(e["first"], d["date"]), max(e["last"], d["date"])
                sig = n.get("signals") or {}
                if sig.get("items") and LEVEL_RANK.get(sig.get("level"), 0) >= LEVEL_RANK.get((e["signals"] or {}).get("level"), 0):
                    e["signals"] = sig
    top = sorted(stories.values(), key=lambda e: e["volume"], reverse=True)[:30]
    flagged = sorted([e for e in stories.values() if LEVEL_RANK.get((e.get("signals") or {}).get("level"), 0) >= 2],
                     key=lambda e: e["volume"], reverse=True)[:10]

    digests = [x for x in archive._load(weekly.WEEKLY_DATA / "index.json", []) if x.get("from", "") <= end and x.get("to", "") >= start]
    langs = Counter()
    for d in days:
        for k, v in (d.get("languages") or {}).items():
            langs[k] += int(v or 0)
    total_l = sum(langs.values()) or 1
    return {
        "month": month, "from": start, "to": end, "days": len(days),
        "posts": sum(d.get("posts", 0) for d in days), "runs": sum(d.get("runs", 0) for d in days),
        "public_sentiment": archive._mean([(d.get("public_sentiment"), d.get("public_posts") or 1) for d in days]),
        "outlet_sentiment": archive._mean([(d.get("outlet_sentiment"), d.get("outlet_posts") or 1) for d in days]),
        "prev_public_sentiment": archive._mean([(d.get("public_sentiment"), d.get("public_posts") or 1) for d in prev]) if prev else None,
        "prev_outlet_sentiment": archive._mean([(d.get("outlet_sentiment"), d.get("outlet_posts") or 1) for d in prev]) if prev else None,
        "prev_days": len(prev),
        "themes": themes, "weeks": week_rows, "top_stories": top, "flagged": flagged, "stories_total": len(stories),
        "languages": {k: round(v / total_l, 3) for k, v in langs.most_common()},
        "digests": digests,
        "events": [e for e in index.get("events") or [] if start <= e.get("date", "") <= end],
    }


REVIEW_PROMPT = """You are a careful, neutral analyst writing the monthly review of the Syria Narrative Tracker, which follows what is said about Syria online (public posts in Arabic, Kurdish and English from Telegram channels, news feeds, YouTube comments, Reddit, X and Bluesky). The review is also sent as a newsletter to researchers, journalists and people who follow Syria closely, so it must stand on its own.

You receive the month's numbers, the weekly digests, the stories the tracker followed and, for some stories, coordination signals. Write:
- "title": a headline for the month (not clickbait; what defined the month).
- "paragraphs": 5 to 7 short paragraphs: the arc of the month and what dominated the discussion; how the themes moved against the previous month, when that is known; where people's reactions and outlet coverage differed; where communities or languages framed things differently; which stories carried signs of coordination and what the signs were; what faded and what emerged. Use the numbers when they matter, sparingly.
- "highlights": 6 to 10 of the given stories that mattered most, each with its "key" exactly as given, its title, and one sentence on why it mattered.
- "watch": 3 to 5 short points on what to watch next month, grounded in the stories, not speculation.
Volume figures are post analyses: each update analyses a sample of posts from the previous day, so one post can be counted in several updates. Use them only to compare weeks or months with each other; never present them as numbers of posts or of people.
Coordination signals are measured signs (copy-paste, near-identical posts, bursts, the same text on several platforms, few commenters writing most comments, regular timing) that a reaction may be organised. Report them as signs to look into, never as proof of a campaign, and never guess who is behind them.
Rules: describe, never endorse; attribute claims to who made them; add no facts that are not in the material; never name or describe private individuals; note when something rests on few posts. Tone runs from -1 (anger, fear, grief) to +1 (hope, pride). Every text field is written twice: in English and, in the field ending in "_ar", in natural Modern Standard Arabic for Syrian readers (not a word-for-word translation)."""


def build_message(cfg: dict, s: dict) -> str:
    def tone(v):
        return "n/a" if v is None else f"{v:+.2f}"
    lines = [f"Month {s['month']}: {s['from']} to {s['to']}, {s['days']} days of data, {s['runs']} updates, {s['posts']} post analyses (see the note on volume figures).",
             f"Average tone: people {tone(s['public_sentiment'])} (previous month {tone(s['prev_public_sentiment'])}), outlets {tone(s['outlet_sentiment'])} (previous month {tone(s['prev_outlet_sentiment'])})."]
    if not s["prev_days"]:
        lines.append("No comparable previous month: this is the first month of data, so do not describe changes from an earlier month.")
    if s["languages"]:
        lines.append("Languages of the posts analysed: " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in s["languages"].items()))
    lines.append("")
    if s["events"]:
        lines += ["Events this month: " + "; ".join(f"{e['date']}: {e['label']}" for e in s["events"]), ""]
    lines.append("Themes (share of discussion, change vs previous month, people tone, outlet tone, stories):")
    for r in s["themes"]:
        ch = "n/a" if r.get("change") is None else f"{r['change'] * 100:+.0f} pts"
        lines.append(f"- {pages.theme_label(cfg, r['theme'], 'en')}: {r['share'] * 100:.0f}%, {ch}, people {tone(r['public_sentiment'])}, outlets {tone(r['outlet_sentiment'])}, {r['stories']} stories")
    lines += ["", "Tone by week (people / outlets / post analyses):"]
    lines += [f"- {w['week']} ({w['from']} to {w['to']}): {tone(w['public_sentiment'])} / {tone(w['outlet_sentiment'])} / {w['posts']}" for w in s["weeks"]]
    if s["digests"]:
        lines += ["", "The weekly digests of the month (title, then the opening paragraph):"]
        for d in s["digests"]:
            lines.append(f"- {d['week']}: {d.get('title', '')}")
            if d.get("paragraphs"):
                lines.append(f"    {d['paragraphs'][0][:500]}")
    lines += ["", f"Stories, most discussed first (key | theme | days seen | appeared in N updates | people tone | outlet tone); {s['stories_total']} stories in all:"]
    for e in s["top_stories"]:
        lines.append(f"[{e['key']}] {e['title']} | {e['theme']} | {e['first']} to {e['last']} | {e['runs']} updates | people {tone(e['public_sentiment'])} | outlets {tone(e['sentiment'])}")
        lines.append(f"    {e['summary'][:300]}")
        if e.get("public_reaction"):
            lines.append(f"    Reaction: {e['public_reaction'][:200]}")
    if s["flagged"]:
        lines += ["", "Stories that carried coordination signals (level: signals):"]
        for e in s["flagged"]:
            sig = e["signals"]
            lines.append(f"- [{e['key']}] {e['title']}: {sig.get('level')}: " + ", ".join(f"{i['id']}={i['value']}" for i in sig.get("items") or []))
    return "\n".join(lines)


def generate(cfg: dict, month: str, log=print) -> dict | None:
    """Write the review for one month. Returns it, or None when the month has too little data."""
    import anthropic
    s = month_stats(cfg, month)
    if not s:
        log(f"  monthly {month}: fewer than {MIN_DAYS} days of data, skipped")
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY secret is missing")
    client = anthropic.Anthropic(api_key=key)
    model = cfg.get("model", "claude-sonnet-5")
    resp = client.messages.create(model=model, max_tokens=12000, system=REVIEW_PROMPT,
                                  messages=[{"role": "user", "content": build_message(cfg, s)}],
                                  output_config={"effort": str(cfg.get("effort", "low")), "format": {"type": "json_schema", "schema": weekly.digest_schema()}})
    text = "".join(b.text for b in resp.content if b.type == "text")
    d = json.loads(text)
    keys = {e["key"] for e in s["top_stories"]} | {e["key"] for e in s["flagged"]}
    highlights, used = [], set()
    for h in d.get("highlights") or []:
        if h.get("key") in keys and h["key"] not in used:
            used.add(h["key"]); highlights.append(h)
    review = {"month": month, "from": s["from"], "to": s["to"], "generated_at": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "model": model, "title": d["title"], "title_ar": d["title_ar"], "paragraphs": d["paragraphs"], "paragraphs_ar": d["paragraphs_ar"],
              "highlights": highlights[:10], "watch": d["watch"], "watch_ar": d["watch_ar"],
              "digests": [{k: x.get(k) for k in ("week", "from", "to", "title", "title_ar", "paragraphs", "paragraphs_ar")} for x in s["digests"]],
              "flagged": [{"key": e["key"], "title": e["title"], "title_ar": e["title_ar"], "theme": e["theme"], "signals": e["signals"]} for e in s["flagged"]],
              "stats": {k: s[k] for k in ("days", "posts", "runs", "public_sentiment", "outlet_sentiment", "prev_public_sentiment", "prev_outlet_sentiment",
                                          "prev_days", "themes", "weeks", "languages", "events", "stories_total")},
              "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}}
    archive._save(MONTHLY_DATA / f"{month}.json", review)
    index = [x for x in archive._load(MONTHLY_DATA / "index.json", []) if x.get("month") != month]
    index.append({"month": month, "from": s["from"], "to": s["to"], "title": review["title"], "title_ar": review["title_ar"],
                  "generated_at": review["generated_at"], "paragraphs": review["paragraphs"][:1], "paragraphs_ar": review["paragraphs_ar"][:1]})
    index.sort(key=lambda x: x["month"])
    archive._save(MONTHLY_DATA / "index.json", index)
    pages.write_monthly_pages(cfg, review)
    pages.write_monthly_listing(cfg, index)
    pages.write_monthly_feeds(cfg, index)
    log(f"  monthly {month}: review written ({resp.usage.input_tokens}/{resp.usage.output_tokens} tokens)")
    return review


def maybe_generate(cfg: dict, state: dict, log=print) -> bool:
    """After a run: if a new month has begun since the last review, write the review of the month that ended.
    Never raises; a failure is logged and tried again on a later run, up to three times."""
    today = dt.datetime.now(UTC).date()
    last = prev_month(today.strftime("%Y-%m"))
    done = {x.get("month") for x in archive._load(MONTHLY_DATA / "index.json", [])}
    attempts = state.get("monthly_attempts") or {}
    if last in done or not cfg.get("monthly_review", True) or int(attempts.get(last, 0)) >= 3:
        return False
    state["monthly_attempts"] = {last: int(attempts.get(last, 0)) + 1}
    try:
        return generate(cfg, last, log) is not None
    except Exception as e:  # noqa: BLE001
        log(f"  monthly {last}: failed ({e}); will retry on a later run")
        return False


def backfill(cfg: dict, log=print) -> int:
    """Reviews for every complete past month with enough data that has none yet."""
    days = archive.all_days()
    if not days:
        return 0
    today = dt.datetime.now(UTC).date()
    done = {x.get("month") for x in archive._load(MONTHLY_DATA / "index.json", [])}
    n, month = 0, days[0][:7]
    while month < today.strftime("%Y-%m"):
        if month not in done and generate(cfg, month, log):
            n += 1
        first = dt.date(int(month[:4]), int(month[5:7]), 1)
        month = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1).strftime("%Y-%m")
    return n


if __name__ == "__main__":
    import pipeline as P
    print(f"{backfill(P.load_config())} reviews written.")
