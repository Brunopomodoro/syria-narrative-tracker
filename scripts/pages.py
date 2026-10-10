#!/usr/bin/env python3
"""
Static pages for the Syria Narrative Tracker, written by the pipeline after every run:

  stories/en/<key>.html, stories/ar/<key>.html   a permanent page per story, with its full latest analysis and its history
  stories/en/index.html, stories/ar/index.html   the recent stories, by day
  weekly/en/<week>.html, weekly/ar/<week>.html   the weekly digests (text from scripts/weekly.py)
  feed.xml, feed-ar.xml                          RSS feeds of the weekly digests
  sitemap.xml, robots.txt                        for search engines
  index.html                                     the crawlable block between <!--prerender--> and <!--/prerender-->

Everything here is plain HTML built from the data files; nothing calls the network or Claude.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
from collections import defaultdict

import archive

ROOT = archive.ROOT
DATA = archive.DATA
STORIES = ROOT / "stories"
WEEKLY = ROOT / "weekly"
MONTHLY = ROOT / "monthly"
STORY_INDEX = STORIES / "index.json"
UTC = dt.timezone.utc
LANGS = ("en", "ar")
MONTHS_AR = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

W = {   # the words on the static pages
    "en": {"tracker": "Tracker", "trends": "Trends", "data": "Data", "about": "About", "switch": "العربية",
           "people": "People", "outlets": "Outlets", "reacting": "How people are reacting", "framed": "How it's framed", "watch": "Watch for:",
           "sigTitle": "Signs of coordination:", "sigLevels": {"none": "none", "low": "weak", "medium": "moderate", "high": "strong"},
           "sigNote": "Measured signals, not proof: real breaking news, popular slogans and a few devoted commenters produce them too. The About page explains each one.",
           "where": "Sources", "overtime": "Over time", "update": "Update", "share": "Share of discussion", "firstSeen": "First seen", "lastSeen": "Last seen",
           "updates": "updates", "update1": "update", "story": "Story", "theme": "Theme", "emotions": "Emotions", "listing": "Stories", "listingSub": "Every story the tracker has followed in the last 30 days, by the day it was last seen. Older stories are in the downloads on the Data page.",
           "allStories": "All recent stories", "digest": "Weekly digest", "digests": "Weekly digests", "week": "Week", "highlights": "The week's stories", "watchNext": "What to watch",
           "themeTable": "Themes this week", "dailyTone": "Tone by day", "stories": "Stories", "posts": "Posts analysed", "vsLast": "vs last week",
           "postsNote": "Each update analyses a sample of up to {n} posts from the previous {h} hours, so one post can be counted in several updates. Compare days with each other rather than reading the figures as numbers of posts.",
           "note": "Written automatically by an AI model from the week's public posts. It describes what was said, not what is true.",
           "storyNote": "Analysis generated automatically by an AI model from public posts. It describes what is being said, not what is true. Individuals are never named, quoted or linked.",
           "tone": ["Strongly negative", "Leaning negative", "Mostly neutral", "Leaning positive", "Strongly positive", "No reactions yet"],
           "footer": "Summaries are written automatically by an AI model from public posts. They describe what is being said, not what is true.",
           "feedTitle": "Syria Narrative Tracker: weekly digest", "feedDesc": "A weekly written summary of what is being said about Syria online.",
           "review": "Monthly review", "reviews": "Monthly reviews", "month": "Month", "monthHighlights": "The month's stories", "watchMonth": "What to watch next month",
           "weeksBrief": "The weeks in brief", "flaggedTitle": "Stories that carried signs of coordination", "themeTableMonth": "Themes this month", "vsLastMonth": "vs last month",
           "weeklyTone": "Tone by week", "weekCol": "Week", "daysCol": "Days", "readOnline": "Read online", "subscribe": "Subscribe by email", "level": "Level",
           "monthNote": "Written automatically by an AI model from the month's public posts and the tracker's weekly digests. It describes what was said, not what is true.",
           "feedTitleMonthly": "Syria Narrative Tracker: monthly review", "feedDescMonthly": "A monthly written review of what is being said about Syria online: what moved, who said what, and the stories that mattered.",
           "prerender": "What people are talking about", "moreStories": "More stories", "readMore": "Read the analysis", "seenIn": "seen in"},
    "ar": {"tracker": "المتتبّع", "trends": "الاتجاهات", "data": "البيانات", "about": "حول الموقع", "switch": "English",
           "people": "الناس", "outlets": "وسائل الإعلام", "reacting": "كيف يتفاعل الناس", "framed": "كيف تُقدَّم القصة", "watch": "انتبه إلى:",
           "sigTitle": "مؤشرات التنسيق:", "sigLevels": {"none": "لا شيء", "low": "ضعيفة", "medium": "متوسطة", "high": "قوية"},
           "sigNote": "مؤشرات مقيسة لا أدلة: الأخبار العاجلة الحقيقية والشعارات الشائعة وقلة من المعلّقين المتحمسين تنتجها أيضاً. تشرح صفحة «حول» كل مؤشر.",
           "where": "المصادر", "overtime": "مع الوقت", "update": "التحديث", "share": "الحصة من النقاش", "firstSeen": "أول ظهور", "lastSeen": "آخر ظهور",
           "updates": "تحديثاً", "update1": "تحديث واحد", "story": "قصة", "theme": "الموضوع", "emotions": "المشاعر", "listing": "القصص", "listingSub": "كل قصة تابعها المتتبّع خلال آخر ٣٠ يوماً، حسب يوم آخر ظهور لها. القصص الأقدم في ملفات التنزيل على صفحة البيانات.",
           "allStories": "كل القصص الحديثة", "digest": "الملخص الأسبوعي", "digests": "الملخصات الأسبوعية", "week": "الأسبوع", "highlights": "قصص الأسبوع", "watchNext": "ما يجب متابعته",
           "themeTable": "مواضيع هذا الأسبوع", "dailyTone": "النبرة حسب اليوم", "stories": "القصص", "posts": "المنشورات المحلَّلة", "vsLast": "مقارنة بالأسبوع الماضي",
           "postsNote": "يحلّل كل تحديث عيّنة تصل إلى {n} منشور من الساعات الـ{h} السابقة، لذا قد يُحتسب المنشور الواحد في أكثر من تحديث. قارن الأيام ببعضها بدلاً من قراءة الأرقام كأعداد منشورات.",
           "note": "كُتب تلقائياً بواسطة نموذج ذكاء اصطناعي من منشورات الأسبوع العامة، ويصف ما قيل لا ما هو صحيح.",
           "storyNote": "تحليل مولَّد تلقائياً بواسطة نموذج ذكاء اصطناعي من منشورات عامة، يصف ما يُقال لا ما هو صحيح. لا يُذكر الأفراد ولا يُقتبس كلامهم ولا تُربط منشوراتهم.",
           "tone": ["سلبي جداً", "يميل إلى السلبية", "محايد غالباً", "يميل إلى الإيجابية", "إيجابي جداً", "لا تفاعل بعد"],
           "footer": "تُكتب الملخصات تلقائياً بواسطة نموذج ذكاء اصطناعي انطلاقاً من منشورات عامة، وهي تصف ما يُقال، لا ما هو صحيح.",
           "feedTitle": "متتبّع السرديات السورية: الملخص الأسبوعي", "feedDesc": "ملخص مكتوب أسبوعياً لما يُقال عن سوريا على الإنترنت.",
           "review": "المراجعة الشهرية", "reviews": "المراجعات الشهرية", "month": "الشهر", "monthHighlights": "قصص الشهر", "watchMonth": "ما يجب متابعته الشهر المقبل",
           "weeksBrief": "الأسابيع باختصار", "flaggedTitle": "قصص حملت مؤشرات تنسيق", "themeTableMonth": "مواضيع هذا الشهر", "vsLastMonth": "مقارنة بالشهر الماضي",
           "weeklyTone": "النبرة حسب الأسبوع", "weekCol": "الأسبوع", "daysCol": "الأيام", "readOnline": "اقرأ على الموقع", "subscribe": "اشترك بالبريد الإلكتروني", "level": "المستوى",
           "monthNote": "كُتبت تلقائياً بواسطة نموذج ذكاء اصطناعي من منشورات الشهر العامة ومن الملخصات الأسبوعية للمتتبّع، وتصف ما قيل لا ما هو صحيح.",
           "feedTitleMonthly": "متتبّع السرديات السورية: المراجعة الشهرية", "feedDescMonthly": "مراجعة مكتوبة شهرياً لما يُقال عن سوريا على الإنترنت: ما الذي تغيّر، ومن قال ماذا، والقصص التي كانت الأهم.",
           "prerender": "ما الذي يتحدث عنه الناس", "moreStories": "المزيد من القصص", "readMore": "اقرأ التحليل", "seenIn": "ظهرت في"},
}

CSS = """
:root{--paper:#F3F5F2;--ink:#1D262B;--muted:#5B666A;--faint:#9AA3A6;--rule:#D6DCD8;--wash:#E9EEEA;--neg:#A3303C;--neu:#A7ABA3;--pos:#2C7663;--brass:#8A6420;
--sans:"IBM Plex Sans","IBM Plex Sans Arabic",system-ui,sans-serif;--display:"IBM Plex Serif","Noto Naskh Arabic",Georgia,serif}
@media (prefers-color-scheme:dark){:root{--paper:#172024;--ink:#E7ECE8;--muted:#A1ACAF;--faint:#6B777B;--rule:#2C383D;--wash:#1E292E;--neg:#D8606B;--neu:#6F7670;--pos:#4FAE94;--brass:#D2A95A}}
html[lang=ar]{--sans:"IBM Plex Sans Arabic","IBM Plex Sans",system-ui,sans-serif;--display:"Noto Naskh Arabic","IBM Plex Sans Arabic",serif}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 var(--sans)}html[lang=ar] body{font-size:18px;line-height:1.8}
a{color:inherit;text-decoration-color:var(--brass);text-underline-offset:3px}a:hover{color:var(--brass)}
.wrap{max-width:760px;margin:0 auto;padding:0 20px 40px}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;padding:22px 0 18px;border-bottom:1px solid var(--rule);margin-bottom:34px}
.top .brand{font-weight:600;font-size:1rem;text-decoration:none}.top nav{display:flex;gap:18px;color:var(--muted);font-size:.88rem;flex-wrap:wrap}.top nav a{text-decoration:none}
.top .lang{border:1px solid var(--rule);border-radius:999px;padding:2px 12px;color:var(--ink)}
.eyebrow{color:var(--muted);font-size:.9rem;margin:0 0 10px}h1{font-family:var(--display);font-weight:600;font-size:1.9rem;line-height:1.25;margin:0 0 14px}
h2{font-family:var(--display);font-weight:600;font-size:1.25rem;margin:34px 0 10px}p{margin:0 0 14px;max-width:68ch}.sub{color:var(--muted);font-size:.9rem}
.tone{display:flex;gap:18px 28px;flex-wrap:wrap;margin:0 0 22px;color:var(--muted);font-size:.92rem}.tone i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:7px;vertical-align:middle}
.tone i.o{background:transparent;border:1.5px solid var(--ink)}.tone b{color:var(--ink);font-weight:500}
.reaction{border-inline-start:3px solid var(--neu);padding:6px 16px;margin:0 0 18px}.reaction p{margin:0}
ul{padding-inline-start:20px}li{margin-bottom:6px}.flag{color:var(--brass);font-size:.95rem}
.signals{margin:14px 0 18px;padding:10px 14px;border-inline-start:3px solid var(--faint);background:var(--wash);border-radius:0 6px 6px 0;font-size:.92rem}html[dir="rtl"] .signals{border-radius:6px 0 0 6px}.signals.medium{border-color:var(--brass)}.signals.high{border-color:var(--neg)}.signals p{margin:0}.signals ul{margin:6px 0 0}.signals .sub{margin-top:8px;font-size:.82rem}
.tw{overflow-x:auto;max-width:100%;margin:6px 0 18px}table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{text-align:start;padding:7px 12px 7px 0;border-bottom:1px solid var(--rule);vertical-align:top}th{color:var(--muted);font-weight:500}
td.n{font-variant-numeric:tabular-nums;white-space:nowrap}.bar{position:relative;height:10px;background:var(--wash);border-radius:3px;min-width:80px}.bar i{position:absolute;inset-inline-start:0;top:0;height:100%;background:var(--brass);border-radius:3px;opacity:.85}
.day{margin:22px 0 6px;font-weight:500;color:var(--muted);font-size:.9rem}.list{list-style:none;padding:0}.list li{padding:8px 0;border-top:1px solid var(--rule);margin:0}.list .meta{display:block;color:var(--muted);font-size:.85rem}
.chip{display:inline-block;border:1px solid var(--rule);border-radius:999px;padding:1px 10px;font-size:.82rem;color:var(--muted);margin-inline-end:8px}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--rule);color:var(--muted);font-size:.85rem}
"""

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400;500;600&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=Noto+Naskh+Arabic:wght@500;600;700&display=swap" rel="stylesheet">'
CSP = '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'none\'; style-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src \'self\' data:; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'


# ----------------------------------------------------------------- helpers

def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def site_url(cfg: dict) -> str:
    u = str(cfg.get("site_url") or "").strip()
    if not u:
        cname = ROOT / "CNAME"
        if cname.exists():
            u = "https://" + cname.read_text(encoding="utf-8").strip()
    return u.rstrip("/")


def site_title(cfg: dict, lang: str) -> str:
    return str(cfg.get("site_title_ar") if lang == "ar" else cfg.get("site_title")) or "Syria Narrative Tracker"


def ar_digits(s: str) -> str:
    return s.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def fmt_date(iso: str, lang: str, time: bool = False) -> str:
    d = archive_parse(iso)
    if not d:
        return str(iso or "")
    if lang == "ar":
        out = f"{d.day} {MONTHS_AR[d.month - 1]} {d.year}"
        if time:
            out += f"، {d.strftime('%H:%M')} UTC"
        return ar_digits(out)
    out = f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"
    return out + (f", {d.strftime('%H:%M')} UTC" if time else "")


def archive_parse(iso: str):
    try:
        s = str(iso)
        if len(s) == 10:
            return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def num(v, lang: str) -> str:
    s = f"{v:,}" if isinstance(v, int) else str(v)
    return ar_digits(s.replace(",", "٬")) if lang == "ar" else s


def pct(v, lang: str) -> str:
    return (ar_digits(str(round((v or 0) * 100))) + "٪") if lang == "ar" else f"{round((v or 0) * 100)}%"


def signed(v, lang: str) -> str:
    s = f"{v:+.2f}"
    return ar_digits(s.replace(".", "٫")) if lang == "ar" else s


def pts(v, lang: str) -> str:
    """A change in share, in percentage points."""
    s = f"{round(v * 100):+d}"
    return ar_digits(s) + " نقطة" if lang == "ar" else s + " pts"


def tone_label(v, lang: str) -> str:
    w = W[lang]["tone"]
    if v is None:
        return w[5]
    return w[0] if v <= -0.5 else w[1] if v <= -0.15 else w[2] if v < 0.15 else w[3] if v < 0.5 else w[4]


def tone_color(v) -> str:
    """The same neutral-to-red / neutral-to-green mix as the website."""
    v = max(-1.0, min(1.0, float(v or 0)))
    neu, neg, pos = (167, 171, 163), (163, 48, 60), (44, 118, 99)
    tgt, t = (neg, -v) if v < 0 else (pos, v)
    return "rgb(%d,%d,%d)" % tuple(round(a + (b - a) * t) for a, b in zip(neu, tgt))


def theme_label(cfg: dict, theme: str, lang: str) -> str:
    for t in archive.theme_catalog(cfg):
        if t["id"] == theme:
            return t["label_ar"] if lang == "ar" and t.get("label_ar") else t["label"]
    return theme


def t(n: dict, field: str, lang: str):
    """A text field in the page's language, falling back to the other language."""
    v = n.get(field + "_ar") if lang == "ar" else n.get(field)
    if v in (None, "", []):
        v = n.get(field) if lang == "ar" else n.get(field + "_ar")
    return v


