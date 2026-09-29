"""
Coordination signals: measurable signs that the public reaction to a story may be organised
rather than spontaneous. Computed from the posts assigned to each story in one update.

Every signal has innocent explanations (breaking news causes bursts, prayers and slogans repeat,
a few devoted commenters can dominate a thread), so the output is a list of signals and a level
for a human to judge, never a verdict. Nothing here identifies anyone: commenter concentration is
counted from one-way hashes that live only in memory during the run.

Signals (id: what it measures):
  copies        share of the story's public posts that are exact repeats of another (texts of 40+ characters)
  near_copies   share of distinct public texts that are near-copies of another (word 3-gram Jaccard >= 0.6)
  burst         the busiest hour holds many times the story's average hourly volume of public posts
  burst_no_news a burst hour in which no outlet on the list published anything about the story
  synchrony     the same or near-same text appears on two or more platforms within one hour
  concentration a small share of commenters wrote a large share of the comments (hashed, never stored)
  regularity    comments arrive at unusually regular intervals
"""
from __future__ import annotations

import datetime as dt
import math
import re
from collections import Counter, defaultdict

MIN_TEXT = 40            # shorter texts (prayers, slogans, "🙏") are ignored by the copy signals
NEAR = 0.6               # Jaccard similarity of word 3-grams that counts as a near-copy

CATALOG = [
    {"id": "copies", "label": "Copy-paste posting", "label_ar": "نسخ ولصق",
     "about": "A large share of the public posts in this story are exact repeats of one another.",
     "about_ar": "حصة كبيرة من منشورات الناس في هذه القصة تكرار حرفي لبعضها.",
     "innocent": "Slogans, prayers and shared news snippets repeat naturally; the signal ignores texts under 40 characters.",
     "innocent_ar": "الشعارات والأدعية ومقاطع الأخبار المتداولة تتكرر طبيعياً؛ تتجاهل الإشارة النصوص الأقصر من 40 حرفاً."},
    {"id": "near_copies", "label": "Near-identical posts", "label_ar": "منشورات شبه متطابقة",
     "about": "Many distinct public posts differ from one another only by a few words, the usual shape of scripted posting.",
     "about_ar": "منشورات كثيرة لا تختلف عن بعضها إلا بكلمات قليلة، وهو الشكل المعتاد للمنشورات المكتوبة وفق نص جاهز.",
     "innocent": "Short comments built on a common phrase can look alike without any coordination.",
     "innocent_ar": "قد تتشابه التعليقات القصيرة المبنية على عبارة شائعة من دون أي تنسيق."},
    {"id": "burst", "label": "Sudden burst", "label_ar": "موجة مفاجئة",
     "about": "The busiest hour holds several times the story's average hourly volume of public posts.",
     "about_ar": "تحوي الساعة الأكثر نشاطاً أضعاف المتوسط الساعي لمنشورات الناس في هذه القصة.",
     "innocent": "Real breaking news causes bursts too; read it together with the other signals.",
     "innocent_ar": "الأخبار العاجلة الحقيقية تسبب موجات أيضاً؛ اقرأها مع الإشارات الأخرى."},
    {"id": "burst_no_news", "label": "Burst without news", "label_ar": "موجة بلا خبر",
     "about": "During the burst hour no outlet on the list published anything about the story, so the surge was not a reaction to fresh coverage.",
     "about_ar": "خلال ساعة الموجة لم تنشر أي وسيلة إعلام على القائمة شيئاً عن القصة، فالارتفاع لم يكن رد فعل على تغطية جديدة."},
    {"id": "synchrony", "label": "Same text on several platforms", "label_ar": "النص نفسه على منصات عدة",
     "about": "The same or near-same text appeared on two or more platforms within one hour.",
     "about_ar": "ظهر النص نفسه أو شبه نفسه على منصتين أو أكثر خلال ساعة واحدة."},
    {"id": "concentration", "label": "Few accounts, many comments", "label_ar": "حسابات قليلة وتعليقات كثيرة",
     "about": "A small share of commenters wrote a large share of the comments. Counted from one-way hashes that exist only during the run; no account is stored.",
     "about_ar": "حصة صغيرة من المعلّقين كتبت حصة كبيرة من التعليقات. تُحسب من بصمات أحادية الاتجاه لا توجد إلا أثناء التحديث؛ لا يُحفظ أي حساب.",
     "innocent": "A few devoted commenters can dominate any thread.",
     "innocent_ar": "قد يهيمن معلّقون قليلون متحمسون على أي نقاش."},
    {"id": "regularity", "label": "Regular timing", "label_ar": "توقيت منتظم",
     "about": "Comments arrived at unusually even intervals, as scheduled posting does.",
     "about_ar": "وصلت التعليقات على فترات منتظمة بشكل غير معتاد، كما يحدث في النشر المجدول."},
]
LEVELS = ["none", "low", "medium", "high"]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _shingles(text: str) -> set:
    w = _norm(text).split()
    if len(w) < 3:
        return {" ".join(w)} if w else set()
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _hour(t: dt.datetime) -> dt.datetime:
    return t.replace(minute=0, second=0, microsecond=0)


