#!/usr/bin/env python3
"""
Weekly digest: once a new ISO week has started, a written summary of the week that just ended,
from the archive, written by Claude in English and Arabic, with the week's theme table computed here.

  data/weekly/<week>.json    the digest text and the week's numbers
  data/weekly/index.json     the list of digests
  weekly/<lang>/<week>.html  the pages (scripts/pages.py), feed.xml / feed-ar.xml

Called by scripts/pipeline.py after a run (maybe_generate) and by the Maintenance workflow (backfill).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pages  # noqa: E402

DATA = archive.DATA
WEEKLY_DATA = DATA / "weekly"
UTC = dt.timezone.utc
MIN_DAYS = 3   # a week with fewer days of data gets no digest


def week_of(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_range(week: str) -> tuple[str, str]:
    y, w = int(week[:4]), int(week[-2:])
    monday = dt.date.fromisocalendar(y, w, 1)
    return monday.isoformat(), (monday + dt.timedelta(days=6)).isoformat()


def week_stats(cfg: dict, week: str) -> dict | None:
    """The week's numbers from the archive: per-theme share and tone (with the change from the week before),
    daily tone, and the top stories with their latest analysis."""
    start, end = week_range(week)
    index = archive._load(archive.ARCHIVE / "index.json", {})
    days = [d for d in index.get("days") or [] if start <= d["date"] <= end and d.get("runs")]
    if len(days) < MIN_DAYS:
        return None
    prev_start, prev_end = week_range(week_of(dt.date.fromisoformat(start) - dt.timedelta(days=1)))
    prev = [d for d in index.get("days") or [] if prev_start <= d["date"] <= prev_end and d.get("runs")]
    theme_ids = [t["id"] for t in archive.theme_catalog(cfg)]

    def theme_table(ds):
        out = {}
        for tid in theme_ids:
            rows = [d["themes"][tid] for d in ds if d.get("themes", {}).get(tid)]
            share = sum(d.get("themes", {}).get(tid, {}).get("share", 0) for d in ds) / len(ds) if ds else 0
            out[tid] = {"theme": tid, "share": round(share, 3), "stories": sum(r.get("stories", 0) for r in rows),
                        "volume": sum(r.get("volume", 0) for r in rows),
                        "public_sentiment": archive._mean([(r.get("public_sentiment"), r.get("public_volume", 0)) for r in rows]),
                        "outlet_sentiment": archive._mean([(r.get("outlet_sentiment"), r.get("volume", 0) - r.get("public_volume", 0)) for r in rows])}
        return out

    this, last = theme_table(days), theme_table(prev) if prev else {}
    themes = []
    for tid, row in this.items():
        if row["share"] <= 0 and not row["stories"]:
            continue
        row["change"] = round(row["share"] - last[tid]["share"], 3) if last else None
        themes.append(row)
    themes.sort(key=lambda r: r["share"], reverse=True)

    stories: dict = {}
    for d in days:
        for r in archive.load_day(d["date"]).get("runs") or []:
            for n in r.get("narratives") or []:
                key = n.get("key") or archive.story_key(n)
                e = stories.setdefault(key, {"key": key, "runs": 0, "max_share": 0, "volume": 0})
                e.update({"title": n.get("title", ""), "title_ar": n.get("title_ar", ""), "theme": n.get("theme", "other"),
                          "summary": n.get("summary", ""), "public_reaction": n.get("public_reaction", ""),
                          "public_sentiment": n.get("public_sentiment"), "sentiment": n.get("sentiment"),
                          "framings": n.get("framings", []), "flags": n.get("flags", [])})
                e["runs"] += 1
                e["volume"] += int(n.get("volume") or 0)
                e["max_share"] = max(e["max_share"], float(n.get("share") or 0))
    top = sorted(stories.values(), key=lambda e: e["volume"], reverse=True)[:25]
    return {
        "week": week, "from": start, "to": end,
        "days": [{"date": d["date"], "runs": d["runs"], "posts": d.get("posts", 0), "public_sentiment": d.get("public_sentiment"),
                  "outlet_sentiment": d.get("outlet_sentiment")} for d in days],
        "posts": sum(d.get("posts", 0) for d in days), "runs": sum(d.get("runs", 0) for d in days),
        "public_sentiment": archive._mean([(d.get("public_sentiment"), d.get("public_posts") or 1) for d in days]),
        "outlet_sentiment": archive._mean([(d.get("outlet_sentiment"), d.get("outlet_posts") or 1) for d in days]),
        "prev_public_sentiment": archive._mean([(d.get("public_sentiment"), d.get("public_posts") or 1) for d in prev]) if prev else None,
        "themes": themes, "top_stories": top,
        "events": [e for e in index.get("events") or [] if start <= e.get("date", "") <= end],
    }


DIGEST_PROMPT = """You are a careful, neutral analyst writing the weekly brief of the Syria Narrative Tracker, which follows what is said about Syria online (public posts in Arabic, Kurdish and English from Telegram channels, news feeds, YouTube comments, Reddit and X). Readers are researchers, journalists and people who follow Syria closely.

