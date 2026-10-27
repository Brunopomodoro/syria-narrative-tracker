#!/usr/bin/env python3
"""Audience indicators from the archive: what the tracker's record of public posts and comments says about Syrian
media audiences (GUIDE.md, "Audience snapshot"). No call to Claude: everything is computed from the stories already
analysed, one entry per story and day (the day's last analysis of it).

  alignment   how close people's mood on a story is to the tone of each type of outlet covering it (state,
              independent Syrian, Arab and regional, Kurdish, international via Google News): a proxy for which
              outlets' framing audiences share, not a measure of trust itself
  doubt       the share of people's attention on stories where they voiced doubt about official or media accounts
  platforms   where reactions happen (video comments, text platforms, Telegram) and engagement per post, by topic
  fatigue     topics (and long-running stories) whose share of people's attention fell while outlets kept covering
              them, and the share of reactions carrying tiredness, resignation or numbness, week by week
  emotions    the emotions most present in people's reactions
  gaps        topics people talk about more (or less) than outlets cover them
  languages   attention and mood by language (Arabic, English, Kurdish), by topic
  weeks       the same signals week by week since the archive starts

Writes data/audience.json, and with --report the English report audience/en.html and its PDF audience/en.pdf.

Usage:  python scripts/audience.py [--report]
"""
import collections
import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pages  # noqa: E402

OUT = pages.DATA / "audience.json"
KINDS = {"official": "State media", "independent": "Independent and private Syrian outlets", "regional": "Arab and regional outlets",
         "kurdish": "Kurdish outlets", "aggregator": "International news (via Google News)"}
DOUBT = re.compile(r"skeptic|sceptic|doubt|distrust|mistrust|disbelie|not believ|conspirac|propaganda|fabricat|cover[- ]?up|"
                   r"question(?:s|ed|ing)?\s+(?:the\s+)?(?:official|government|state|authorit|narrative|account|version|claim)|"
                   r"mock(?:s|ed|ing|ery)?\s+(?:of\s+)?(?:the\s+)?(?:official|government|state|authorit|claim|promise)|"
                   r"dismiss(?:ed|ing)?\s+(?:the\s+)?(?:official|government)|suspicio", re.I)
TIRED = re.compile(r"fatigue|exhaust|weary|tired|resign|apath|numb|fatalis|helpless|despair|hopeless|futil", re.I)
NEUTRAL = 0.15


def direction(v: float) -> int:
    return -1 if v <= -NEUTRAL else 1 if v >= NEUTRAL else 0


def entries() -> list:
    """One entry per story and day: the day's last analysis of the story, with the day's sample size."""
    out = []
    for day in archive.all_days():
        runs = sorted(archive.load_day(day).get("runs") or [], key=lambda r: r.get("generated_at", ""))
        last = {}
        for r in runs:
            st = r.get("stats") or {}
            for n in r.get("narratives") or []:
                key = n.get("key") or archive.story_key(n)
                last[key] = (n, int(st.get("public_posts") or 0), int(st.get("outlet_posts") or 0))
        for key, (n, pub_total, out_total) in last.items():
            out.append({"day": day, "key": key, "n": n, "pub_total": pub_total, "out_total": out_total})
    return out


def wmean(pairs) -> float | None:
    pairs = [(v, w) for v, w in pairs if v is not None and w]
    total = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / total, 3) if total else None