# ----------------------------------------------------------------- the page frame

def page(cfg: dict, lang: str, title: str, description: str, body: str, path: str, alt_path: str, root: str = "../../",
         updated: str | None = None, kind: str = "article", image: str = "assets/og.png") -> str:
    w, base = W[lang], site_url(cfg)
    other = "en" if lang == "ar" else "ar"
    canonical = f"{base}/{path}" if base else path
    alt = f"{base}/{alt_path}" if base else root + alt_path
    og = f"""<meta property="og:type" content="{kind}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}"><meta property="og:locale" content="{'ar_SY' if lang == 'ar' else 'en_GB'}"><meta property="og:site_name" content="{esc(site_title(cfg, lang))}">
<meta property="og:image" content="{esc((base + '/' if base else root) + image)}"><meta name="twitter:card" content="summary_large_image">"""
    return f"""<!doctype html>
<html lang="{lang}" dir="{'rtl' if lang == 'ar' else 'ltr'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{CSP}
<meta name="referrer" content="no-referrer">
<title>{esc(title)} · {esc(site_title(cfg, lang))}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="alternate" hreflang="{lang}" href="{esc(canonical)}"><link rel="alternate" hreflang="{other}" href="{esc(alt)}">
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{esc(w['feedTitle'])}" href="{root}{'feed-ar.xml' if lang == 'ar' else 'feed.xml'}">
<link rel="alternate" type="application/rss+xml" title="{esc(w['feedTitleMonthly'])}" href="{root}{'feed-monthly-ar.xml' if lang == 'ar' else 'feed-monthly.xml'}">
{og}
{FONTS}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="top"><a class="brand" href="{root}{'?lang=ar' if lang == 'ar' else ''}">{esc(site_title(cfg, lang))}</a>
<nav><a href="{root}{'?lang=ar' if lang == 'ar' else ''}">{w['tracker']}</a><a href="{root}{'?lang=ar' if lang == 'ar' else ''}#trends">{w['trends']}</a><a href="{root}{'?lang=ar' if lang == 'ar' else ''}#data">{w['data']}</a><a href="{root}{'?lang=ar' if lang == 'ar' else ''}#about">{w['about']}</a><a class="lang" lang="{other}" href="{root}{alt_path}">{w['switch']}</a></nav></header>
<main>
{body}
</main>
<footer>{esc(w['footer'])}{(' · ' + esc(fmt_date(updated, lang, True))) if updated else ''}</footer>
</div>
</body>
</html>
"""


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------- stories

