#!/usr/bin/env python3
"""Posts the tracker's reports to its Facebook Page and its X account: yesterday's daily brief each morning, each
weekly digest and each monthly report once written. Runs after every update; each network does nothing until its
secrets exist.

Secrets (repository secrets, never in the code):
  Facebook  FB_PAGE_ID, FB_PAGE_TOKEN (a Page access token that never expires; see GUIDE.md) and, optionally,
            FB_APP_SECRET (adds appsecret_proof to every call).
  X         X_API_KEY, X_API_SECRET (the app's consumer keys) and X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET (the
            account's access token, made after the app was set to "Read and write").

What has been posted is recorded in data/social.json, so nothing goes out twice, and a post that fails is tried
again at the next update. At most `per_run` posts go out per update and network (monthly first, then weekly, then
daily), so a day with several reports spreads them out. Settings under `facebook:` and `x:` in config.yaml.

On X every post is paid for (much more when it carries a link), so posting keeps to a monthly budget in dollars
(`monthly_budget_usd`, with `cost_per_post_usd` and `cost_per_link_post_usd`). The reports come first; what the budget leaves after the reports still to come this month goes to story
posts: one story at a time, at the hours Syrians are most online (Damascus time), spread evenly over the rest of
the month. A story post is short enough to show in full in the timeline: what people say about the story and how they feel
compared with the media, the link to the story's page (`story_links: false` under `x:` leaves it out), and hashtags.

The words of each X post are written by Claude from the report's or story's own text, as a person would post it
(`rewrite: true` under `x:`; about a cent a post). The link and hashtags are added afterwards, and a draft that
brings in a number not in the material, is too long, or fails in any way is dropped for the plain format.

Usage:  python scripts/social.py              post what is due
        python scripts/social.py --dry-run    check the token and print what would be posted, post nothing
        python scripts/social.py --preview    print the latest daily, weekly and monthly posts, due or not
"""
import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import sys
import time
import urllib.parse

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import arabic  # noqa: E402
import archive  # noqa: E402
import hashtags  # noqa: E402
import pages  # noqa: E402
import pipeline as P  # noqa: E402

STATE = pages.DATA / "social.json"
GRAPH = "https://graph.facebook.com"

LABEL = {"daily": {"en": "Daily brief", "ar": "الموجز اليومي"},
         "weekly": {"en": "Weekly digest", "ar": "الملخص الأسبوعي"},
         "monthly": {"en": "Monthly report", "ar": "التقرير الشهري"}}
WORDS = {"en": {"stories": "Top stories", "findings": "Key findings", "read": "Read it in full", "pdf": "PDF",
                "people": "people", "outlets": "outlets"},
         "ar": {"stories": "أبرز القصص", "findings": "أبرز النتائج", "read": "اقرأه كاملاً", "pdf": "PDF",
                "people": "الناس", "outlets": "وسائل الإعلام"}}
NOTE = "ملخص آلي لما يُقال على الإنترنت، لا لما هو صحيح · An automatic summary of what is said online, not of what is true."


def settings(cfg: dict, network: str = "facebook") -> dict:
    s = {"enabled": True, "first_lang": "ar", "per_run": 1, "daily": True, "weekly": True, "monthly": True,
         "daily_after_utc": 4, "api_version": "", "languages": ["ar", "en"], "max_tags": 4,
         "stories_per_day": 0, "story_hours": [21, 14, 18], "utc_offset": 3, "feed_story_languages": ["ar"]}
    if network == "x":
        s.update({"per_run": 2, "max_tags": 3, "daily_languages": ["ar"], "monthly_budget_usd": 10, "cost_per_post_usd": 0.015,
                  "cost_per_link_post_usd": 0.20,
                  "stories": True, "story_language": "ar", "story_hours": [20, 13, 17, 22, 9], "utc_offset": 3,
                  "max_stories_per_day": 5, "story_gap_hours": 1.5, "story_repeat_hours": 48, "story_min_voices": 5,
                  "rewrite": True, "images": True, "link_in_reply": True})
    s.update(cfg.get(network) or {})
    return s


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- composing

def clip(text: str, limit: int) -> str:
    """Whole sentences up to about limit characters; a cut sentence ends with an ellipsis."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    out = ""
    for sentence in re.split(r"(?<=[.!?؟])\s+", text):
        if len(out) + len(sentence) + 1 > limit:
            break
        out = (out + " " + sentence).strip()
    if len(out) < limit * 0.6:      # a long sentence: cut it at a word instead of dropping it
        out = text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:،؛ —-") + "…"
    return out


def url(cfg: dict, path: str) -> str:
    return f"{pages.site_url(cfg)}/{path}"


def block(head: str, lead: str, list_title: str, items: list, link_label: str, link: str, extra: str = "") -> str:
    lines = [head, ""]
    if lead:
        lines += [lead, ""]
    if items:
        lines += [list_title + ":"] + [f"• {x}" for x in items] + [""]
    lines.append(f"{link_label}: {link}" + extra)
    return "\n".join(lines)


def tag_line(cfg: dict, themes: list, titles_by_lang: dict, order: list) -> str:
    tags, seen = [], set()
    for lang in order:
        for tag in hashtags.select(cfg, lang, themes, titles_by_lang.get(lang) or []):
            if tag.lower() not in seen:
                seen.add(tag.lower())
                tags.append(tag)
    return " ".join("#" + t for t in tags[:8])


def compose(cfg: dict, kind: str, ident: str) -> dict | None:
    """The post for one report: {"key", "message", "link"}; None when the report does not exist."""
    order = ["ar", "en"] if settings(cfg)["first_lang"] == "ar" else ["en", "ar"]
    blocks, titles, themes = [], {}, []
    if kind == "daily":
        s = pages.daily_summary(cfg, archive.load_day(ident))
        if not s or not s["stories"]:
            return None
        themes = [x["theme"] for x in s["themes"]]
        for lang in order:
            ov, w = s["overall"], WORDS[lang]
            mood = ov.get("public_mood_ar" if lang == "ar" else "public_mood") or ov.get("mood_ar" if lang == "ar" else "mood") or ""
            brief = clip(pages.t(ov, "brief", lang), 360)
            top = [str(pages.t(e, "title", lang)) for e in s["stories"][:3]]
            titles[lang] = [pages.t(e, "title", lang) for e in s["stories"]]
            blocks.append(block(f"{LABEL['daily'][lang]} · {pages.fmt_date(ident, lang)}", (f"{mood}. " if mood else "") + brief,
                                w["stories"], top, w["read"], url(cfg, f"daily/{lang}/{ident}.html")))
    elif kind in ("weekly", "monthly"):
        d = archive._load(pages.DATA / kind / f"{ident}.json", None)
        if not d:
            return None
        themes = [x["theme"] for x in sorted((d.get("stats") or {}).get("themes") or [], key=lambda x: -x.get("share", 0))]
        for lang in order:
            w = WORDS[lang]
            titles[lang] = [pages.t(d, "title", lang)] + [pages.t(h, "title", lang) for h in d.get("highlights") or []]
            folder = "weekly" if kind == "weekly" else "monthly"
            pdf = f" ({w['pdf']}: {url(cfg, f'{folder}/{lang}/{ident}.pdf')})" if (pages.ROOT / folder / lang / f"{ident}.pdf").exists() else ""
            when = (f"{pages.fmt_date(d['from'], lang)} – {pages.fmt_date(d['to'], lang)}" if kind == "weekly" else pages.fmt_month(ident, lang))
            head = f"{LABEL[kind][lang]} · {when}\n{pages.t(d, 'title', lang)}"
            if kind == "monthly" and (d.get("key_findings_ar" if lang == "ar" else "key_findings") or d.get("key_findings")):
                items = [clip(x, 200) for x in (d.get("key_findings_ar" if lang == "ar" else "key_findings") or d.get("key_findings"))[:3]]
                blocks.append(block(head, "", w["findings"], items, w["read"], url(cfg, f"{folder}/{lang}/{ident}.html"), pdf))
            else:
                paras = d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or [""]
                top = [str(pages.t(h, "title", lang)) for h in (d.get("highlights") or [])[:3]]
                blocks.append(block(head, clip(paras[0], 420), w["stories"], top, w["read"], url(cfg, f"{folder}/{lang}/{ident}.html"), pdf))
    else:
        return None
    message = "\n\n· · ·\n\n".join(blocks) + "\n\n" + tag_line(cfg, themes, titles, order) + "\n\n" + NOTE
    first = order[0]
    link = url(cfg, {"daily": f"daily/{first}/{ident}.html", "weekly": f"weekly/{first}/{ident}.html", "monthly": f"monthly/{first}/{ident}.html"}[kind])
    return {"key": f"{kind}:{ident}", "message": message, "link": link}


# ---------------------------------------------------------------- X

X_API = "https://api.x.com/2"


def x_len(text: str) -> int:
    """A post's length as X counts it: a link counts 23, most letters (Latin, Arabic) 1, others (emoji, CJK) 2."""
    n = 0
    for part in re.split(r"(https?://\S+)", text):
        if part.startswith(("http://", "https://")):
            n += 23
            continue
        for ch in part:
            c = ord(ch)
            n += 1 if c <= 4351 or 8192 <= c <= 8205 or 8208 <= c <= 8223 or 8242 <= c <= 8247 else 2
    return n


