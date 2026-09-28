#!/usr/bin/env python3
"""
Permanent archive, downloads and methodology files for the Syria Narrative Tracker.

  data/archive/YYYY-MM-DD.json   every run of that day in full, plus that day's outlet headlines. Never deleted.
  data/archive/index.json        one summary per day: volume and tone overall, per theme, per language, per source type
  data/exports/YYYY-MM/*         flat tables for spreadsheets and R/Python (runs, stories, themes, headlines) + stories.json
  data/exports/index.json        the list of export files, with sizes and row counts
  data/methodology.json          sources, themes, sampling settings, model, the exact analysis instructions, changelog

Used by scripts/pipeline.py. Nothing here reads the network or calls Claude.
Posts by individuals are never stored: the archive holds analyses and outlet headlines only.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
EXPORTS = DATA / "exports"
UTC = dt.timezone.utc

LANGS = ["ar", "ku", "en"]
KINDS = [
    {"id": "official", "label": "Official and state", "label_ar": "رسمية وحكومية"},
    {"id": "independent", "label": "Independent and opposition-origin", "label_ar": "مستقلة ومعارضة سابقاً"},
    {"id": "kurdish", "label": "Kurdish-run and north-east", "label_ar": "كردية وشمال شرق سوريا"},
    {"id": "regional", "label": "Regional outlets", "label_ar": "إقليمية"},
    {"id": "aggregator", "label": "News aggregators", "label_ar": "مجمّعات أخبار"},
]
KIND_IDS = [k["id"] for k in KINDS]


# ----------------------------------------------------------------- small helpers

def _load(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _mean(pairs: list) -> float | None:
    """Weighted mean of (value, weight) pairs; None when there is nothing to average."""
    pairs = [(v, w) for v, w in pairs if v is not None and w]
    total = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / total, 3) if total else None


def theme_catalog(cfg: dict) -> list:
    out = []
    for t in cfg.get("themes") or []:
        if t.get("id"):
            out.append({"id": str(t["id"]), "label": str(t.get("label", t["id"])), "label_ar": str(t.get("label_ar", "")),
                        "about": str(t.get("about", "")), "about_ar": str(t.get("about_ar", ""))})
    if not any(t["id"] == "other" for t in out):
        out.append({"id": "other", "label": "Other", "label_ar": "أخرى", "about": "Anything that fits no theme above."})
    return out


def story_key(narrative: dict) -> str:
    """A permanent name for a story: the day it was first seen plus its id. Story ids are reused by the
    analysis while a story is ongoing, and the date keeps two different stories with the same id apart."""
    return f"{str(narrative.get('first_seen', ''))[:10]}-{narrative['id']}"


# ----------------------------------------------------------------- daily archive

def day_path(date: str) -> pathlib.Path:
    return ARCHIVE / f"{date}.json"


def load_day(date: str) -> dict:
    return _load(day_path(date), {"date": date, "runs": [], "headlines": []})


def run_record(latest: dict) -> dict:
    """What the archive keeps about one run: the full analysis plus how it was made."""
    keep = ("format", "generated_at", "window_hours", "model", "stats", "overall", "narratives", "cost_usd")
    rec = {k: latest[k] for k in keep if k in latest}
    rec["sources"] = [{"name": s["name"], "platform": s["platform"], "ok": bool(s.get("ok")),
                       "fetched": int(s.get("fetched") or 0)} for s in latest.get("sources") or []]
    return rec


def add_run(latest: dict) -> str:
    """Append this run to its day's archive file. Returns the day (YYYY-MM-DD)."""
    date = str(latest["generated_at"])[:10]
    day = load_day(date)
    rec = run_record(latest)
    day["runs"] = [r for r in day["runs"] if r.get("generated_at") != rec["generated_at"]] + [rec]
    day["runs"].sort(key=lambda r: r.get("generated_at", ""))
    _save(day_path(date), day)
    return date