You receive the week's numbers and the stories the tracker followed. Write:
- "title": a headline for the week (not clickbait; what defined the week).
- "paragraphs": 3 to 5 short paragraphs: what dominated the discussion and how it moved; where people's reactions and outlet coverage differed; where communities or languages framed things differently; what was new or faded. Use the numbers when they matter (shares, tones, changes from the week before), sparingly.
- "highlights": 3 to 6 of the given stories that mattered most, each with its "key" exactly as given, its title, and one sentence on why it mattered.
- "watch": 2 to 4 short points on what to watch next week, grounded in the stories, not speculation.
Rules: describe, never endorse; attribute claims to who made them; add no facts that are not in the material; never name or describe private individuals; note when something rests on few posts. Tone runs from -1 (anger, fear, grief) to +1 (hope, pride). Every text field is written twice: in English and, in the field ending in "_ar", in natural Modern Standard Arabic for Syrian readers (not a word-for-word translation)."""


def digest_schema() -> dict:
    strs = {"type": "array", "items": {"type": "string"}}
    obj = lambda props: {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    return obj({"title": {"type": "string"}, "title_ar": {"type": "string"}, "paragraphs": strs, "paragraphs_ar": strs,
                "highlights": {"type": "array", "items": obj({"key": {"type": "string"}, "title": {"type": "string"}, "title_ar": {"type": "string"},
                                                              "why": {"type": "string"}, "why_ar": {"type": "string"}})},
                "watch": strs, "watch_ar": strs})


def build_message(cfg: dict, s: dict) -> str:
    def tone(v):
        return "n/a" if v is None else f"{v:+.2f}"
    lines = [f"Week {s['week']}: {s['from']} to {s['to']}. {s['runs']} updates, {s['posts']} posts analysed.",
             f"Average tone: people {tone(s['public_sentiment'])} (previous week {tone(s['prev_public_sentiment'])}), outlets {tone(s['outlet_sentiment'])}.", ""]
    if s["events"]:
        lines += ["Events this week: " + "; ".join(f"{e['date']}: {e['label']}" for e in s["events"]), ""]
    lines.append("Themes (share of discussion, change vs previous week, people tone, outlet tone, stories):")
    for r in s["themes"]:
        ch = "n/a" if r.get("change") is None else f"{r['change'] * 100:+.0f} pts"
        lines.append(f"- {pages.theme_label(cfg, r['theme'], 'en')}: {r['share'] * 100:.0f}%, {ch}, people {tone(r['public_sentiment'])}, outlets {tone(r['outlet_sentiment'])}, {r['stories']} stories")
    lines += ["", "Tone by day (people / outlets / posts):"]
    lines += [f"- {d['date']}: {tone(d['public_sentiment'])} / {tone(d['outlet_sentiment'])} / {d['posts']}" for d in s["days"]]
    lines += ["", "Stories, most discussed first (key | theme | appeared in N updates | people tone | outlet tone):"]
    for e in s["top_stories"]:
        lines.append(f"[{e['key']}] {e['title']} | {e['theme']} | {e['runs']} updates | people {tone(e['public_sentiment'])} | outlets {tone(e['sentiment'])}")
        lines.append(f"    {e['summary'][:400]}")
        if e.get("public_reaction"):
            lines.append(f"    Reaction: {e['public_reaction'][:300]}")
        if e.get("flags"):
            lines.append(f"    Flags: {'; '.join(e['flags'])[:200]}")
    return "\n".join(lines)


def generate(cfg: dict, week: str, log=print) -> dict | None:
    """Write the digest for one week. Returns it, or None when the week has too little data."""
    import anthropic
    s = week_stats(cfg, week)
    if not s:
        log(f"  weekly {week}: fewer than {MIN_DAYS} days of data, skipped")
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()   # stripped, as pipeline.secret() does: a secret saved with a trailing newline breaks the request
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY secret is missing")
    client = anthropic.Anthropic(api_key=key)
    model = cfg.get("model", "claude-sonnet-5")
    resp = client.messages.create(model=model, max_tokens=8000, system=DIGEST_PROMPT,
                                  messages=[{"role": "user", "content": build_message(cfg, s)}],
                                  output_config={"effort": str(cfg.get("effort", "low")), "format": {"type": "json_schema", "schema": digest_schema()}})
    text = "".join(b.text for b in resp.content if b.type == "text")
    d = json.loads(text)
    keys = {e["key"] for e in s["top_stories"]}
    d["highlights"] = [h for h in d.get("highlights") or [] if h.get("key") in keys][:6]
    digest = {"week": week, "from": s["from"], "to": s["to"], "generated_at": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "model": model, "title": d["title"], "title_ar": d["title_ar"], "paragraphs": d["paragraphs"], "paragraphs_ar": d["paragraphs_ar"],
              "highlights": d["highlights"], "watch": d["watch"], "watch_ar": d["watch_ar"],
              "stats": {k: s[k] for k in ("days", "posts", "runs", "public_sentiment", "outlet_sentiment", "prev_public_sentiment", "themes", "events")},
              "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}}
    archive._save(WEEKLY_DATA / f"{week}.json", digest)
    index = [x for x in archive._load(WEEKLY_DATA / "index.json", []) if x.get("week") != week]
    index.append({"week": week, "from": s["from"], "to": s["to"], "title": digest["title"], "title_ar": digest["title_ar"],
                  "generated_at": digest["generated_at"], "paragraphs": digest["paragraphs"][:1], "paragraphs_ar": digest["paragraphs_ar"][:1]})
    index.sort(key=lambda x: x["week"])
    archive._save(WEEKLY_DATA / "index.json", index)
    pages.write_weekly_pages(cfg, digest)
    pages.write_weekly_listing(cfg, index)
    pages.write_feeds(cfg, index)
    log(f"  weekly {week}: digest written ({resp.usage.input_tokens}/{resp.usage.output_tokens} tokens)")
    return digest


def maybe_generate(cfg: dict, state: dict, log=print) -> bool:
    """After a run: if a new ISO week has begun since the last digest, write the digest of the week that ended.
    Never raises; a failure is logged and tried again on the next run."""
    today = dt.datetime.now(UTC).date()
    current = week_of(today)
    last = week_of(today - dt.timedelta(days=7))
    done = {x.get("week") for x in archive._load(WEEKLY_DATA / "index.json", [])}
    attempts = state.get("weekly_attempts") or {}
    if last in done or not cfg.get("weekly_digest", True) or int(attempts.get(last, 0)) >= 3:
        return False
    state["weekly_attempts"] = {last: int(attempts.get(last, 0)) + 1}   # up to three tries, on later runs
    try:
        return generate(cfg, last, log) is not None
    except Exception as e:  # noqa: BLE001
        log(f"  weekly {last}: failed ({e}); will retry on a later run")
        return False


def backfill(cfg: dict, log=print) -> int:
    """Digests for every complete past week with enough data that has none yet."""
    days = archive.all_days()
    if not days:
        return 0
    first, today = dt.date.fromisoformat(days[0]), dt.datetime.now(UTC).date()
    done = {x.get("week") for x in archive._load(WEEKLY_DATA / "index.json", [])}
    n, d = 0, first
    while True:
        week = week_of(d)
        _, end = week_range(week)
        if dt.date.fromisoformat(end) >= today:
            break
        if week not in done and generate(cfg, week, log):
            n += 1
        d = dt.date.fromisoformat(end) + dt.timedelta(days=1)
    return n


if __name__ == "__main__":
    import pipeline as P
    print(f"{backfill(P.load_config())} digests written.")