CARD_WORDS = {"en": {"most": "Most discussed", "comments": "How Syrians reacted online"}, "ar": {"most": "الأكثر نقاشاً", "comments": "كيف تفاعل السوريون على الإنترنت"}}


def themes_line(cfg: dict, themes: list, lang: str) -> str:
    """"Most discussed: Society and daily life 15% · Israel and the south 9%" for a card."""
    top = [x for x in themes if x.get("theme") != "other" and x.get("share")][:3]
    return f"{CARD_WORDS[lang]['most']}: " + " · ".join(f"{pages.theme_label(cfg, x['theme'], lang)} {pages.pct(x['share'], lang)}" for x in top) if top else ""


def compose_x(cfg: dict, kind: str, ident: str, lang: str, state: dict | None = None) -> dict | None:
    """One post on X for a report in one language: the label and date, the headline (and, for the daily brief, the
    mood and as much of the brief as fits), the link and the hashtags that fit; at most 280 by X's count."""
    w = WORDS[lang]
    if kind == "daily":
        s = pages.daily_summary(cfg, archive.load_day(ident))
        if not s or not s["stories"]:
            return None
        ov = s["overall"]
        mood = ov.get("public_mood_ar" if lang == "ar" else "public_mood") or ov.get("mood_ar" if lang == "ar" else "mood") or ""
        head = f"{LABEL['daily'][lang]} · {pages.fmt_date(ident, lang)}"
        body = (f"{mood}. " if mood else "") + no_scores(pages.t(ov, "brief", lang))
        themes, titles = [x["theme"] for x in s["themes"]], [pages.t(e, "title", lang) for e in s["stories"]]
        link, lead = url(cfg, f"daily/{lang}/{ident}.html"), []
        card = {"eyebrow": head, "title": titles[0] if titles else "", "people": s.get("public_sentiment"), "media": s.get("outlet_sentiment"),
                "line": themes_line(cfg, s["themes"], lang)}
    elif kind in ("weekly", "monthly"):
        d = archive._load(pages.DATA / kind / f"{ident}.json", None)
        if not d:
            return None
        when = (f"{pages.fmt_date(d['from'], lang)} – {pages.fmt_date(d['to'], lang)}" if kind == "weekly" else pages.fmt_month(ident, lang))
        head = f"{LABEL[kind][lang]} · {when}\n{pages.t(d, 'title', lang)}"
        findings = d.get("key_findings_ar" if lang == "ar" else "key_findings") or d.get("key_findings") or []
        points = d.get("key_points_ar" if lang == "ar" else "key_points") or d.get("key_points") or []   # the weekly report's key points
        lead = [str(x) for x in (findings if kind == "monthly" else points) if not has_score(x) and not has_count(x)]   # no scores or counts on X
        body = lead[0] if lead else no_scores((d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or [""])[0])
        themes = [x["theme"] for x in sorted((d.get("stats") or {}).get("themes") or [], key=lambda x: -x.get("share", 0))]
        titles = [pages.t(d, "title", lang)] + [pages.t(h, "title", lang) for h in d.get("highlights") or []]
        link = url(cfg, f"{kind}/{lang}/{ident}.html")
        st = d.get("stats") or {}
        card = {"eyebrow": head.split("\n")[0], "title": pages.t(d, "title", lang), "people": st.get("public_sentiment"),
                "media": st.get("outlet_sentiment"), "line": themes_line(cfg, sorted(st.get("themes") or [], key=lambda x: -x.get("share", 0)), lang)}
    else:
        return None
    inline = not settings(cfg, "x").get("link_in_reply")      # otherwise the link goes in a reply, where it does not cut the reach
    shown = link if inline else ""
    tags = hashtags.select(cfg, lang, themes, titles)[: int(settings(cfg, "x").get("max_tags") or 4)]
    tag_text = lambda n: " ".join("#" + t for t in tags[:n])  # noqa: E731
    facts = {"what": LABEL[kind][lang], "period": head.split("\n")[0].split(" · ", 1)[-1], "headline": head.split("\n", 1)[-1] if "\n" in head else "",
             "main_point": body, "other_points": lead[1:3] if kind != "daily" else [],
             "top_stories": titles[1:4] if kind != "daily" else titles[:3]}
    joined = lambda wd, n: "\n\n".join([wd] + ([shown] if shown else []) + ([tag_text(n)] if n else []))  # noqa: E731
    words = rewrite(cfg, state, lang, facts, 280 - (23 if shown else 0) - x_len(tag_text(2)) - 6, lines=4)
    if words:
        n = len(tags)
        while n > 1 and x_len(joined(words, n)) > 280:
            n -= 1
        return {"key": f"{kind}:{ident}:{lang}", "text": joined(words, n), "words": words, "link": link, "card": card, "lang": lang}
    def build(text_body: str, n_tags: int) -> str:
        parts = [head] + ([text_body] if text_body else []) + ([shown] if shown else [])
        out = "\n\n".join(parts)
        return out + ("\n\n" + " ".join("#" + t for t in tags[:n_tags]) if n_tags else "")
    n_tags = len(tags)
    while n_tags > 2 and x_len(build("", n_tags)) > 200:      # keep room for words; at least the first two tags
        n_tags -= 1
    room = 280 - x_len(build("", n_tags)) - 2
    text_body = clip(body, room) if room > 40 else ""
    while text_body and x_len(build(text_body, n_tags)) > 280:
        text_body = clip(text_body, len(text_body) - 20) if len(text_body) > 60 else ""
    while n_tags and x_len(build(text_body, n_tags)) > 280:
        n_tags -= 1
    return {"key": f"{kind}:{ident}:{lang}", "text": build(text_body, n_tags), "link": link, "card": card, "lang": lang}