def add_headlines(posts: list) -> list:
    """Store outlet posts (never individuals' posts) in the archive of the day they were published.
    Returns the days that changed."""
    items = []
    for p in posts:
        if p.get("voice") != "outlet" or not p.get("time"):
            continue
        items.append({"id": p["id"], "t": p["time"].strftime("%Y-%m-%dT%H:%M:%SZ"), "s": p["source"], "k": p.get("kind", ""),
                      "u": p["url"] if str(p.get("url", "")).startswith("https://") else "", "l": p.get("lang", ""),
                      "x": str(p["text"])[:300]})
    return merge_headlines(items)


def merge_headlines(items: list) -> list:
    """Merge headline records (the data/headlines.json shape) into their days' archive files, by id."""
    by_day = defaultdict(list)
    for h in items:
        if h.get("id") and h.get("t"):
            by_day[str(h["t"])[:10]].append(h)
    changed = []
    for date, day_items in by_day.items():
        day = load_day(date)
        have = {h["id"] for h in day["headlines"]}
        new = [h for h in day_items if h["id"] not in have]
        if new:
            day["headlines"] = sorted(day["headlines"] + new, key=lambda h: h["t"])
            _save(day_path(date), day)
            changed.append(date)
    return changed


def all_days() -> list:
    return sorted(p.stem for p in ARCHIVE.glob("????-??-??.json"))


# ----------------------------------------------------------------- per-day index for the trend views

def day_summary(day: dict, theme_ids: list) -> dict:
    runs = day.get("runs") or []
    out = {"date": day["date"], "runs": len(runs), "posts": 0, "public_posts": 0, "outlet_posts": 0,
           "unique_posts": 0, "stories": 0, "cost_usd": 0.0, "languages": defaultdict(int), "platforms": defaultdict(int),
           "headlines": len(day.get("headlines") or []),
           "public_sentiment": None, "outlet_sentiment": None, "public_tone": {}, "outlet_tone": {}, "themes": {}}
    pub_s, out_s = [], []
    pub_tone = {l: [] for l in LANGS}
    out_tone = {k: [] for k in KIND_IDS}
    themes: dict = defaultdict(lambda: {"share": [], "volume": 0, "public_volume": 0, "stories": set(),
                                        "pub": [], "out": [], "pub_tone": {l: [] for l in LANGS},
                                        "out_tone": {k: [] for k in KIND_IDS}})
    for r in runs:
        st = r.get("stats") or {}
        ov = r.get("overall") or {}
        out["posts"] += int(st.get("posts_analyzed") or 0)
        out["public_posts"] += int(st.get("public_posts") or 0)
        out["outlet_posts"] += int(st.get("outlet_posts") or 0)
        out["unique_posts"] += int(st.get("unique_posts") or 0)
        out["cost_usd"] += float(r.get("cost_usd") or 0)
        for k, v in (st.get("languages") or {}).items():
            out["languages"][k] += int(v)
        for k, v in (st.get("platforms") or {}).items():
            out["platforms"][k] += int(v)
        pub_s.append((ov.get("public_sentiment"), st.get("public_posts") or 1))
        out_s.append((ov.get("sentiment"), st.get("outlet_posts") or 1))
        run_share: dict = defaultdict(float)
        for n in r.get("narratives") or []:
            out["stories"] += 1
            theme = n.get("theme") if n.get("theme") in theme_ids else "other"
            vol, pvol = int(n.get("volume") or 0), int(n.get("public_volume") or 0)
            t = themes[theme]
            run_share[theme] += float(n.get("share") or 0)
            t["volume"] += vol
            t["public_volume"] += pvol
            t["stories"].add(n.get("key") or story_key(n))
            t["pub"].append((n.get("public_sentiment"), pvol))
            t["out"].append((n.get("sentiment"), vol - pvol))
            plang = n.get("public_languages") or {}
            for l, v in (n.get("public_tone") or {}).items():
                if l in LANGS:
                    w = int(plang.get(l) or (n.get("languages") or {}).get(l) or 0)
                    t["pub_tone"][l].append((v, w))
                    pub_tone[l].append((v, w))
            kinds = n.get("kinds") or {}
            for k, v in (n.get("outlet_tone") or {}).items():
                if k in KIND_IDS:
                    w = int(kinds.get(k) or 0)
                    t["out_tone"][k].append((v, w))
                    out_tone[k].append((v, w))
        for theme, s in run_share.items():
            themes[theme]["share"].append(s)
    out["public_sentiment"] = _mean(pub_s)
    out["outlet_sentiment"] = _mean(out_s)
    out["public_tone"] = {l: _mean(v) for l, v in pub_tone.items() if _mean(v) is not None}
    out["outlet_tone"] = {k: _mean(v) for k, v in out_tone.items() if _mean(v) is not None}
    for theme, t in themes.items():
        out["themes"][theme] = {
            "share": round(sum(t["share"]) / len(runs), 3) if runs else 0,   # mean share of discussion per run
            "volume": t["volume"], "public_volume": t["public_volume"], "stories": len(t["stories"]),
            "public_sentiment": _mean(t["pub"]), "outlet_sentiment": _mean(t["out"]),
            "public_tone": {l: _mean(v) for l, v in t["pub_tone"].items() if _mean(v) is not None},
            "outlet_tone": {k: _mean(v) for k, v in t["out_tone"].items() if _mean(v) is not None},
        }
    out["languages"], out["platforms"] = dict(out["languages"]), dict(out["platforms"])
    out["cost_usd"] = round(out["cost_usd"], 4)
    return out