def week_of(day: str) -> str:
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def compute(cfg: dict) -> dict:
    es = entries()
    days = sorted({e["day"] for e in es})
    theme = lambda e: e["n"].get("theme") or "other"  # noqa: E731
    pubv = lambda e: int(e["n"].get("public_volume") or 0)  # noqa: E731
    outv = lambda e: max(0, int(e["n"].get("volume") or 0) - pubv(e))  # noqa: E731

    # alignment of people's mood with each outlet type's tone, on the same stories
    align = {}
    for k, label in KINDS.items():
        rows = [(e["n"]["public_sentiment"], (e["n"].get("outlet_tone") or {}).get(k), pubv(e)) for e in es
                if e["n"].get("public_sentiment") is not None and isinstance((e["n"].get("outlet_tone") or {}).get(k), (int, float)) and pubv(e)]
        if len(rows) < 5:
            continue
        agree = sum(w for p, o, w in rows if direction(p) == direction(o)) / sum(w for _, _, w in rows)
        align[k] = {"label": label, "stories": len({(e["key"]) for e in es if (e["n"].get("outlet_tone") or {}).get(k) is not None}),
                    "people": wmean((p, w) for p, o, w in rows), "outlets": wmean((o, w) for p, o, w in rows),
                    "gap": wmean((abs(p - o), w) for p, o, w in rows), "agree": round(agree, 3),
                    "angrier": round(sum(w for p, o, w in rows if p < o - 0.1) / sum(w for _, _, w in rows), 3)}

    # doubt about official or media accounts
    pub_all = sum(pubv(e) for e in es) or 1
    doubt_e = [e for e in es if pubv(e) and DOUBT.search(str(e["n"].get("public_reaction") or ""))]
    doubt_share = sum(pubv(e) for e in doubt_e) / pub_all
    by_theme_doubt = {}
    for t in {theme(e) for e in es}:
        tot = sum(pubv(e) for e in es if theme(e) == t)
        if tot >= 50:
            by_theme_doubt[t] = round(sum(pubv(e) for e in doubt_e if theme(e) == t) / tot, 3)
    kind_mix = {}
    for label, group in (("doubt", doubt_e), ("other", [e for e in es if pubv(e) and e not in doubt_e])):
        c = collections.Counter()
        for e in group:
            c.update({k: v for k, v in (e["n"].get("kinds") or {}).items() if k in KINDS})
        total = sum(c.values()) or 1
        kind_mix[label] = {k: round(v / total, 3) for k, v in c.items()}

    # platforms and engagement
    plat = collections.Counter()
    plat_theme = collections.defaultdict(collections.Counter)
    eng_theme = collections.defaultdict(lambda: [0, 0])
    for e in es:
        p = e["n"].get("platforms") or {}
        plat.update(p)
        plat_theme[theme(e)].update(p)
        eng_theme[theme(e)][0] += int(e["n"].get("engagement") or 0)
        eng_theme[theme(e)][1] += int(e["n"].get("volume") or 0)
    ptotal = sum(plat.values()) or 1
    platforms = {k: round(v / ptotal, 3) for k, v in plat.most_common()}
    video_share = {t: round(c.get("youtube", 0) / (sum(c.values()) or 1), 3) for t, c in plat_theme.items() if sum(c.values()) >= 100}
    engagement = {t: round(a / b, 1) for t, (a, b) in eng_theme.items() if b >= 100}

    # fatigue: long-running stories
    by_key = collections.defaultdict(list)
    for e in es:
        by_key[e["key"]].append(e)
    fatigue = []
    for key, rows in by_key.items():
        rows.sort(key=lambda e: e["day"])
        if len({e["day"] for e in rows}) < 7:
            continue
        third = max(2, len(rows) // 3)
        share = lambda rs, f, tot: sum(f(e) / (e[tot] or 1) for e in rs) / len(rs)  # noqa: E731
        p0, p1 = share(rows[:third], pubv, "pub_total"), share(rows[-third:], pubv, "pub_total")
        o0, o1 = share(rows[:third], outv, "out_total"), share(rows[-third:], outv, "out_total")
        if p0 <= 0:
            continue
        n = rows[-1]["n"]
        fatigue.append({"key": key, "title": n.get("title"), "theme": theme(rows[-1]), "days": len({e["day"] for e in rows}),
                        "first": rows[0]["day"], "last": rows[-1]["day"],
                        "people_change": round(p1 / p0 - 1, 3), "outlet_change": round(o1 / o0 - 1, 3) if o0 > 0 else None})
    fatigue.sort(key=lambda f: f["people_change"])
    for f in fatigue:
        f["fatigue"] = f["people_change"] <= -0.3 and (f["outlet_change"] is None or f["outlet_change"] >= -0.1)

    # fatigue by topic: people's share of attention in the second half of the period against the first, beside
    # outlets' share of coverage (stories are often renamed from day to day, so topics are steadier than stories)
    half = days[len(days) // 2]
    topic_trend = {}
    for t in {theme(e) for e in es} - {"other"}:
        a, b = [e for e in es if e["day"] < half], [e for e in es if e["day"] >= half]
        sa = lambda rs, f: sum(f(e) for e in rs if theme(e) == t) / (sum(f(e) for e in rs) or 1)  # noqa: E731
        pa, pb, oa, ob = sa(a, pubv), sa(b, pubv), sa(a, outv), sa(b, outv)
        if pa + pb < 0.04:
            continue
        topic_trend[t] = {"people_before": round(pa, 3), "people_after": round(pb, 3), "outlets_before": round(oa, 3), "outlets_after": round(ob, 3),
                          "people_change": round(pb / pa - 1, 3) if pa else None, "outlet_change": round(ob / oa - 1, 3) if oa else None}
        tt = topic_trend[t]
        tt["fatigue"] = bool(tt["people_change"] is not None and tt["people_change"] <= -0.25 and (tt["outlet_change"] or 0) >= -0.1)

    # emotions in people's reactions
    emo = collections.Counter()
    for e in es:
        for x in e["n"].get("emotions") or []:
            emo[str(x).strip().lower()] += pubv(e)
    emo_total = sum(emo.values()) or 1
    emotions = {k: round(v / emo_total, 3) for k, v in emo.most_common(12)}

    # gaps: people's attention vs outlets' coverage by topic
    out_all = sum(outv(e) for e in es) or 1
    gaps = {}
    for t in {theme(e) for e in es} - {"other"}:
        ps, os_ = sum(pubv(e) for e in es if theme(e) == t) / pub_all, sum(outv(e) for e in es if theme(e) == t) / out_all
        gaps[t] = {"people": round(ps, 3), "outlets": round(os_, 3), "gap": round(ps - os_, 3)}

    # languages
    lang_theme = collections.defaultdict(lambda: collections.defaultdict(list))
    lang_att = collections.defaultdict(collections.Counter)
    for e in es:
        pl = e["n"].get("public_languages") or {}
        for lang, tone in (e["n"].get("public_tone") or {}).items():
            if isinstance(tone, (int, float)) and pl.get(lang):
                lang_theme[lang][theme(e)].append((tone, pl[lang]))
                lang_att[lang][theme(e)] += pl[lang]
    languages = {}
    for lang in ("ar", "en", "ku"):
        if lang not in lang_att:
            continue
        tot = sum(lang_att[lang].values()) or 1
        languages[lang] = {"posts": sum(lang_att[lang].values()),
                           "tone": wmean(x for v in lang_theme[lang].values() for x in v),
                           "topics": {t: {"share": round(c / tot, 3), "tone": wmean(lang_theme[lang][t])} for t, c in lang_att[lang].most_common(6)}}

    # weeks
    weeks = []
    for w in sorted({week_of(e["day"]) for e in es}):
        we = [e for e in es if week_of(e["day"]) == w]
        pw = sum(pubv(e) for e in we) or 1
        people = wmean((e["n"].get("public_sentiment"), pubv(e)) for e in we)
        tones = [(v, outv(e)) for e in we for v in [(lambda ot: sum(ot) / len(ot) if ot else None)([x for x in (e["n"].get("outlet_tone") or {}).values() if isinstance(x, (int, float))])]]
        weeks.append({"week": w, "days": len({e["day"] for e in we}), "partial": len({e["day"] for e in we}) < 5, "people": people, "outlets": wmean(tones),
                      "doubt": round(sum(pubv(e) for e in we if e in doubt_e) / pw, 3),
                      "tired": round(sum(pubv(e) for e in we if any(TIRED.search(str(x)) for x in e["n"].get("emotions") or [])) / pw, 3)})

    return {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "from": days[0], "to": days[-1],
            "days": len(days), "story_days": len(es), "stories": len(by_key), "public_posts": pub_all, "outlet_posts": out_all,
            "alignment": align, "doubt": {"share": round(doubt_share, 3), "by_theme": by_theme_doubt, "outlet_mix": kind_mix},
            "platforms": platforms, "video_share": video_share, "engagement": engagement,
            "fatigue": fatigue[:15], "topic_trend": topic_trend, "half": half, "emotions": emotions,
            "gaps": gaps, "languages": languages, "weeks": weeks}


def main() -> int:
    import pipeline as P
    cfg = P.load_config()
    data = compute(cfg)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(pages.ROOT)}: {data['stories']} stories over {data['days']} days.")
    if "--report" in sys.argv:
        import audience_report
        audience_report.write(cfg, data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