def load_story_index() -> dict:
    return archive._load(STORY_INDEX, {})


def update_story_index(latest: dict) -> dict:
    """One entry per story ever shown: titles, theme, first and last seen, how many updates it appeared in, last tones."""
    index = load_story_index()
    when = latest.get("generated_at", "")
    for n in latest.get("narratives") or []:
        key = n.get("key") or archive.story_key(n)
        e = index.setdefault(key, {"first_seen": n.get("first_seen", when), "runs": 0, "last_run": ""})
        e.update({"id": n["id"], "title": n.get("title", ""), "title_ar": n.get("title_ar", ""), "theme": n.get("theme", "other"),
                  "last_seen": when, "public_sentiment": n.get("public_sentiment"), "sentiment": n.get("sentiment"),
                  "share": n.get("share", 0)})
        if e.get("last_run") != when:
            e["runs"] = int(e.get("runs") or 0) + 1
            e["last_run"] = when
    archive._save(STORY_INDEX, index)
    return index


def story_runs(key: str, first_day: str, last_day: str, cache: dict) -> list:
    """Every run in which the story appeared, from the archive: [(time, share, public_sentiment, sentiment, volume)]."""
    out = []
    for date in archive.all_days():
        if date < first_day or date > last_day:
            continue
        day = cache.get(date) or cache.setdefault(date, archive.load_day(date))
        for r in day.get("runs") or []:
            for n in r.get("narratives") or []:
                if (n.get("key") or archive.story_key(n)) == key:
                    out.append((r.get("generated_at"), n.get("share", 0), n.get("public_sentiment"), n.get("sentiment"), n.get("volume", 0)))
    return out