def update_index(cfg: dict, dates: list | None = None) -> dict:
    """Recompute the per-day summaries for the given days (all days when None) and rewrite index.json."""
    path = ARCHIVE / "index.json"
    index = _load(path, {})
    themes = theme_catalog(cfg)
    theme_ids = [t["id"] for t in themes]
    days = {d["date"]: d for d in index.get("days") or []}
    for date in (dates if dates is not None else all_days()):
        if day_path(date).exists():
            days[date] = day_summary(load_day(date), theme_ids)
    ordered = [days[d] for d in sorted(days)]
    index = {
        "updated": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_day": ordered[0]["date"] if ordered else None,
        "last_day": ordered[-1]["date"] if ordered else None,
        "themes": [{k: t[k] for k in ("id", "label", "label_ar")} for t in themes],
        "kinds": KINDS,
        "languages": [{"id": "ar", "label": "Arabic", "label_ar": "العربية"}, {"id": "ku", "label": "Kurdish", "label_ar": "الكردية"},
                      {"id": "en", "label": "English", "label_ar": "الإنجليزية"}],
        "events": [{"date": str(e.get("date"))[:10], "label": str(e.get("label", "")), "label_ar": str(e.get("label_ar", ""))}
                   for e in (cfg.get("events") or []) if e.get("date")],
        "days": ordered,
    }
    _save(path, index)
    return index


# ----------------------------------------------------------------- monthly exports

RUN_COLS = ["run_time", "posts_analyzed", "public_posts", "outlet_posts", "unique_posts", "stories",
            "public_sentiment", "outlet_sentiment", "public_mood", "outlet_mood",
            "lang_ar", "lang_ku", "lang_en", "lang_other", "model", "cost_usd"]
STORY_COLS = ["run_time", "story_key", "story_id", "theme", "title", "title_ar", "share", "volume", "public_volume",
              "outlet_sentiment", "public_sentiment", "emotions", "framings", "flags", "sources", "platforms", "languages",
              *[f"public_tone_{l}" for l in LANGS], *[f"outlet_tone_{k}" for k in KIND_IDS],
              "first_seen", "summary", "summary_ar", "public_reaction", "public_reaction_ar"]