def _cv(values: list) -> float | None:
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    if m <= 0:
        return None
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values)) / m


def story_signals(posts: list) -> dict:
    """posts: the sampled posts assigned to one story (each with text, copies, time, platform, voice, who).
    Returns {"level": ..., "score": n, "items": [{"id", "value", "n"}]}."""
    public = [p for p in posts if p.get("voice") == "public"]
    items = []

    # 1. exact copies (from the duplicate merge done at collection time)
    long_public = [p for p in public if len(p.get("text") or "") >= MIN_TEXT]
    vol = sum(int(p.get("copies") or 1) for p in long_public)
    if vol >= 10:
        ratio = (vol - len(long_public)) / vol
        if ratio >= 0.3:
            items.append({"id": "copies", "value": round(ratio, 2), "n": vol})

    # 2. near-copies among distinct texts
    if len(long_public) >= 8:
        sh = [_shingles(p["text"]) for p in long_public]
        near = 0
        for i in range(len(sh)):
            if any(_jaccard(sh[i], sh[j]) >= NEAR for j in range(len(sh)) if j != i):
                near += 1
        ratio = near / len(sh)
        if ratio >= 0.25:
            items.append({"id": "near_copies", "value": round(ratio, 2), "n": len(sh)})

    # 3. burst: busiest hour against the mean of the hours with activity
    timed = [p for p in public if isinstance(p.get("time"), dt.datetime)]
    by_hour = Counter()
    for p in timed:
        by_hour[_hour(p["time"])] += int(p.get("copies") or 1)
    if by_hour and sum(by_hour.values()) >= 20:
        peak_hour, peak = by_hour.most_common(1)[0]
        mean = sum(by_hour.values()) / len(by_hour)
        if len(by_hour) >= 3 and peak >= 15 and peak / mean >= 4:
            items.append({"id": "burst", "value": round(peak / mean, 1), "n": peak})
            outlet_hours = {_hour(p["time"]) for p in posts if p.get("voice") != "public" and isinstance(p.get("time"), dt.datetime)}
            if peak_hour not in outlet_hours and (peak_hour - dt.timedelta(hours=1)) not in outlet_hours:
                items.append({"id": "burst_no_news", "value": 1, "n": peak})

    # 4. synchrony: same or near-same text on 2+ platforms within an hour
    if len(timed) >= 6:
        groups = defaultdict(list)
        for p in timed:
            if len(p.get("text") or "") >= MIN_TEXT:
                groups[_norm(p["text"])[:120]].append(p)
        keys = list(groups)
        sh = {k: _shingles(k) for k in keys}
        merged, used = [], set()
        for i, k in enumerate(keys):
            if k in used:
                continue
            bucket = list(groups[k]); used.add(k)
            for k2 in keys[i + 1:]:
                if k2 not in used and _jaccard(sh[k], sh[k2]) >= NEAR:
                    bucket += groups[k2]; used.add(k2)
            merged.append(bucket)
        sync = 0
        for bucket in merged:
            plats = {p["platform"] for p in bucket}
            if len(plats) >= 2:
                times = sorted(p["time"] for p in bucket)
                if (times[-1] - times[0]) <= dt.timedelta(hours=1):
                    sync += 1
        if sync >= 3:
            items.append({"id": "synchrony", "value": sync, "n": sync})

    # 5. concentration of commenters (hashed ids that exist only during the run)
    who = [p["who"] for p in public if p.get("who")]
    if len(who) >= 20:
        counts = Counter(who)
        top_n = max(1, math.ceil(len(counts) * 0.05))
        top_share = sum(c for _, c in counts.most_common(top_n)) / len(who)
        if top_share >= 0.4:
            items.append({"id": "concentration", "value": round(top_share, 2), "n": len(who)})

    # 6. regular timing of comments
    times = sorted(p["time"] for p in timed if p.get("platform") in ("telegram_comments", "telegram_groups", "youtube", "reddit"))
    if len(times) >= 10:
        gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:]) if (b - a).total_seconds() > 0]
        cv = _cv(gaps)
        if cv is not None and cv < 0.35 and len(gaps) >= 9:
            items.append({"id": "regularity", "value": round(cv, 2), "n": len(times)})

    score = len(items)
    strong = any(i["id"] == "copies" and i["value"] >= 0.6 for i in items) or any(i["id"] == "concentration" and i["value"] >= 0.7 for i in items)
    level = "high" if score >= 3 or strong else "medium" if score == 2 else "low" if score == 1 else "none"
    return {"level": level, "score": score, "items": items}


def attach(narratives: list, sample: list) -> None:
    """Adds "signals" to every narrative from the sampled posts assigned to it."""
    by_pid = {p["pid"]: p for p in sample if p.get("pid")}
    for n in narratives:
        posts = [by_pid[i] for i in n.get("post_pids") or [] if i in by_pid]
        n["signals"] = story_signals(posts) if posts else {"level": "none", "score": 0, "items": []}
        n.pop("post_pids", None)