def signal_value(i: dict, lang: str) -> str:
    """One signal's value in words (the same phrasing as the website)."""
    v, n = i.get("value"), i.get("n")
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if lang == "ar":
        return {"copies": f"{pct(v, lang)} من {num(n, lang)} منشوراً للناس تكرار حرفي",
                "near_copies": f"{pct(v, lang)} من {num(n, lang)} نصاً مميزاً شبه متطابقة",
                "burst": f"احتوت الساعة الأكثر نشاطاً على {num(v, lang)} أضعاف المتوسط الساعي ({num(n, lang)} منشوراً)",
                "burst_no_news": "لم تغطِّ أي وسيلة إعلام على القائمة القصة في تلك الساعة",
                "synchrony": f"ظهر {num(v, lang)} نصوص على منصات عدة خلال ساعة",
                "concentration": f"كتب أعلى ٥٪ من المعلّقين {pct(v, lang)} من {num(n, lang)} تعليقاً",
                "regularity": f"تتفاوت الفواصل بين التعليقات بنسبة {pct(v, lang)} فقط ({num(n, lang)} تعليقاً)"}.get(i.get("id"), str(v))
    return {"copies": f"{pct(v, lang)} of {num(n, lang)} public posts are exact repeats",
            "near_copies": f"{pct(v, lang)} of {num(n, lang)} distinct texts are near-identical",
            "burst": f"the busiest hour held {v}× the hourly average ({num(n, lang)} posts)",
            "burst_no_news": "no outlet on the list covered the story in that hour",
            "synchrony": f"{num(v, lang)} texts appeared on several platforms within an hour",
            "concentration": f"the top 5% of commenters wrote {pct(v, lang)} of {num(n, lang)} comments",
            "regularity": f"comment intervals vary by only {pct(v, lang)} ({num(n, lang)} comments)"}.get(i.get("id"), str(v))