THEME_COLS = ["run_time", "theme", "stories", "share", "volume", "public_volume", "public_sentiment", "outlet_sentiment",
              *[f"public_tone_{l}" for l in LANGS], *[f"outlet_tone_{k}" for k in KIND_IDS]]
HEADLINE_COLS = ["time", "source", "kind", "language", "text", "url"]


def _join(v) -> str:
    return "; ".join(str(x) for x in v) if isinstance(v, list) else ""


def _kv(d: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in sorted((d or {}).items()))


def _csv(rows: list, cols: list) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
    return buf.getvalue()


def month_rows(month: str, theme_ids: list) -> dict:
    """Flat rows for one month (YYYY-MM) from the daily archive files."""
    runs, stories, themes, heads, index = [], [], [], [], {}
    for date in all_days():
        if not date.startswith(month):
            continue
        day = load_day(date)
        for r in day.get("runs") or []:
            st, ov, t = r.get("stats") or {}, r.get("overall") or {}, r.get("generated_at")
            langs = st.get("languages") or {}
            runs.append({"run_time": t, "posts_analyzed": st.get("posts_analyzed"), "public_posts": st.get("public_posts"),
                         "outlet_posts": st.get("outlet_posts"), "unique_posts": st.get("unique_posts"),
                         "stories": len(r.get("narratives") or []),
                         "public_sentiment": ov.get("public_sentiment"), "outlet_sentiment": ov.get("sentiment"),
                         "public_mood": ov.get("public_mood"), "outlet_mood": ov.get("mood"),
                         "lang_ar": langs.get("ar", 0), "lang_ku": langs.get("ku", 0), "lang_en": langs.get("en", 0),
                         "lang_other": langs.get("other", 0), "model": r.get("model"), "cost_usd": r.get("cost_usd")})
            per_theme: dict = defaultdict(lambda: {"stories": 0, "share": 0.0, "volume": 0, "public_volume": 0,
                                                   "pub": [], "out": [], "pt": {l: [] for l in LANGS}, "ot": {k: [] for k in KIND_IDS}})
            for n in r.get("narratives") or []:
                theme = n.get("theme") if n.get("theme") in theme_ids else "other"
                key = n.get("key") or story_key(n)
                vol, pvol = int(n.get("volume") or 0), int(n.get("public_volume") or 0)
                row = {"run_time": t, "story_key": key, "story_id": n.get("id"), "theme": theme, "title": n.get("title"),
                       "title_ar": n.get("title_ar"), "share": n.get("share"), "volume": vol, "public_volume": pvol,
                       "outlet_sentiment": n.get("sentiment"), "public_sentiment": n.get("public_sentiment"),
                       "emotions": _join(n.get("emotions")), "framings": _join(n.get("framings")), "flags": _join(n.get("flags")),
                       "sources": _join(n.get("sources")), "platforms": _kv(n.get("platforms")), "languages": _kv(n.get("languages")),
                       "first_seen": n.get("first_seen"), "summary": n.get("summary"), "summary_ar": n.get("summary_ar"),
                       "public_reaction": n.get("public_reaction"), "public_reaction_ar": n.get("public_reaction_ar")}
                for l in LANGS:
                    row[f"public_tone_{l}"] = (n.get("public_tone") or {}).get(l)
                for k in KIND_IDS:
                    row[f"outlet_tone_{k}"] = (n.get("outlet_tone") or {}).get(k)
                stories.append(row)
                e = index.setdefault(key, {"runs": []})
                e["story"] = n
                tone = n.get("public_sentiment") if n.get("public_sentiment") is not None else n.get("sentiment")
                e["runs"].append([t, n.get("share", 0), tone])
                pt = per_theme[theme]
                pt["stories"] += 1
                pt["share"] += float(n.get("share") or 0)
                pt["volume"] += vol
                pt["public_volume"] += pvol
                pt["pub"].append((n.get("public_sentiment"), pvol))
                pt["out"].append((n.get("sentiment"), vol - pvol))
                plang = n.get("public_languages") or {}
                for l, v in (n.get("public_tone") or {}).items():
                    if l in LANGS:
                        pt["pt"][l].append((v, int(plang.get(l) or (n.get("languages") or {}).get(l) or 0)))
                for k, v in (n.get("outlet_tone") or {}).items():
                    if k in KIND_IDS:
                        pt["ot"][k].append((v, int((n.get("kinds") or {}).get(k) or 0)))
            for theme, pt in per_theme.items():
                row = {"run_time": t, "theme": theme, "stories": pt["stories"], "share": round(pt["share"], 3),
                       "volume": pt["volume"], "public_volume": pt["public_volume"],
                       "public_sentiment": _mean(pt["pub"]), "outlet_sentiment": _mean(pt["out"])}
                for l in LANGS:
                    row[f"public_tone_{l}"] = _mean(pt["pt"][l])
                for k in KIND_IDS:
                    row[f"outlet_tone_{k}"] = _mean(pt["ot"][k])
                themes.append(row)
        for h in day.get("headlines") or []:
            heads.append({"time": h.get("t"), "source": h.get("s"), "kind": h.get("k"), "language": h.get("l"),
                          "text": h.get("x"), "url": h.get("u")})
    story_index = sorted(({**e["story"], "key": k, "runs": e["runs"], "first_run": e["runs"][0][0], "last_run": e["runs"][-1][0]}
                          for k, e in index.items()), key=lambda s: s["last_run"], reverse=True)
    return {"runs": runs, "stories": stories, "themes": themes, "headlines": heads, "story_index": story_index}