def oauth1_header(method: str, link: str, keys: dict, params: dict | None = None) -> str:
    """The OAuth 1.0a Authorization header (HMAC-SHA1) for a request made with the account's own access token."""
    enc = lambda v: urllib.parse.quote(str(v), safe="~-._")  # noqa: E731
    oauth = {"oauth_consumer_key": keys["api_key"], "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
             "oauth_timestamp": str(int(time.time())), "oauth_token": keys["token"], "oauth_version": "1.0"}
    oauth.update({k: v for k, v in (keys.get("_fixed") or {}).items()})          # tests only
    pairs = sorted((enc(k), enc(v)) for k, v in {**oauth, **(params or {})}.items())
    base = "&".join([method.upper(), enc(link), enc("&".join(f"{k}={v}" for k, v in pairs))])
    signing_key = f"{enc(keys['api_secret'])}&{enc(keys['token_secret'])}"
    oauth["oauth_signature"] = base64.b64encode(hmac.new(signing_key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(oauth.items()))


def x_call(method: str, path: str, keys: dict, body: dict | None = None) -> dict:
    link = f"{X_API}/{path}"
    r = requests.request(method, link, json=body, timeout=40, headers={"Authorization": oauth1_header(method, link, keys)})
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        detail = data.get("detail") or data.get("title") or (data.get("errors") or [{}])[0].get("message") or ""
        raise RuntimeError(f"X said: HTTP {r.status_code} {detail}".strip())
    return data


X_UPLOAD = "https://api.x.com/2/media/upload"
READ_MORE = {"en": "Full analysis", "ar": "التحليل الكامل"}


def x_upload(keys: dict, png: pathlib.Path) -> str:
    """Upload an image; returns its media id. Multipart: only the oauth_ parameters are signed."""
    with open(png, "rb") as fh:
        r = requests.post(X_UPLOAD, files={"media": (png.name, fh, "image/png")}, data={"media_category": "tweet_image", "media_type": "image/png"},
                          timeout=60, headers={"Authorization": oauth1_header("POST", X_UPLOAD, keys)})
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        detail = data.get("detail") or data.get("title") or (data.get("errors") or [{}])[0].get("message") or ""
        raise RuntimeError(f"X said: HTTP {r.status_code} {detail}".strip())
    mid = (data.get("data") or {}).get("id") or data.get("media_id_string")
    if not mid:
        raise RuntimeError("X gave no media id")
    return str(mid)


def card_image(cfg: dict, post: dict, keys: dict | None) -> str | None:
    """Draw the post's card and upload it; the media id, or None (no Chrome, no card, or the upload failed: the post
    then goes out without an image)."""
    if not settings(cfg, "x").get("images") or not post.get("card") or not keys:
        return None
    import tempfile
    import cards
    with tempfile.TemporaryDirectory() as tmp:
        png = pathlib.Path(tmp) / "card.png"
        if not cards.render(cfg, post["card"], post.get("lang") or "ar", png):
            print("X: the card was not drawn; the post goes out without an image.")
            return None
        try:
            return x_upload(keys, png)
        except Exception as e:  # noqa: BLE001
            print(f"X: the card was not uploaded ({x_explain(e)}); the post goes out without an image.")
            return None


def expected_cost(s: dict, post: dict) -> float:
    """The post, plus the reply that carries its link."""
    return post_cost(s, post["text"]) + (float(s["cost_per_link_post_usd"]) if s.get("link_in_reply") and post.get("link") else 0.0)


def publish(cfg: dict, keys: dict, post: dict) -> dict:
    """The post (with its card when there is one), then its link in a reply. Raises if the post fails; a failed reply
    is reported and the post kept. Returns {"id", "reply", "usd"}."""
    s = settings(cfg, "x")
    body = {"text": post["text"]}
    media = card_image(cfg, post, keys)
    if media:
        body["media"] = {"media_ids": [media]}
    pid = (x_call("POST", "tweets", keys, body).get("data") or {}).get("id")
    cost, reply = post_cost(s, post["text"]), None
    if s.get("link_in_reply") and post.get("link") and pid:
        try:
            text = f"{READ_MORE[post.get('lang') or 'ar']}: {post['link']}"
            reply = (x_call("POST", "tweets", keys, {"text": text, "reply": {"in_reply_to_tweet_id": pid}}).get("data") or {}).get("id")
            cost += post_cost(s, text)
        except Exception as e:  # noqa: BLE001
            print(f"X: the link reply to {pid} failed. {x_explain(e)}")
    return {"id": pid, "reply": reply, "usd": round(cost, 4), "image": bool(media)}


def x_explain(e: Exception) -> str:
    text = str(e)
    if "HTTP 401" in text:
        return text + ". The keys are wrong or were regenerated: copy all four again (GUIDE.md, Posting to X)."
    if "HTTP 402" in text or "Credits" in text:
        return text + ". The developer account has no credits left: add credits in the X Developer Console."
    if "HTTP 403" in text:
        return text + ". The app may be read-only: set it to Read and write, then regenerate the access token and secret."
    if "HTTP 429" in text:
        return text + ". Too many requests for now."
    return text


def x_keys() -> dict | None:
    keys = {"api_key": os.environ.get("X_API_KEY", "").strip(), "api_secret": os.environ.get("X_API_SECRET", "").strip(),
            "token": os.environ.get("X_ACCESS_TOKEN", "").strip(), "token_secret": os.environ.get("X_ACCESS_TOKEN_SECRET", "").strip()}
    return keys if all(keys.values()) else None


# ---------------------------------------------------------------- what is due

def latest(kind: str) -> dict | None:
    idx = archive._load(pages.DATA / kind / "index.json", []) or []
    return idx[-1] if idx else None


def due(cfg: dict, state: dict, now: dt.datetime, network: str = "facebook") -> list:
    """(kind, ident) of the reports to post now, in order: monthly, weekly, daily. Only recent reports count, so
    switching posting on does not post the whole archive, and a missed daily brief is not posted days late.
    On X each report is one post per language, so the items are (kind, ident, lang)."""
    s, posted = settings(cfg, network), (state.get(network) or {}).get("posted") or {}
    langs = [x for x in s["languages"] if x in ("ar", "en")] if network == "x" else [None]
    done = lambda kind, ident, lang: (f"{kind}:{ident}:{lang}" if lang else f"{kind}:{ident}") in posted  # noqa: E731
    out = []
    for kind, days in (("monthly", 20), ("weekly", 6)):
        item = latest(kind) if s[kind] else None
        if item:
            ident = item["month" if kind == "monthly" else "week"]
            made = archive_parse(item.get("generated_at"))
            if made and now - made < dt.timedelta(days=days):
                out += [(kind, ident, lang) for lang in langs if not done(kind, ident, lang)]
    if s["daily"] and now.hour >= int(s["daily_after_utc"]):
        yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
        if yesterday in archive.all_days():
            dlangs = [x for x in langs if x in s.get("daily_languages", langs)] if network == "x" else langs
            out += [("daily", yesterday, lang) for lang in dlangs if not done("daily", yesterday, lang)]
    return [x if network == "x" else x[:2] for x in out]


def archive_parse(iso: str | None) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- X: posts in a human voice

VOICE = """You write the posts of Syrian Pulse (syrianpulse.org) on {network}. The site reads public posts and comments about Syria
every few hours and reports what Syrians are saying online: the stories, the mood of ordinary people, and how it differs
from the media's. Write ONE post from the material below, the way a sharp, warm Syrian observer would post it: a person
talking to people, not a press release or a bot.

- Open with a hook: the most striking or human thing in the material, a contrast, or a short question. Never open with a
  label such as "Daily brief:" or "Story:".
- Plain, natural, specific words; short sentences; at most {lines} short lines in all.
- Arabic: simple Modern Standard Arabic, as a Syrian journalist writes on social media; no dialect words (no شو، فين،
  هيك، مو، كتير). English: plain international English; no slang (no folks, guys, gonna).
- End with a question only sometimes (about one post in three, and not when the recent posts did). A question must be
  open and neutral, never leading or implying blame (not "will this go unpunished?").
- Only what the material says. No new facts, names, numbers or causes. Every number you use must be in the material,
  written in digits, never in words (so it can be checked).
- Never use tone scores or the site's measures (numbers like -0.15 or +0.20, "points", "tone", "sentiment",
  "voices counted"): say the mood in plain words ("a little less gloomy", "angrier than the news").
- Never say how many comments, posts, voices, updates or analyses there were, or how much was collected (not "94
  comments", not "18,368 posts", not "a few comments"): talk about what people say, not how many said it.
- It reports what people SAY, not what is true: attribute ("many say", "commenters are split", "the mood is").
- Never name or quote an individual commenter. Talk about people in aggregate ("people", "commenters", "voices").
- Neutral: no side taken, no insult, no slur, no word that carries a judgement the material does not; no sarcasm about
  victims; no hype, no clickbait, no emojis, no hashtags, no links, no long dash.
- Short: at most {words} words ({room} characters) in all. Two or three short sentences is ideal.
- Do not open (or close) the same way as these recent posts: {recent}
Language: {language}.{rules}

The material (JSON):
{facts}"""

NUMBER_WORDS = re.compile(r"(?<![\w])(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
                          r"twenty|thirty|forty|fifty|hundred|thousand|dozens?|اثنان|اثنين|ثلاثة|ثلاث|أربعة|أربع|خمسة|خمس|ستة|ست|"
                          r"سبعة|سبع|ثمانية|ثماني|تسعة|تسع|عشرة|عشر|عشرين|ثلاثين|مئة|مائة|ألف)(?![\w])", re.I)
DIGITS_IN = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


def numbers(text: str) -> set:
    return set(re.findall(r"\d+(?:[.,]\d+)*", str(text).translate(DIGITS_IN)))


SCORE = re.compile(r"(?<![\d.,])[-+−]?0[.,]\d+|\d+\s*-?\s*(?:points?|نقطة|نقاط)\b", re.I)


COUNT = re.compile(r"\d[\d,.]*\s*(?:comments?|posts?|voices?|updates?|analys[ie]s|reactions?|replies)\b|"
                   r"\d[\d,.]*\s*(?:تعليق|منشور|صوت|أصوات|تحديث|تحليل|رد|ردود|تفاعل)|"
                   r"(?:التعليقات|المنشورات|الأصوات)\s+ال(?:ثلاث|أربع|خمس|ست|سبع|ثماني|تسع|عشر)", re.I)


def has_count(text: str) -> bool:
    """A count of what the tracker collected ("94 comments", "18,368 posts"), which posts on X leave out."""
    return bool(COUNT.search(str(text or "").translate(DIGITS_IN)))


def has_score(text: str) -> bool:
    """A tone score (-0.15, +0.20, "a 33-point gap"): the site's measure, which means nothing to readers on X."""
    return bool(SCORE.search(str(text or "").translate(DIGITS_IN)))


def no_scores(text: str) -> str:
    """The text without its sentences that carry a tone score."""
    return " ".join(x for x in re.split(r"(?<=[.!?؟])\s+", str(text or "")) if not has_score(x)).strip()


def comments(n: int, lang: str) -> str:
    return pages.comments_text(n, lang)


def allowed_numbers(text: str) -> set:
    """The numbers of the material, plus their rounded forms: 18,368 also allows 18 (as in "18 thousand")."""
    out = numbers(text)
    out |= {n.split(",")[0] for n in out if "," in n} | {n.split(".")[0] for n in out if "." in n}
    return out


def fit_sentences(text: str, room: int) -> str:
    """The whole sentences (and lines) of text that fit in room by X's count; "" when not even the first does."""
    out = ""
    for part in re.split(r"(?<=[.!?؟])[ ]+|(?=\n)", text):
        joined = (out + (" " if out and not part.startswith("\n") else "") + part).strip()
        if x_len(joined) > room:
            break
        out = joined
    return out


def rewrite(cfg: dict, state: dict | None, lang: str, facts: dict, room: int, lines: int = 4, network: str = "x") -> str | None:
    """The words of a post written by Claude from `facts`, or None (switched off, no key, a failure, or a draft that
    breaks a rule twice), in which case the caller uses its plain format. A draft that runs long is cut to its whole
    sentences when enough is left; otherwise Claude gets one more try, told what was wrong."""
    s = settings(cfg, "x")
    if not s.get("rewrite") or not P.secret("ANTHROPIC_API_KEY") or room < 60:
        return None
    where = "x" if network == "x" else "fb_feed"                   # Facebook posts keep their own recent texts
    recent = [t[:200] for t in ((state or {}).get(where) or {}).get("recent_texts") or []][-6:]
    target = int(room * 0.8)                          # some margin: models count characters loosely
    prompt = VOICE.format(network="X" if network == "x" else "Facebook", lines=lines, room=target, words=max(12, target // 6),
                          recent=json.dumps(recent, ensure_ascii=False) if recent else "(none yet)",
                          language="Arabic, for Syrian readers" if lang == "ar" else "English",
                          rules=arabic.rules() if lang == "ar" else "", facts=json.dumps(facts, ensure_ascii=False, indent=1))
    schema = {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": {"type": "string"}}}
    allowed = allowed_numbers(json.dumps(facts, ensure_ascii=False))
    feedback = ""
    for _ in range(2):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=P.secret("ANTHROPIC_API_KEY"))
            with client.messages.stream(model=cfg.get("model", "claude-sonnet-5"), max_tokens=3000,
                                        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                                        messages=[{"role": "user", "content": prompt + feedback}]) as stream:
                resp = stream.get_final_message()
            cost = P.estimate_cost(cfg.get("model", ""), {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens})
            if state is not None:
                spent = state.setdefault(where, {}).setdefault("rewrite_usd", {})
                month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
                spent[month] = round(spent.get(month, 0) + cost, 4)
                for k in sorted(spent)[:-3]:
                    spent.pop(k)
            text = str(P.extract_json("".join(b.text for b in resp.content if b.type == "text")).get("text") or "")
        except Exception as e:  # noqa: BLE001  (the plain format goes out instead)
            print(f"X: the rewrite failed ({type(e).__name__}); the plain format is used.")
            return None
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"#(\w+)", lambda m: m.group(1).replace("_", " "), text)      # a hashtag in the words: keep the word
        text = text.replace(" — ", "، " if lang == "ar" else ", ").replace("—", "-")
        text = re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()
        if lang == "ar":
            text = arabic.tidy(text)
        words = NUMBER_WORDS.findall(text)
        extra = (numbers(text) - allowed) | set(words)
        if x_len(text) > room or text.count("\n") >= lines * 2:
            cut = fit_sentences(text, room)
            if cut and x_len(cut) >= room * 0.5 and cut.count("\n") < lines * 2 and not numbers(cut) - allowed and not has_count(cut):
                return cut
            problem = f"it was {x_len(text)} characters; the limit is {target}. Write a shorter one"
        elif has_score(text):
            problem = "it used a tone score or points; say the mood in plain words, with no score"
        elif has_count(text):
            problem = "it said how many comments, posts or analyses there were; leave every such count out"
        elif extra:
            problem = f"it used numbers that are not in the material ({', '.join(sorted(extra))}). Use only the material's numbers, or none"
        elif text:
            return text
        else:
            problem = "it was empty"
        print(f"X: a rewrite was rejected ({problem}).")
        feedback = f"\n\nYour last draft was rejected: {problem}.\nThe rejected draft: {text}"
    return None


def remember(state: dict, text: str, where: str = "x") -> None:
    """Keep the last few posts, so the next rewrite opens differently."""
    recent = state.setdefault(where, {}).setdefault("recent_texts", [])
    recent.append(text)
    del recent[:-8]


# ---------------------------------------------------------------- X: the budget and the story posts

STORY_WORDS = {"en": {"people": "People's mood", "outlets": "The media's"},
               "ar": {"people": "مزاج الناس", "outlets": "مزاج وسائل الإعلام"}}


def post_cost(s: dict, text: str) -> float:
    """What X charges for a post: much more when it carries a link."""
    return float(s["cost_per_link_post_usd"] if re.search(r"https?://", text or "") else s["cost_per_post_usd"])


def spent_this_month(xs: dict, s: dict, now: dt.datetime) -> float:
    """Dollars spent on X posts this calendar month (UTC). Older records without a price: report posts always had a
    link, the first story posts had none; skipped reports cost nothing."""
    month = now.strftime("%Y-%m")
    reports = sum(float(v.get("usd", s["cost_per_link_post_usd"])) for v in (xs.get("posted") or {}).values()
                  if v.get("id") and str(v.get("at", "")).startswith(month))
    stories = sum(float(v.get("usd", s["cost_per_post_usd"])) for v in xs.get("story_posts") or [] if str(v.get("at", "")).startswith(month))
    return round(reports + stories, 4)


def month_days_left(now: dt.datetime) -> list:
    """The dates from today to the end of the month."""
    d, out = now.date(), []
    while d.month == now.month:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


def reports_to_come(cfg: dict, state: dict, now: dt.datetime) -> int:
    """Report posts still to make this month: those due now, each later day's daily brief and each later Monday's
    weekly digest, so story posts never use the budget the reports need."""
    s = settings(cfg, "x")
    langs = [x for x in s["languages"] if x in ("ar", "en")]
    dlangs = [x for x in langs if x in s["daily_languages"]]
    posted = (state.get("x") or {}).get("posted") or {}
    n = len(due(cfg, state, now, "x"))
    for d in month_days_left(now):
        brief = (d - dt.timedelta(days=1)).isoformat()            # the brief posted on day d is the one for the day before
        if s["daily"] and (d > now.date() or now.hour < int(s["daily_after_utc"])):
            n += sum(1 for lang in dlangs if f"daily:{brief}:{lang}" not in posted)
        if s["weekly"] and d > now.date() and d.weekday() == 0:
            n += len(langs)
    return n


def story_allowance(cfg: dict, state: dict, now: dt.datetime) -> dict:
    """Today's share of the story posts the budget leaves: the dollars left after the report posts still to come
    (each with its link) buy this month's story posts, which are spread evenly over the month's days."""
    s, xs = settings(cfg, "x"), state.get("x") or {}
    budget, spent = float(s["monthly_budget_usd"]), spent_this_month(xs, s, now)
    plain, linked = float(s["cost_per_post_usd"]), float(s["cost_per_link_post_usd"])
    report_price = plain + linked if s.get("link_in_reply") else linked          # with its link in a reply: two posts
    price = (report_price if s.get("story_links", True) else plain)
    reserve = round(reports_to_come(cfg, state, now) * report_price, 4)
    left = max(0.0, budget - spent - reserve)
    month, today = now.strftime("%Y-%m"), local_now(s, now).date().isoformat()
    stories = [p for p in xs.get("story_posts") or [] if str(p.get("at", "")).startswith(month)]
    done_today = sum(1 for p in stories if str(p.get("slot", "")).startswith(today))
    quota = len(stories) + int(left / price + 1e-9) if price > 0 else len(stories)
    days = len(month_days_left(now)) + now.day - 1
    target = int(quota * now.day / days + 0.5)                   # where an even spread should be by the end of today
    per_day = min(int(s["max_stories_per_day"]), max(done_today, target - (len(stories) - done_today)))
    return {"budget": budget, "spent": spent, "reserve": reserve, "left": round(left, 2), "story_price": price,
            "stories_left": int(left / price + 1e-9) if price > 0 else 0, "today": per_day, "done_today": done_today}


def local_now(s: dict, now: dt.datetime) -> dt.datetime:
    return now + dt.timedelta(hours=float(s.get("utc_offset") or 0))


def story_slot(cfg: dict, state: dict, now: dt.datetime) -> str | None:
    """The story slot open now ("YYYY-MM-DD HH", Damascus time), or None. Today's allowance takes the first hours
    of `story_hours` (the busiest first) and posts at them in time order; a slot stays open two hours, so a late
    update still posts, but a missed slot is not made up later."""
    s, xs = settings(cfg, "x"), state.get("x") or {}
    allow = story_allowance(cfg, state, now)
    local = local_now(s, now)
    hours = sorted(int(h) for h in (s["story_hours"] or [])[: allow["today"]])
    open_now = [h for h in hours if h <= local.hour + local.minute / 60 < h + 2]
    if not open_now:
        return None
    slot = f"{local.date().isoformat()} {open_now[-1]:02d}"
    posts = xs.get("story_posts") or []
    if any(p.get("slot") == slot for p in posts):
        return None
    last = max((archive_parse(p.get("at")) for p in posts if archive_parse(p.get("at"))), default=None)
    if last and now - last < dt.timedelta(hours=float(s["story_gap_hours"])):
        return None
    return slot


def outlet_tone(n: dict):
    vals = [v for v in (n.get("outlet_tone") or {}).values() if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else n.get("sentiment")


def story_candidates(cfg: dict, state: dict, now: dt.datetime, lang: str | None = None, posts: list | None = None,
                     pool_hours: float = 0) -> list:
    """The current stories worth a post, best first. Stories that people (not only outlets) talk about come first,
    then those where people and the media disagree, and new ones. Not posted in the last `story_repeat_hours`
    (on X, or in `posts` when given). From the latest update, and with `pool_hours` also from the updates of that
    many hours before (each story as the update where people discussed it most), since one update may have few stories."""
    s, xs = settings(cfg, "x"), state.get("x") or {}
    lang = lang or s["story_language"]
    recent = {p.get("key") for p in (xs.get("story_posts") or [] if posts is None else posts)
              if (t := archive_parse(p.get("at"))) and now - t < dt.timedelta(hours=float(s["story_repeat_hours"]))}
    latest_data = archive._load(pages.DATA / "latest.json", {}) or {}
    runs = []
    if pool_hours:
        since = now - dt.timedelta(hours=pool_hours)
        for day in ((now - dt.timedelta(days=1)).date().isoformat(), now.date().isoformat()):
            runs += [r for r in archive.load_day(day).get("runs") or [] if (t := archive_parse(r.get("generated_at"))) and t >= since]
    pool = {}
    for run in runs + [latest_data]:                     # each story as the update where people discussed it most
        for n in run.get("narratives") or []:
            k = n.get("key") or (archive.story_key(n) if n.get("id") else "")
            if k and (k not in pool or int(n.get("public_volume") or 0) >= int(pool[k].get("public_volume") or 0)):
                pool[k] = {**n, "key": k}
    out = []
    for n in pool.values():
        key, voices = n.get("key") or "", int(n.get("public_volume") or 0)
        if (not key or key in recent or n.get("theme", "other") == "other" or voices < int(s["story_min_voices"])
                or not pages.t(n, "title", lang) or not (pages.ROOT / "stories" / lang / f"{key}.html").exists()):
            continue
        people, media = n.get("public_sentiment"), outlet_tone(n)
        gap = abs(people - media) if isinstance(people, (int, float)) and isinstance(media, (int, float)) else 0
        first = archive_parse(n.get("first_seen"))
        score = voices * (0.5 + voices / max(1, int(n.get("volume") or voices)))
        score *= (1.5 if gap >= 0.4 else 1) * (1.3 if first and now - first < dt.timedelta(hours=24) else 1)
        out.append((score, n, gap))
    return [(n, gap) for score, n, gap in sorted(out, key=lambda x: -x[0])]


def clip_clause(text: str, limit: int) -> str:
    """As much of the text as fits in limit characters, cut after a whole sentence or, failing that, a whole clause
    (at a comma, semicolon or colon), so a post does not end mid-thought; an ellipsis only when no clause fits."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    for pattern in (r"(?<=[.!?؟])\s+", r"(?<=[،,؛;:])\s+"):
        out = ""
        for part in re.split(pattern, text):
            if len(out) + len(part) + 1 > limit:
                break
            out = (out + " " + part).strip()
        if len(out) >= limit * 0.4:
            return out.rstrip("،,؛;:") + ("" if out[-1:] in ".!?؟" else ("." if pattern.startswith("(?<=[،") else ""))
    return clip(text, limit)


def rows(text: str, width: int = 50) -> int:
    """About how many lines the post takes on a phone; X folds longer posts behind "Show more", hiding the hashtags."""
    text = re.sub(r"https?://\S+", "x" * 23, text)          # X shows a link shortened, on one line
    return sum(max(1, -(-len(line) // width)) for line in text.split("\n"))


def story_card(cfg: dict, n: dict, lang: str) -> dict:
    when = pages.fmt_date(dt.datetime.now(dt.timezone.utc).date().isoformat(), lang)
    return {"eyebrow": f"{pages.theme_label(cfg, n.get('theme', 'other'), lang)} · {when}", "title": str(pages.t(n, "title", lang) or ""),
            "people": n.get("public_sentiment"), "media": outlet_tone(n), "line": CARD_WORDS[lang]["comments"]}


def compose_story(cfg: dict, n: dict, gap: float, lang: str, max_rows: int = 8, state: dict | None = None) -> dict:
    """A story post, short enough to show in full in the timeline: the words (a rewrite, or the title, the mood of
    people and of the media when the two differ, and a sentence of what people say), the link to the story's page and
    the hashtags."""
    w = STORY_WORDS[lang]
    key = n.get("key") or ""
    title = str(pages.t(n, "title", lang) or "")
    mood = pages.tone_label(n.get("public_sentiment"), lang)
    people = f"{w['people']}: {mood}"
    head = [title, people] + ([f"{w['outlets']}: {pages.tone_label(outlet_tone(n), lang)}"] if gap >= 0.4 else [])
    body = no_scores(pages.t(n, "public_reaction", lang) or pages.t(n, "summary", lang))
    tags = hashtags.select(cfg, lang, [n.get("theme", "")], [title])[: int(settings(cfg, "x")["max_tags"])]
    full = url(cfg, f"stories/{lang}/{key}.html") if settings(cfg, "x").get("story_links", True) else ""
    link = "" if settings(cfg, "x").get("link_in_reply") else full        # in a reply, where it does not cut the reach
    def tail(n_tags: int) -> str:
        parts = ([link] if link else []) + ([" ".join("#" + t for t in tags[:n_tags])] if n_tags else [])
        return ("\n\n" + "\n".join(parts)) if parts else ""
    def build(text_body: str, n_tags: int) -> str:
        return "\n".join(head) + ("\n\n" + text_body if text_body else "") + tail(n_tags)
    fits = lambda text: x_len(text) <= 280 and rows(text) <= max_rows  # noqa: E731
    n_tags = len(tags)
    facts = {"story": title, "what_happened": no_scores(pages.t(n, "summary", lang)), "what_people_say": body,
             "people_mood": mood,
             "media_mood": pages.tone_label(outlet_tone(n), lang) if gap >= 0.4 else "about the same as people's",
             "feelings": (n.get("emotions_ar") if lang == "ar" else n.get("emotions")) or []}
    words = rewrite(cfg, state, lang, facts, 280 - x_len(tail(2)), lines=max_rows - (4 if link else 3))
    if words:
        k = n_tags
        while k > 1 and not fits(words + tail(k)):
            k -= 1
        if fits(words + tail(k)):
            return {"key": key, "text": words + tail(k), "words": words, "link": full, "card": story_card(cfg, n, lang), "lang": lang}
    cuts = [clip_clause(body, limit) for limit in range(150, 39, -10)]
    whole = [c for c in cuts if not c.endswith("…") and fits(build(c, n_tags))]     # a whole sentence or clause
    cut = [c for c in cuts if fits(build(c, n_tags))]
    text_body = whole[0] if whole else cut[0] if cut else ""
    while n_tags > 1 and not fits(build(text_body, n_tags)):
        n_tags -= 1
    return {"key": key, "text": build(text_body, n_tags), "link": full, "card": story_card(cfg, n, lang), "lang": lang}


def run_x_story(cfg: dict, state: dict, now: dt.datetime, keys: dict) -> None:
    s, xs = settings(cfg, "x"), state.setdefault("x", {})
    slot = story_slot(cfg, state, now)
    if not slot or not s["stories"]:
        return
    cands = story_candidates(cfg, state, now)
    if not cands:
        return
    post = compose_story(cfg, *cands[0], s["story_language"], state=state)
    if spent_this_month(xs, s, now) + expected_cost(s, post) > float(s["monthly_budget_usd"]) + 1e-9:
        return
    try:
        res = publish(cfg, keys, post)
    except Exception as e:  # noqa: BLE001
        xs["last_error"] = {"at": now.isoformat(timespec="seconds"), "item": f"story:{post['key']}", "error": x_explain(e)}
        print(f"X: story {post['key']} not posted. {x_explain(e)}")
        return
    pid = res["id"]
    posts = xs.setdefault("story_posts", [])
    posts.append({"key": post["key"], "slot": slot, "id": pid, "reply": res["reply"], "at": now.isoformat(timespec="seconds"), "usd": res["usd"]})
    remember(state, post.get("words") or post["text"])
    cutoff = (now - dt.timedelta(days=40)).isoformat()
    xs["story_posts"] = [p for p in posts if str(p.get("at", "")) >= cutoff]
    xs.pop("last_error", None)
    print(f"X: posted story {post['key']} ({pid}) for the {slot}:00 slot.")


# ---------------------------------------------------------------- the Graph API

def call(method: str, path: str, token: str, secret: str, version: str, **params) -> dict:
    params["access_token"] = token
    if secret:
        params["appsecret_proof"] = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    base = f"{GRAPH}/{version}" if version else GRAPH
    r = requests.request(method, f"{base}/{path}", data=params if method == "POST" else None,
                         params=params if method == "GET" else None, timeout=40)
    try:
        body = r.json()
    except ValueError:
        body = {"error": {"message": f"HTTP {r.status_code}, not JSON"}}
    if r.status_code >= 400 or "error" in body:
        err = body.get("error") or {}
        raise RuntimeError(f"Facebook said: {err.get('message', 'HTTP ' + str(r.status_code))} (code {err.get('code', '?')})")
    return body


def explain(e: Exception) -> str:
    text = str(e)
    if "(code 190)" in text:
        return text + ". The Page token is invalid or expired: make a new one (GUIDE.md, Facebook) and replace FB_PAGE_TOKEN."
    if "(code 200)" in text or "(code 10)" in text:
        return text + ". The token lacks pages_manage_posts, or its owner is not an admin of the Page."
    return text


def trim(posted: dict) -> None:
    """Keep the record short: the last 200 items."""
    if len(posted) > 200:
        for k in sorted(posted, key=lambda k: posted[k].get("at", ""))[:-200]:
            posted.pop(k)


def run_facebook(cfg: dict, state: dict, now: dt.datetime, preview: list | None, check: bool) -> None:
    s = settings(cfg, "facebook")
    page_id, token = os.environ.get("FB_PAGE_ID", "").strip(), os.environ.get("FB_PAGE_TOKEN", "").strip()
    secret = os.environ.get("FB_APP_SECRET", "").strip()
    items = preview if preview is not None else due(cfg, state, now, "facebook")
    if check:
        print("\n######## Facebook")
        if page_id and token:
            try:
                me = call("GET", page_id, token, secret, s["api_version"], fields="name,link")
                print(f"Token works: it can post to the Page \"{me.get('name')}\" ({me.get('link', '')}).")
            except Exception as e:  # noqa: BLE001
                print(f"Token check failed. {explain(e)}")
        else:
            print("FB_PAGE_ID and FB_PAGE_TOKEN are not set; nothing would be posted.")
        if not items:
            print("Nothing is due.")
        for kind, ident in items:
            post = compose(cfg, kind, ident)
            print(f"\n===== {kind} {ident}: link {post['link'] if post else '(no report)'}\n{post['message'] if post else ''}")
        return
    if not s["enabled"] or not page_id or not token:
        return
    fb = state.setdefault("facebook", {})
    posted = fb.setdefault("posted", {})
    for kind, ident in items[: int(s["per_run"])]:
        post = compose(cfg, kind, ident)
        if not post:
            continue
        try:
            res = call("POST", f"{page_id}/feed", token, secret, s["api_version"], message=post["message"], link=post["link"])
        except Exception as e:  # noqa: BLE001
            fb["last_error"] = {"at": now.isoformat(timespec="seconds"), "item": post["key"], "error": explain(e)}
            print(f"Facebook: {post['key']} not posted. {explain(e)} It is tried again at the next update.")
            return
        posted[post["key"]] = {"id": res.get("id"), "at": now.isoformat(timespec="seconds")}
        fb.pop("last_error", None)
        print(f"Facebook: posted {post['key']} ({res.get('id')}).")
    trim(posted)


def run_x(cfg: dict, state: dict, now: dt.datetime, preview: list | None, check: bool) -> None:
    s, keys = settings(cfg, "x"), x_keys()
    items = preview if preview is not None else due(cfg, state, now, "x")
    if check:
        print("\n######## X")
        if keys:
            try:
                me = x_call("GET", "users/me", keys)
                user = (me.get("data") or {}).get("username") or ""
                print(f"Keys work: they can post as @{user}.")
                profile = pages.x_profile(cfg).rsplit("/", 1)[-1]
                if profile and user.lower() != profile.lower():
                    print(f"Warning: the site links to @{profile} (x_profile_url in config.yaml), but the keys post as @{user}.")
            except Exception as e:  # noqa: BLE001
                print(f"Key check failed. {x_explain(e)}")
        else:
            print("X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET are not all set; nothing would be posted.")
        if not items:
            print("Nothing is due.")
        def show(title: str, post: dict | None) -> None:
            if not post:
                print(f"\n===== {title}\n(no report)")
                return
            reply = f"\n  ↳ reply: {READ_MORE[post.get('lang') or 'ar']}: {post['link']}" if s.get("link_in_reply") and post.get("link") else ""
            card = f"\n  [card: {post['card'].get('eyebrow')} | {post['card'].get('title')} | {post['card'].get('line')}]" if s.get("images") and post.get("card") else ""
            print(f"\n===== {title} ({x_len(post['text'])}/280)\n{post['text']}{reply}{card}")
        tested = False
        for kind, ident, lang in items:
            post = compose_x(cfg, kind, ident, lang, state)
            show(f"{kind} {ident} {lang}", post)
            if keys and post and not tested and s.get("images"):     # draw and upload one card (nothing is posted)
                tested = True
                mid = card_image(cfg, post, keys)
                print(f"  Card test: {'drawn and uploaded, media id ' + mid if mid else 'failed (see above)'}.")
        a, xs_state = story_allowance(cfg, state, now), state.get("x") or {}
        print(f"\n######## X budget\n${a['budget']:g} a month (a post costs ${s['cost_per_post_usd']}, ${s['cost_per_link_post_usd']} with a link); "
              f"${a['spent']:.2f} spent this month, ${a['reserve']:.2f} kept for the reports still to come, ${a['left']:.2f} left for stories "
              f"({a['stories_left']} story posts at ${a['story_price']:.3f} with the link reply); today {a['done_today']} of {a['today']} story posts made. "
              f"Story slot open now: {story_slot(cfg, state, now) or 'none'}. "
              f"Rewrites: {'on' if s.get('rewrite') else 'off'}, ${(xs_state.get('rewrite_usd') or {}).get(now.strftime('%Y-%m'), 0)} this month.")
        for n, gap in story_candidates(cfg, state, now)[:3]:
            show(f"story {n.get('key')}", compose_story(cfg, n, gap, s["story_language"], state=state))
        return
    if not s["enabled"] or not keys:
        return
    xs = state.setdefault("x", {})
    posted = xs.setdefault("posted", {})
    for kind, ident, lang in items[: int(s["per_run"])]:
        post = compose_x(cfg, kind, ident, lang, state)
        if not post:
            continue
        if spent_this_month(xs, s, now) + expected_cost(s, post) > float(s["monthly_budget_usd"]) + 1e-9:
            print(f"X: the monthly budget of ${s['monthly_budget_usd']} is used up; {post['key']} waits.")
            return
        try:
            res = publish(cfg, keys, post)
        except Exception as e:  # noqa: BLE001
            xs["last_error"] = {"at": now.isoformat(timespec="seconds"), "item": post["key"], "error": x_explain(e)}
            print(f"X: {post['key']} not posted. {x_explain(e)} It is tried again at the next update.")
            return
        pid = res["id"]
        posted[post["key"]] = {"id": pid, "reply": res["reply"], "at": now.isoformat(timespec="seconds"), "usd": res["usd"]}
        remember(state, post.get("words") or post["text"])
        xs.pop("last_error", None)
        print(f"X: posted {post['key']} ({pid}).")
    trim(posted)
    run_x_story(cfg, state, now, keys)


# ---------------------------------------------------------------- the social feeds (for Zapier and the like)

SOCIAL_WORDS = {"en": {"title": "Syria Narrative Tracker: posts", "stories": "Top stories", "points": "Key points", "people": "People's mood",
                       "media": "The media", "more": "The full analysis and the PDF on the site:", "note": "An automatic summary of what is said online, not of what is true."},
                "ar": {"title": "متتبّع السرديات السورية: منشورات", "stories": "أبرز القصص", "points": "أبرز النقاط", "people": "مزاج الناس",
                       "media": "وسائل الإعلام", "more": "التحليل الكامل وملف PDF على الموقع:", "note": "ملخص آلي لما يُقال على الإنترنت، لا لما هو صحيح."}}


def social_item(cfg: dict, kind: str, ident: str, lang: str) -> dict | None:
    """A ready-to-post text for one report in one language (for a Facebook Page through Zapier): the label and date,
    the headline, the mood of people and the media in words, the brief or the key points, the top stories, hashtags
    and the link. No tone scores and no counts. {"title", "text", "link", "at"}; None when the report is not ready."""
    w = SOCIAL_WORDS[lang]
    if kind == "daily":
        s = pages.daily_summary(cfg, archive.load_day(ident))
        if not s or not s["stories"]:
            return None
        a = archive._load(pages.DATA / "experts" / "analyses" / f"{ident}.json", None)
        end = dt.datetime.fromisoformat(ident).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        at = archive_parse(a.get("generated_at")) if a else end + dt.timedelta(hours=6)    # once the media half is in
        head = f"{LABEL['daily'][lang]} · {pages.fmt_date(ident, lang)}"
        title = str(pages.t(s["stories"][0], "title", lang) or "")
        people, media = s.get("public_sentiment"), s.get("outlet_sentiment")
        body = [no_scores(pages.t(s["overall"], "brief", lang))]
        listed = (w["stories"], [str(pages.t(e, "title", lang)) for e in s["stories"][:3]])
        themes, titles = [x["theme"] for x in s["themes"]], [pages.t(e, "title", lang) for e in s["stories"]]
        shares = s["themes"]
    else:
        d = archive._load(pages.DATA / kind / f"{ident}.json", None)
        if not d:
            return None
        at = archive_parse(d.get("generated_at"))
        when = (f"{pages.fmt_date(d['from'], lang)} – {pages.fmt_date(d['to'], lang)}" if kind == "weekly" else pages.fmt_month(ident, lang))
        head, title, st = f"{LABEL[kind][lang]} · {when}", str(pages.t(d, "title", lang) or ""), d.get("stats") or {}
        people, media = st.get("public_sentiment"), st.get("outlet_sentiment")
        lead = (d.get("key_findings_ar" if lang == "ar" else "key_findings") if kind == "monthly" else d.get("key_points_ar" if lang == "ar" else "key_points")) or []
        body = []
        listed = (w["points"], [str(x) for x in lead if not has_score(x) and not has_count(x)][:3])
        shares = sorted(st.get("themes") or [], key=lambda x: -x.get("share", 0))
        themes = [x["theme"] for x in shares]
        titles = [title] + [pages.t(h, "title", lang) for h in d.get("highlights") or []]
    if not at:
        return None
    mood = " · ".join(x for x in ((f"{w['people']}: {pages.tone_label(people, lang)}" if people is not None else ""),
                                  (f"{w['media']}: {pages.tone_label(media, lang)}" if media is not None else "")) if x)
    link = url(cfg, f"{kind}/{lang}/{ident}.html")
    tags = " ".join("#" + t for t in hashtags.select(cfg, lang, themes, titles)[:5])
    parts = [head, title] + ([mood] if mood else []) + [x for x in body if x]
    if listed[1]:
        parts.append(listed[0] + ":\n" + "\n".join(f"• {x}" for x in listed[1]))
    parts += [f"{w['more']} {link}", tags, w["note"]]
    card = {"eyebrow": head, "title": title, "people": people, "media": media, "line": themes_line(cfg, shares, lang)}
    return {"title": f"{head}: {title}", "text": "\n\n".join(p for p in parts if p), "link": link, "at": at,
            "card": card, "slug": f"{kind}-{ident}"}


def add_images(cfg: dict, items: list, lang: str, base: str) -> None:
    """Give each feed item an image: its card (cards/<lang>/<kind>-<ident>.png, drawn once with Chrome by
    scripts/cards.py), a hand-added post's own image, or the site's preview image. Cards no longer in the feed are
    removed, so the folder stays small."""
    import cards
    folder = pages.ROOT / "cards" / lang
    folder.mkdir(parents=True, exist_ok=True)
    keep = set()
    for i in items:
        if i.get("card") and i.get("slug"):
            png = folder / f"{i['slug']}.png"
            if png.exists() or cards.render(cfg, {**i["card"], "account": base.replace("https://", "").replace("www.", "")}, lang, png):
                keep.add(png.name)
                i["image"] = f"{base}/cards/{lang}/{png.name}"
        if not i.get("image"):
            i["image"] = f"{base}/assets/{'og-ar' if lang == 'ar' else 'og'}.png"
        elif not str(i["image"]).startswith("http"):
            i["image"] = f"{base}/{str(i['image']).lstrip('/')}"
    for png in folder.glob("*.png"):
        if png.name not in keep:
            png.unlink()


def media(i: dict) -> str:
    """The item's image, as an RSS enclosure and a Media RSS element (Zapier offers either)."""
    from xml.sax.saxutils import escape
    if not i.get("image"):
        return ""
    u = escape(i["image"])
    return f'<enclosure url="{u}" length="0" type="image/png"/><media:content url="{u}" medium="image" type="image/png"/>'


FEED_MORE = {"en": "The full analysis on the site:", "ar": "التحليل الكامل على الموقع:"}


def feed_story_post(cfg: dict, n: dict, gap: float, lang: str, state: dict) -> dict:
    """A story post for the Facebook Page: the headline, what people say (written by Claude in a human voice, or the
    story's summary and reactions), the mood of people and the media in words, the link, hashtags and the note."""
    w = SOCIAL_WORDS[lang]
    key, title = n.get("key") or "", str(pages.t(n, "title", lang) or "")
    people, media = n.get("public_sentiment"), outlet_tone(n)
    mood = " · ".join(x for x in ((f"{w['people']}: {pages.tone_label(people, lang)}" if people is not None else ""),
                                  (f"{w['media']}: {pages.tone_label(media, lang)}" if media is not None else "")) if x)
    summary, reaction = no_scores(pages.t(n, "summary", lang) or ""), no_scores(pages.t(n, "public_reaction", lang) or "")
    facts = {"story": title, "what_happened": summary, "what_people_say": reaction, "people_mood": pages.tone_label(people, lang),
             "media_mood": pages.tone_label(media, lang) if gap >= 0.4 else "about the same as people's",
             "feelings": (n.get("emotions_ar") if lang == "ar" else n.get("emotions")) or []}
    words = rewrite(cfg, state, lang, facts, 600, lines=6, network="facebook")
    link = url(cfg, f"stories/{lang}/{key}.html")
    tags = " ".join("#" + t for t in hashtags.select(cfg, lang, [n.get("theme", "")], [title])[:4])
    body = [words] if words else [x for x in (summary, reaction) if x and not has_count(x)]
    parts = [title] + body + ([mood] if mood else []) + [f"{FEED_MORE[lang]} {link}", tags, w["note"]]
    return {"key": key, "title": title, "text": "\n\n".join(x for x in parts if x), "link": link,
            "card": story_card(cfg, n, lang), "words": words}


def zapier_cycle(s: dict, now: dt.datetime) -> tuple:
    """The start and end dates of the current Zapier month: from `zapier_cycle_day` (the day the plan's usage resets,
    shown in Zapier under Settings, Usage) to the same day of the next month."""
    day = max(1, min(28, int(s.get("zapier_cycle_day") or 1)))
    today = now.date()
    start = today.replace(day=day) if today.day >= day else (today.replace(day=1) - dt.timedelta(days=1)).replace(day=day)
    end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=day)
    return start, end


def feed_room(cfg: dict, state: dict, now: dt.datetime, lang: str) -> int:
    """How many more story posts the feed can carry this Zapier month without going over `zapier_monthly_limit`
    (100 on the free plan), keeping room for every report still to come: past that, Zapier would pause the Zap and
    the reports would stop too. Counts the reports, hand-added posts and story posts already in the feed."""
    s = settings(cfg, "facebook")
    limit = int(s.get("zapier_monthly_limit") or 0)
    if limit <= 0:
        return 10 ** 6
    start, end = zapier_cycle(s, now)
    inside = lambda at: at and start <= at.date() and at <= now  # noqa: E731
    used = 0
    for kind, ident in [("daily", d) for d in archive.all_days()[-40:] if d >= (start - dt.timedelta(days=2)).isoformat()] + [
            (k, x["month" if k == "monthly" else "week"]) for k in ("weekly", "monthly") for x in (archive._load(pages.DATA / k / "index.json", []) or [])[-6:]]:
        item = social_item(cfg, kind, ident, lang)
        used += bool(item and inside(item["at"]))
    used += sum(1 for e in archive._load(pages.DATA / "social_extra.json", []) or [] if e.get("lang") == lang and inside(archive_parse(e.get("at"))))
    used += sum(1 for e in (state.get("fb_feed") or {}).get("story_posts") or [] if e.get("lang") == lang and inside(archive_parse(e.get("at"))))
    yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
    brief = social_item(cfg, "daily", yesterday, lang) if yesterday in archive.all_days() else None
    reserve = (0 if brief and brief["at"] <= now else 1)                           # today's brief, if not out yet
    d = now.date() + dt.timedelta(days=1)
    while d < end:
        reserve += 1 + (d.weekday() == 0) + (d.day == 1)                           # each day's brief, Mondays' digest, the monthly report
        d += dt.timedelta(days=1)
    return max(0, limit - used - reserve)


def run_feed_stories(cfg: dict, state: dict, now: dt.datetime) -> None:
    """Story posts in the feeds of ready-made posts, for the Facebook Page through Zapier: `stories_per_day` a day
    (under facebook: in config.yaml), at the first hours of its `story_hours` (Damascus time), in each of
    `feed_story_languages`; the best current story not posted there in the last two days. Each post is kept in
    data/social.json, so the feed item stays the same until it leaves the feed."""
    s = settings(cfg, "facebook")
    per_day = int(s.get("stories_per_day") or 0)
    if not s["enabled"] or per_day <= 0:
        return
    fs = state.setdefault("fb_feed", {})
    posts = fs.setdefault("story_posts", [])
    local = local_now(s, now)
    hours = sorted(int(h) for h in (s.get("story_hours") or [])[:per_day])
    open_now = [h for h in hours if h <= local.hour + local.minute / 60 < h + 2]     # a late update still posts
    if not open_now:
        return
    slot = f"{local.date().isoformat()} {open_now[-1]:02d}"
    for lang in s.get("feed_story_languages") or []:
        if any(p.get("slot") == slot and p.get("lang") == lang for p in posts):
            continue
        if feed_room(cfg, state, now, lang) < 1:
            print(f"Facebook feed: no story post at {slot}:00 ({lang}); the rest of this Zapier month's posts are kept for the reports.")
            continue
        cands = story_candidates(cfg, state, now, lang, [p for p in posts if p.get("lang") == lang], pool_hours=24)
        if not cands:
            continue
        post = feed_story_post(cfg, *cands[0], lang, state)
        tag = slot.replace(" ", "-")
        posts.append({"key": post["key"], "lang": lang, "slot": slot, "at": now.isoformat(timespec="seconds"), "title": post["title"],
                      "text": post["text"], "link": post["link"], "card": post["card"], "slug": f"story-{tag}", "guid": f"{post['link']}#fb-{tag}"})
        remember(state, post["words"] or post["text"], "fb_feed")
        print(f"Facebook feed: story {post['key']} added for the {slot}:00 slot ({lang}).")
    cutoff = (now - dt.timedelta(days=10)).isoformat()
    fs["story_posts"] = [p for p in posts if str(p.get("at", "")) >= cutoff]


def write_social_feeds(cfg: dict, now: dt.datetime, state: dict | None = None) -> None:
    """feed-social-ar.xml and feed-social.xml: the latest daily briefs (once the day's media analysis is in, or 6 hours
    after the day ends), weekly digests and monthly reports, each item a post ready to publish. GUIDE.md, "Facebook
    through Zapier". Posts added by hand go in data/social_extra.json, each with its time ("at"): a report again
    ("report": [kind, ident]) or a text of its own ("title", "text", "link", and optionally "card" and "slug" for its
    image card, or "image"), and a "guid" that is new to the feed. Story posts come from run_feed_stories."""
    from email.utils import format_datetime
    from xml.sax.saxutils import escape
    reports = [("daily", d) for d in archive.all_days()[-12:] if d < now.date().isoformat()]
    for kind in ("weekly", "monthly"):
        reports += [(kind, x["month" if kind == "monthly" else "week"]) for x in (archive._load(pages.DATA / kind / "index.json", []) or [])[-4:]]
    extra = archive._load(pages.DATA / "social_extra.json", []) or []   # posts added by hand, each at its own time
    stories = ((state if state is not None else load_state()).get("fb_feed") or {}).get("story_posts") or []
    for lang in ("ar", "en"):
        items = [i for k, ident in reports if (i := social_item(cfg, k, ident, lang)) and i["at"] <= now]
        for e in extra:
            at = archive_parse(e.get("at"))
            if e.get("lang") != lang or not at or at > now:
                continue
            item = social_item(cfg, *e["report"], lang) if e.get("report") else {"title": e["title"], "text": e["text"], "link": e["link"], "image": e.get("image"),
                                                                                         "card": e.get("card"), "slug": e.get("slug")}
            if item:
                items.append({**item, "at": at, "guid": e.get("guid") or item["link"]})
        for e in stories:
            if e.get("lang") == lang and (at := archive_parse(e.get("at"))) and at <= now:
                items.append({**{k: e.get(k) for k in ("title", "text", "link", "card", "slug", "guid")}, "at": at})
        items.sort(key=lambda i: i["at"], reverse=True)
        items = items[:20]
        w, base = SOCIAL_WORDS[lang], pages.site_url(cfg)
        if lang in (settings(cfg, "facebook").get("feed_images") or []):
            add_images(cfg, items, lang, base)
        name = "feed-social-ar.xml" if lang == "ar" else "feed-social.xml"
        body = "".join(f"""<item><title>{escape(i['title'])}</title><link>{escape(i['link'])}</link><guid isPermaLink="false">{escape(i.get('guid') or i['link'])}</guid>
<pubDate>{format_datetime(i['at'])}</pubDate><description><![CDATA[{i['text'].replace(']]>', ']] >')}]]></description>{media(i)}</item>
""" for i in items)
        xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>{escape(w["title"])}</title><link>{escape(base)}/</link>'
               f'<description>{escape(w["title"])}</description><language>{lang}</language>\n{body}</channel></rss>\n')
        path = pages.ROOT / name
        if not path.exists() or path.read_text(encoding="utf-8") != xml:
            path.write_text(xml, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="check the keys and print what would be posted; post nothing")
    ap.add_argument("--preview", action="store_true", help="print the latest posts of each kind, due or not; post nothing")
    ap.add_argument("--only", choices=["facebook", "x"], help="one network only")
    args = ap.parse_args()
    cfg = P.load_config()
    now = dt.datetime.now(dt.timezone.utc)
    state = load_state()
    before = json.dumps(state, sort_keys=True)
    check = args.dry_run or args.preview
    preview_fb = preview_x = None
    if args.preview:
        base = [("daily", (now.date() - dt.timedelta(days=1)).isoformat())]
        base += [(k, x["month" if k == "monthly" else "week"]) for k in ("weekly", "monthly") if (x := latest(k))]
        preview_fb = base
        sx = settings(cfg, "x")
        preview_x = [(k, i, lang) for k, i in base for lang in sx["languages"] if k != "daily" or lang in sx["daily_languages"]]
    if args.only in (None, "facebook"):
        run_facebook(cfg, state, now, preview_fb, check)
    if args.only in (None, "x"):
        run_x(cfg, state, now, preview_x, check)
    if not check and args.only in (None, "facebook"):
        try:
            run_feed_stories(cfg, state, now)
        except Exception as e:  # noqa: BLE001  (the reports still go out)
            print(f"Facebook feed: no story post this time ({type(e).__name__}: {e}).")
    if not check and json.dumps(state, sort_keys=True) != before:
        save_state(state)
    if not args.dry_run:
        try:
            write_social_feeds(cfg, now, state)
        except Exception as e:  # noqa: BLE001  (posting never fails because of the feeds)
            print(f"Social feeds not written: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