def story_body(cfg: dict, n: dict, runs: list, lang: str, when: str) -> str:
    w = W[lang]
    key = n.get("key") or archive.story_key(n)
    theme = n.get("theme", "other")
    pub, out = n.get("public_sentiment"), n.get("sentiment")
    first = n.get("first_seen") or (runs[0][0] if runs else when)
    tone = f"""<div class="tone"><span><i style="background:{tone_color(pub) if pub is not None else 'var(--faint)'}"></i>{w['people']}: <b>{esc(tone_label(pub, lang))}</b>{(' (' + signed(pub, lang) + ')') if pub is not None else ''}</span>
<span><i class="o"></i>{w['outlets']}: <b>{esc(tone_label(out, lang))}</b> ({signed(out or 0, lang)})</span></div>"""
    n_runs = len(runs) or 1
    parts = [f"""<p class="eyebrow"><a href="index.html">{w['listing']}</a> · <a href="../../{'?lang=ar' if lang == 'ar' else ''}#trends">{esc(theme_label(cfg, theme, lang))}</a> · {w['firstSeen']} {esc(fmt_date(first, lang))} · {w['seenIn']} {num(n_runs, lang)} {w['update1'] if n_runs == 1 else w['updates']}</p>""",
             f"<h1>{esc(t(n, 'title', lang))}</h1>", tone, f"<p>{esc(t(n, 'summary', lang))}</p>"]
    reaction = t(n, "public_reaction", lang)
    if reaction:
        parts.append(f"""<h2>{w['reacting']}</h2><div class="reaction" style="border-color:{tone_color(pub) if pub is not None else 'var(--neu)'}"><p>{esc(reaction)}</p></div>""")
    emotions = t(n, "emotions", lang) or []
    if emotions:
        parts.append(f"<p class=\"sub\">{w['emotions']}: {esc(('، ' if lang == 'ar' else ', ').join(emotions))}</p>")
    framings = t(n, "framings", lang) or []
    if framings:
        parts.append(f"<h2>{w['framed']}</h2><ul>" + "".join(f"<li>{esc(f)}</li>" for f in framings) + "</ul>")
    flags = t(n, "flags", lang) or []
    if flags:
        parts.append(f"<p class=\"flag\">{w['watch']} {esc(('؛ ' if lang == 'ar' else '; ').join(flags))}</p>")
    sig = n.get("signals") or {}
    if sig.get("items"):
        import signals as SIG
        cat = {c["id"]: c for c in SIG.CATALOG}
        rows = "".join(f"<li><b>{esc(cat[i['id']]['label_ar' if lang == 'ar' else 'label'] if i['id'] in cat else i['id'])}</b> {esc(signal_value(i, lang))}</li>" for i in sig["items"])
        parts.append(f"<div class=\"signals {esc(sig.get('level', ''))}\"><p><b>{w['sigTitle']} {w['sigLevels'].get(sig.get('level'), '')}</b></p><ul>{rows}</ul><p class=\"sub\">{esc(w['sigNote'])}</p></div>")
    names = n.get("sources") or []
    links = [e for e in (n.get("examples") or []) if str(e.get("url", "")).startswith("https://")]
    if names or links:
        src = ", ".join(f'<a href="{esc(e["url"])}" rel="noopener nofollow">{esc(e["source"])}</a>' for e in links)
        rest = [s for s in names if s not in {e["source"] for e in links}]
        parts.append(f"<h2>{w['where']}</h2><p>{src}{(', ' if src and rest else '') + esc(', '.join(rest))}</p>")
    if runs:
        rows = "".join(f"<tr><td class=\"n\">{esc(fmt_date(r[0], lang, True))}</td><td class=\"n\">{pct(r[1], lang)}</td>"
                       f"<td class=\"n\">{signed(r[2], lang) if r[2] is not None else '–'}</td><td class=\"n\">{signed(r[3] or 0, lang)}</td></tr>"
                       for r in reversed(runs[-40:]))
        parts.append(f"<h2>{w['overtime']}</h2><div class=\"tw\"><table><thead><tr><th>{w['update']}</th><th>{w['share']}</th><th>{w['people']}</th><th>{w['outlets']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
    parts.append(f"<p class=\"sub\">{esc(w['storyNote'])}</p>")
    return "\n".join(parts)


def write_story_pages(cfg: dict, latest: dict, narratives: list | None = None, cache: dict | None = None) -> int:
    """Pages for the given stories (default: every story in latest). Returns how many were written."""
    cache = cache if cache is not None else {}
    when = latest.get("generated_at", "")
    today = when[:10]
    count = 0
    for n in narratives if narratives is not None else (latest.get("narratives") or []):
        key = n.get("key") or archive.story_key(n)
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+", key):
            continue
        runs = story_runs(key, key[:10], today, cache)
        for lang in LANGS:
            other = "ar" if lang == "en" else "en"
            body = story_body(cfg, n, runs, lang, when)
            desc = str(t(n, "summary", lang) or "")[:200]
            write(STORIES / lang / f"{key}.html",
                  page(cfg, lang, str(t(n, "title", lang) or key), desc, body, f"stories/{lang}/{key}.html", f"stories/{other}/{key}.html", updated=when))
        count += 1
    return count


def write_story_listing(cfg: dict, days: int = 30) -> None:
    index = load_story_index()
    cutoff = (dt.datetime.now(UTC) - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    recent = sorted((e for e in index.values() if str(e.get("last_seen", ""))[:10] >= cutoff), key=lambda e: (e.get("last_seen", ""), e.get("share", 0)), reverse=True)
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        by_day = defaultdict(list)
        for e in recent:
            by_day[str(e["last_seen"])[:10]].append(e)
        parts = [f"<h1>{w['listing']}</h1><p class=\"sub\">{esc(w['listingSub'])}</p>"]
        for day in sorted(by_day, reverse=True):
            items = "".join(
                f"""<li><a href="{esc(k)}.html">{esc(e['title_ar'] if lang == 'ar' and e.get('title_ar') else e['title'])}</a>
<span class="meta">{esc(theme_label(cfg, e.get('theme', 'other'), lang))} · {w['people']}: {esc(tone_label(e.get('public_sentiment'), lang))} · {w['outlets']}: {esc(tone_label(e.get('sentiment'), lang))} · {w['seenIn']} {num(int(e.get('runs') or 1), lang)} {w['updates']}</span></li>"""
                for k, e in ((archive_key(e), e) for e in by_day[day]))
            parts.append(f"<p class=\"day\">{esc(fmt_date(day, lang))}</p><ul class=\"list\">{items}</ul>")
        write(STORIES / lang / "index.html", page(cfg, lang, w["listing"], w["listingSub"], "\n".join(parts), f"stories/{lang}/index.html", f"stories/{other}/index.html", kind="website"))


def archive_key(e: dict) -> str:
    return f"{str(e.get('first_seen', ''))[:10]}-{e['id']}"


# ----------------------------------------------------------------- weekly digest pages and feeds

def weekly_body(cfg: dict, d: dict, lang: str) -> str:
    w, s = W[lang], d.get("stats") or {}
    paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or []
    parts = [f"<p class=\"eyebrow\"><a href=\"index.html\">{w['digests']}</a> · {w['week']} {esc(d['week'])} · {esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))}</p>",
             f"<h1>{esc(t(d, 'title', lang))}</h1>"]
    parts += [f"<p>{esc(p)}</p>" for p in paras]
    hl = d.get("highlights") or []
    if hl:
        items = []
        for h in hl:
            key = h.get("key") or ""
            title = esc(t(h, "title", lang))
            link = f'<a href="../../stories/{lang}/{esc(key)}.html">{title}</a>' if key else title
            items.append(f"<li><b>{link}</b>{(' — ' if lang == 'en' else ' ـ ')}{esc(t(h, 'why', lang))}</li>")
        parts.append(f"<h2>{w['highlights']}</h2><ul>{''.join(items)}</ul>")
    watch = d.get("watch_ar" if lang == "ar" else "watch") or []
    if watch:
        parts.append(f"<h2>{w['watchNext']}</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in watch) + "</ul>")
    themes = s.get("themes") or []
    if themes:
        mx = max([x.get("share", 0) for x in themes] + [0.05])
        rows = "".join(f"""<tr><td>{esc(theme_label(cfg, x['theme'], lang))}</td><td><div class="bar"><i style="width:{round(x.get('share', 0) / mx * 100)}%"></i></div></td>
<td class="n">{pct(x.get('share', 0), lang)}{(' <span class="sub">(' + pts(x['change'], lang) + ')</span>') if x.get('change') is not None else ''}</td>
<td class="n">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td><td class="n">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class="n">{num(int(x.get('stories') or 0), lang)}</td></tr>"""
                       for x in themes)
        parts.append(f"<h2>{w['themeTable']}</h2><div class=\"tw\"><table><thead><tr><th>{w['theme']}</th><th></th><th>{w['share']}</th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['stories']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
    days = s.get("days") or []
    if days:
        rows = "".join(f"<tr><td class=\"n\">{esc(fmt_date(x['date'], lang))}</td><td class=\"n\">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td>"
                       f"<td class=\"n\">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class=\"n\">{num(int(x.get('posts') or 0), lang)}</td></tr>" for x in days)
        parts.append(f"<h2>{w['dailyTone']}</h2><div class=\"tw\"><table><thead><tr><th></th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['posts']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
        parts.append(f"<p class=\"sub\">{esc(w['postsNote'].format(n=num(int(cfg.get('max_posts') or 300), lang), h=num(int(cfg.get('window_hours') or 24), lang)))}</p>")
    parts.append(f"<p class=\"sub\">{esc(w['note'])}</p>")
    return "\n".join(parts)


def write_weekly_pages(cfg: dict, digest: dict) -> None:
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        desc = (digest.get("paragraphs_ar" if lang == "ar" else "paragraphs") or [""])[0][:200]
        write(WEEKLY / lang / f"{digest['week']}.html",
              page(cfg, lang, str(t(digest, "title", lang)), desc, weekly_body(cfg, digest, lang),
                   f"weekly/{lang}/{digest['week']}.html", f"weekly/{other}/{digest['week']}.html", updated=digest.get("generated_at")))


def write_weekly_listing(cfg: dict, digests: list) -> None:
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        items = "".join(f"""<li><a href="{esc(d['week'])}.html">{esc(d['title_ar'] if lang == 'ar' and d.get('title_ar') else d['title'])}</a>
<span class="meta">{esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))}</span></li>""" for d in sorted(digests, key=lambda d: d["week"], reverse=True))
        write(WEEKLY / lang / "index.html", page(cfg, lang, w["digests"], w["feedDesc"], f"<h1>{w['digests']}</h1><ul class=\"list\">{items}</ul>",
                                                 f"weekly/{lang}/index.html", f"weekly/{other}/index.html", kind="website"))


def write_feeds(cfg: dict, digests: list) -> None:
    base = site_url(cfg)
    for lang in LANGS:
        w = W[lang]
        items = []
        for d in sorted(digests, key=lambda d: d["week"], reverse=True)[:52]:
            link = f"{base}/weekly/{lang}/{d['week']}.html"
            paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or []
            pub = archive_parse(d.get("generated_at") or d["to"]) or dt.datetime.now(UTC)
            items.append(f"""<item><title>{esc(d['title_ar'] if lang == 'ar' and d.get('title_ar') else d['title'])}</title><link>{esc(link)}</link><guid isPermaLink="true">{esc(link)}</guid>
<pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><description>{esc(' '.join(paras)[:1500])}</description></item>""")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>{esc(w['feedTitle'])}</title><link>{esc(base + '/')}</link>
<description>{esc(w['feedDesc'])}</description><language>{lang}</language><atom:link href="{esc(base + '/' + ('feed-ar.xml' if lang == 'ar' else 'feed.xml'))}" rel="self" type="application/rss+xml"/>
{''.join(items)}</channel></rss>
"""
        write(ROOT / ("feed-ar.xml" if lang == "ar" else "feed.xml"), xml)


# ----------------------------------------------------------------- monthly review pages and feeds

def fmt_month(month: str, lang: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return ar_digits(f"{MONTHS_AR[m - 1]} {y}") if lang == "ar" else f"{MONTHS_EN[m - 1]} {y}"


def subscribe_link(cfg: dict, lang: str) -> str:
    url = str(cfg.get("newsletter_url") or "").strip()
    return f'<p><a class="chip" href="{esc(url)}" rel="noopener">{W[lang]["subscribe"]}</a></p>' if url.startswith("https://") else ""


def monthly_sections(cfg: dict, d: dict, lang: str, base: str = "../../", absolute: str = "") -> list:
    """The review's sections as HTML; absolute links when a site address is given (for the feeds)."""
    w, s = W[lang], d.get("stats") or {}
    root = absolute + "/" if absolute else base
    parts = [f"<p>{esc(p)}</p>" for p in (d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or [])]
    hl = d.get("highlights") or []
    if hl:
        items = []
        for h in hl:
            key = h.get("key") or ""
            title = esc(t(h, "title", lang))
            link = f'<a href="{root}stories/{lang}/{esc(key)}.html">{title}</a>' if key else title
            items.append(f"<li><b>{link}</b>{(' — ' if lang == 'en' else ' ـ ')}{esc(t(h, 'why', lang))}</li>")
        parts.append(f"<h2>{w['monthHighlights']}</h2><ul>{''.join(items)}</ul>")
    watch = d.get("watch_ar" if lang == "ar" else "watch") or []
    if watch:
        parts.append(f"<h2>{w['watchMonth']}</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in watch) + "</ul>")
    digests = d.get("digests") or []
    if digests:
        items = []
        for x in digests:
            first = (x.get("paragraphs_ar" if lang == "ar" else "paragraphs") or x.get("paragraphs") or [""])[0]
            items.append(f'<li><b><a href="{root}weekly/{lang}/{esc(x["week"])}.html">{esc(t(x, "title", lang))}</a></b> '
                         f'<span class="sub">{esc(fmt_date(x.get("from", ""), lang))} – {esc(fmt_date(x.get("to", ""), lang))}</span>'
                         f'{("<br>" + esc(first)) if first else ""}</li>')
        parts.append(f"<h2>{w['weeksBrief']}</h2><ul>{''.join(items)}</ul>")
    flagged = d.get("flagged") or []
    if flagged:
        import signals as SIG
        cat = {c["id"]: c for c in SIG.CATALOG}
        items = []
        for e in flagged:
            sig = e.get("signals") or {}
            names = ", ".join(cat[i["id"]]["label_ar" if lang == "ar" else "label"] if i["id"] in cat else i["id"] for i in sig.get("items") or [])
            items.append(f'<li><b><a href="{root}stories/{lang}/{esc(e["key"])}.html">{esc(t(e, "title", lang))}</a></b> '
                         f'<span class="sub">{w["level"]}: {w["sigLevels"].get(sig.get("level"), "")}; {esc(names)}</span></li>')
        parts.append(f"<h2>{w['flaggedTitle']}</h2><ul>{''.join(items)}</ul><p class=\"sub\">{esc(w['sigNote'])}</p>")
    themes = s.get("themes") or []
    if themes:
        mx = max([x.get("share", 0) for x in themes] + [0.05])
        rows = "".join(f"""<tr><td>{esc(theme_label(cfg, x['theme'], lang))}</td><td><div class="bar"><i style="width:{round(x.get('share', 0) / mx * 100)}%"></i></div></td>
<td class="n">{pct(x.get('share', 0), lang)}{(' <span class="sub">(' + pts(x['change'], lang) + ')</span>') if x.get('change') is not None else ''}</td>
<td class="n">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td><td class="n">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class="n">{num(int(x.get('stories') or 0), lang)}</td></tr>"""
                       for x in themes)
        change_note = f" <span class=\"sub\">({w['vsLastMonth']})</span>" if any(x.get("change") is not None for x in themes) else ""
        parts.append(f"<h2>{w['themeTableMonth']}</h2><div class=\"tw\"><table><thead><tr><th>{w['theme']}</th><th></th><th>{w['share']}{change_note}</th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['stories']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
    weeks = s.get("weeks") or []
    if weeks:
        rows = "".join(f"<tr><td class=\"n\">{esc(x['week'])}</td><td class=\"n\">{esc(fmt_date(x['from'], lang))} – {esc(fmt_date(x['to'], lang))}</td>"
                       f"<td class=\"n\">{signed(x['public_sentiment'], lang) if x.get('public_sentiment') is not None else '–'}</td>"
                       f"<td class=\"n\">{signed(x['outlet_sentiment'], lang) if x.get('outlet_sentiment') is not None else '–'}</td><td class=\"n\">{num(int(x.get('posts') or 0), lang)}</td></tr>" for x in weeks)
        parts.append(f"<h2>{w['weeklyTone']}</h2><div class=\"tw\"><table><thead><tr><th>{w['weekCol']}</th><th>{w['daysCol']}</th><th>{w['people']}</th><th>{w['outlets']}</th><th>{w['posts']}</th></tr></thead><tbody>{rows}</tbody></table></div>")
        parts.append(f"<p class=\"sub\">{esc(w['postsNote'].format(n=num(int(cfg.get('max_posts') or 300), lang), h=num(int(cfg.get('window_hours') or 24), lang)))}</p>")
    parts.append(f"<p class=\"sub\">{esc(w['monthNote'])}</p>")
    return parts


def monthly_body(cfg: dict, d: dict, lang: str) -> str:
    w = W[lang]
    head = [f"<p class=\"eyebrow\"><a href=\"index.html\">{w['reviews']}</a> · {esc(fmt_month(d['month'], lang))} · {esc(fmt_date(d['from'], lang))} – {esc(fmt_date(d['to'], lang))}</p>",
            f"<h1>{esc(t(d, 'title', lang))}</h1>", subscribe_link(cfg, lang)]
    return "\n".join(head + monthly_sections(cfg, d, lang))


def monthly_email_html(cfg: dict, d: dict, lang: str) -> str:
    """The whole review as self-contained HTML with absolute links, for the feed item (newsletter services send it as is)."""
    base, w = site_url(cfg), W[lang]
    link = f"{base}/monthly/{lang}/{d['month']}.html"
    body = "\n".join(monthly_sections(cfg, d, lang, absolute=base))
    body = body.replace('<div class="tw">', "").replace("</table></div>", "</table>")   # no scroll wrappers in email
    body = re.sub(r'<td><div class="bar">.*?</div></td>', "", body).replace("<th></th>", "")   # the bar column needs CSS; email clients have none
    body = body.replace("<table>", '<table cellpadding="6" style="border-collapse:collapse;font-size:14px">').replace("<th>", '<th align="left">')
    return (f'<div dir="{"rtl" if lang == "ar" else "ltr"}" lang="{lang}" style="font-family:system-ui,sans-serif;line-height:1.6">'
            f'<p style="color:#5B666A;font-size:14px">{esc(site_title(cfg, lang))} · {esc(fmt_month(d["month"], lang))} · <a href="{esc(link)}">{w["readOnline"]}</a></p>'
            f'<h1 style="font-size:24px;line-height:1.3">{esc(t(d, "title", lang))}</h1>{body}'
            f'<p style="color:#5B666A;font-size:13px"><a href="{esc(base)}/">{esc(site_title(cfg, lang))}</a> · {esc(w["footer"])}</p></div>')


def write_monthly_pages(cfg: dict, review: dict) -> None:
    for lang in LANGS:
        other = "ar" if lang == "en" else "en"
        desc = (review.get("paragraphs_ar" if lang == "ar" else "paragraphs") or [""])[0][:200]
        write(MONTHLY / lang / f"{review['month']}.html",
              page(cfg, lang, str(t(review, "title", lang)), desc, monthly_body(cfg, review, lang),
                   f"monthly/{lang}/{review['month']}.html", f"monthly/{other}/{review['month']}.html", updated=review.get("generated_at")))


def write_monthly_listing(cfg: dict, reviews: list) -> None:
    for lang in LANGS:
        w, other = W[lang], "ar" if lang == "en" else "en"
        items = "".join(f"""<li><a href="{esc(d['month'])}.html">{esc(d['title_ar'] if lang == 'ar' and d.get('title_ar') else d['title'])}</a>
<span class="meta">{esc(fmt_month(d['month'], lang))}</span></li>""" for d in sorted(reviews, key=lambda d: d["month"], reverse=True))
        feed = f'<p class="sub"><a href="../../{"feed-monthly-ar.xml" if lang == "ar" else "feed-monthly.xml"}">RSS</a></p>'
        write(MONTHLY / lang / "index.html", page(cfg, lang, w["reviews"], w["feedDescMonthly"],
                                                  f"<h1>{w['reviews']}</h1><p class=\"sub\">{esc(w['feedDescMonthly'])}</p>{subscribe_link(cfg, lang)}<ul class=\"list\">{items}</ul>{feed}",
                                                  f"monthly/{lang}/index.html", f"monthly/{other}/index.html", kind="website"))


def write_monthly_feeds(cfg: dict, reviews: list) -> None:
    """RSS with the full review in each item (content:encoded), so an RSS-to-email service can send it as a newsletter."""
    base = site_url(cfg)
    for lang in LANGS:
        w = W[lang]
        items = []
        for x in sorted(reviews, key=lambda d: d["month"], reverse=True)[:24]:
            d = archive._load(MONTHLY_DATA_DIR / f"{x['month']}.json", None) or x
            link = f"{base}/monthly/{lang}/{x['month']}.html"
            paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or []
            pub = archive_parse(x.get("generated_at") or x["to"]) or dt.datetime.now(UTC)
            full = monthly_email_html(cfg, d, lang) if d.get("stats") else " ".join(f"<p>{esc(p)}</p>" for p in paras)
            items.append(f"""<item><title>{esc(x['title_ar'] if lang == 'ar' and x.get('title_ar') else x['title'])}</title><link>{esc(link)}</link><guid isPermaLink="true">{esc(link)}</guid>
<pubDate>{pub.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><description>{esc(' '.join(paras[:2])[:1500])}</description>
<content:encoded><![CDATA[{full.replace(']]>', ']]&gt;')}]]></content:encoded></item>""")
        name = "feed-monthly-ar.xml" if lang == "ar" else "feed-monthly.xml"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>{esc(w['feedTitleMonthly'])}</title><link>{esc(base + '/')}</link>
<description>{esc(w['feedDescMonthly'])}</description><language>{lang}</language><atom:link href="{esc(base + '/' + name)}" rel="self" type="application/rss+xml"/>
{''.join(items)}</channel></rss>
"""
        write(ROOT / name, xml)


MONTHLY_DATA_DIR = DATA / "monthly"


def load_reviews() -> list:
    return archive._load(MONTHLY_DATA_DIR / "index.json", [])


# ----------------------------------------------------------------- sitemap, robots, prerender

def write_sitemap(cfg: dict, digests: list, reviews: list | None = None) -> None:
    base = site_url(cfg)
    if not base:
        return
    today = dt.datetime.now(UTC).strftime("%Y-%m-%d")
    urls = [(f"{base}/", today, "hourly", "1.0"), (f"{base}/?lang=ar", today, "hourly", "1.0"),
            (f"{base}/stories/en/index.html", today, "daily", "0.7"), (f"{base}/stories/ar/index.html", today, "daily", "0.7"),
            (f"{base}/weekly/en/index.html", today, "weekly", "0.6"), (f"{base}/weekly/ar/index.html", today, "weekly", "0.6"),
            (f"{base}/monthly/en/index.html", today, "monthly", "0.6"), (f"{base}/monthly/ar/index.html", today, "monthly", "0.6")]
    for key, e in load_story_index().items():
        for lang in LANGS:
            urls.append((f"{base}/stories/{lang}/{key}.html", str(e.get("last_seen", today))[:10], "daily", "0.6"))
    for d in digests:
        for lang in LANGS:
            urls.append((f"{base}/weekly/{lang}/{d['week']}.html", str(d.get("generated_at", today))[:10], "monthly", "0.6"))
    for d in reviews if reviews is not None else load_reviews():
        for lang in LANGS:
            urls.append((f"{base}/monthly/{lang}/{d['month']}.html", str(d.get("generated_at", today))[:10], "yearly", "0.7"))
    body = "".join(f"<url><loc>{esc(u)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>\n" for u, m, c, p in urls[:49000])
    write(ROOT / "sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n')
    write(ROOT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")


def prerender_index(cfg: dict, latest: dict) -> bool:
    """Write the current analysis into index.html as plain HTML, for crawlers and link previews; the site's
    script replaces it on load. Returns whether index.html changed."""
    path = ROOT / "index.html"
    html_text = path.read_text(encoding="utf-8")
    start, end = "<!--prerender-->", "<!--/prerender-->"
    if start not in html_text or end not in html_text:
        return False
    ov = latest.get("overall") or {}
    sections = []
    for lang in LANGS:
        w = W[lang]
        items = []
        for n in latest.get("narratives") or []:
            key = n.get("key") or archive.story_key(n)
            items.append(f"<li><a href=\"stories/{lang}/{esc(key)}.html\">{esc(t(n, 'title', lang))}</a> {esc(t(n, 'summary', lang))}</li>")
        mood = ov.get("public_mood_ar" if lang == "ar" else "public_mood") or ov.get("mood_ar" if lang == "ar" else "mood") or ""
        sections.append(f"""<section class="pre" lang="{lang}" dir="{'rtl' if lang == 'ar' else 'ltr'}"><h2>{w['prerender']} · {esc(fmt_date(latest.get('generated_at', ''), lang, True))}</h2>
<p><strong>{esc(mood)}</strong> {esc(t(ov, 'brief', lang))}</p><ul>{''.join(items)}</ul><p><a href="stories/{lang}/index.html">{w['moreStories']}</a> · <a href="weekly/{lang}/index.html">{w['digests']}</a> · <a href="monthly/{lang}/index.html">{w['reviews']}</a></p></section>""")
    block = start + "\n" + "\n".join(sections) + "\n" + end
    new = html_text[:html_text.index(start)] + block + html_text[html_text.index(end) + len(end):]
    if new != html_text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def load_digests() -> list:
    return archive._load(DATA / "weekly" / "index.json", [])


def publish(cfg: dict, latest: dict, narratives: list | None = None) -> None:
    """Everything the pipeline does after a run: story pages for the run's stories, listings, feeds, sitemap, prerender."""
    update_story_index(latest)
    write_story_pages(cfg, latest, narratives)
    write_story_listing(cfg)
    digests = load_digests()
    write_weekly_listing(cfg, digests)
    write_feeds(cfg, digests)
    reviews = load_reviews()
    write_monthly_listing(cfg, reviews)
    write_monthly_feeds(cfg, reviews)
    write_sitemap(cfg, digests, reviews)
    prerender_index(cfg, latest)