def write_exports(cfg: dict, months: list) -> None:
    theme_ids = [t["id"] for t in theme_catalog(cfg)]
    for month in months:
        rows = month_rows(month, theme_ids)
        folder = EXPORTS / month
        if not rows["runs"] and not rows["headlines"]:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        # utf-8-sig so Excel opens Arabic correctly; pandas/R read it with encoding="utf-8-sig"
        (folder / "runs.csv").write_text(_csv(rows["runs"], RUN_COLS), encoding="utf-8-sig")
        (folder / "stories.csv").write_text(_csv(rows["stories"], STORY_COLS), encoding="utf-8-sig")
        (folder / "themes.csv").write_text(_csv(rows["themes"], THEME_COLS), encoding="utf-8-sig")
        (folder / "headlines.csv").write_text(_csv(rows["headlines"], HEADLINE_COLS), encoding="utf-8-sig")
        _save(folder / "stories.json", rows["story_index"])
    write_exports_index()


def write_exports_index() -> None:
    months = []
    for folder in sorted(p for p in EXPORTS.glob("????-??") if p.is_dir()):
        files = []
        for f in sorted(folder.iterdir()):
            if f.suffix not in (".csv", ".json"):
                continue
            rows = None
            if f.suffix == ".csv":
                rows = max(0, f.read_text(encoding="utf-8-sig").count("\n") - 1)
            elif f.name == "stories.json":
                rows = len(_load(f, []))
            files.append({"name": f.name, "path": f"data/exports/{folder.name}/{f.name}", "bytes": f.stat().st_size, "rows": rows})
        months.append({"month": folder.name, "files": files})
    days = [{"date": d, "path": f"data/archive/{d}.json", "bytes": day_path(d).stat().st_size} for d in all_days()]
    _save(EXPORTS / "index.json", {"updated": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   "licence": "CC BY 4.0", "months": months, "days": days,
                                   "columns": {"runs.csv": RUN_COLS, "stories.csv": STORY_COLS,
                                               "themes.csv": THEME_COLS, "headlines.csv": HEADLINE_COLS}})


# ----------------------------------------------------------------- methodology

def source_catalog(cfg: dict) -> list:
    out = []
    for ch in cfg.get("telegram_channels") or []:
        out.append({"label": ch.get("label") or ch["name"], "label_ar": ch.get("label_ar", ""), "kind": ch.get("kind", ""),
                    "platform": "telegram", "ref": f"https://t.me/s/{str(ch['name']).lstrip('@')}",
                    "filter": bool(ch.get("filter")), "comments": bool(ch.get("comments", True))})
    for fd in cfg.get("rss_feeds") or []:
        out.append({"label": fd.get("label") or fd["url"], "label_ar": fd.get("label_ar", ""), "kind": fd.get("kind", ""),
                    "platform": "news", "ref": fd["url"], "filter": bool(fd.get("filter"))})
    yt = cfg.get("youtube") or {}
    if yt.get("enabled"):
        out.append({"label": "YouTube comments", "label_ar": "تعليقات يوتيوب", "kind": "public", "platform": "youtube",
                    "ref": "", "detail": f"comments on recent videos found by searching: {', '.join(yt.get('search_terms') or [])}"})
    rd = cfg.get("reddit") or {}
    for fd in (rd.get("feeds") or []) if rd.get("enabled") else []:
        out.append({"label": fd.get("label") or f"Reddit r/{fd['subreddit']}", "label_ar": fd.get("label_ar", ""), "kind": "public",
                    "platform": "reddit", "ref": f"https://www.reddit.com/r/{str(fd['subreddit']).removeprefix('r/')}/",
                    "filter": bool(fd.get("filter"))})
    xc = cfg.get("x_twitter") or {}
    if xc.get("enabled"):
        out.append({"label": "X posts", "label_ar": "منشورات X", "kind": "public", "platform": "x", "ref": "",
                    "detail": f"most-engaged recent posts matching: {xc.get('query', '')}"})
    bs = cfg.get("bluesky") or {}
    if bs.get("enabled"):
        out.append({"label": "Bluesky posts", "label_ar": "منشورات بلوسكاي", "kind": "public", "platform": "bluesky", "ref": "",
                    "detail": f"recent posts matching: {', '.join(bs.get('search_terms') or [])}"})
    tga = cfg.get("telegram_api") or {}
    if tga.get("enabled"):
        out.append({"label": "Telegram comments and reactions", "label_ar": "تعليقات تيليغرام وتفاعلاته", "kind": "public",
                    "platform": "telegram_comments", "ref": "",
                    "detail": "comments and emoji reactions under the posts of the Telegram channels above (once the Telegram login is added)"})
        for g in tga.get("groups") or []:
            out.append({"label": f"Group: {g.get('label') or g['name']}", "label_ar": g.get("label_ar", ""), "kind": "public",
                        "platform": "telegram_groups", "ref": f"https://t.me/{str(g['name']).lstrip('@')}"})
    return out


def write_methodology(cfg: dict, prompt: str, format_version: int) -> dict:
    m = {
        "updated": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "format": format_version,
        "model": cfg.get("model"),
        "doi": str(cfg.get("doi") or ""),
        "site_url": str(cfg.get("site_url") or ""),
        "sampling": {"window_hours": cfg.get("window_hours", 24), "max_posts": cfg.get("max_posts", 150),
                     "public_share": cfg.get("public_share", 0.7), "max_chars_per_post": cfg.get("max_chars_per_post", 400),
                     "history_hours": cfg.get("history_hours", 336), "headline_days": cfg.get("headline_days", 7)},
        "keywords": cfg.get("keywords") or [],
        "themes": theme_catalog(cfg),
        "kinds": KINDS,
        "sources": source_catalog(cfg),
        "prompt": prompt,
        "changelog": [{"date": str(c.get("date"))[:10], "note": str(c.get("note", "")), "note_ar": str(c.get("note_ar", ""))}
                      for c in (cfg.get("method_changelog") or []) if c.get("date")],
        "events": [{"date": str(e.get("date"))[:10], "label": str(e.get("label", "")), "label_ar": str(e.get("label_ar", ""))}
                   for e in (cfg.get("events") or []) if e.get("date")],
    }
    _save(DATA / "methodology.json", m)
    return m
