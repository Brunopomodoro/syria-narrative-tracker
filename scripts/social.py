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
         "daily_after_utc": 4, "api_version": "", "languages": ["ar", "en"], "max_tags": 4}
    if network == "x":
        s["per_run"] = 2
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
    message = "\n\n— — —\n\n".join(blocks) + "\n\n" + tag_line(cfg, themes, titles, order) + "\n\n" + NOTE
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


def compose_x(cfg: dict, kind: str, ident: str, lang: str) -> dict | None:
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
        body = (f"{mood}. " if mood else "") + str(pages.t(ov, "brief", lang) or "")
        themes, titles = [x["theme"] for x in s["themes"]], [pages.t(e, "title", lang) for e in s["stories"]]
        link = url(cfg, f"daily/{lang}/{ident}.html")
    elif kind in ("weekly", "monthly"):
        d = archive._load(pages.DATA / kind / f"{ident}.json", None)
        if not d:
            return None
        when = (f"{pages.fmt_date(d['from'], lang)} – {pages.fmt_date(d['to'], lang)}" if kind == "weekly" else pages.fmt_month(ident, lang))
        head = f"{LABEL[kind][lang]} · {when}\n{pages.t(d, 'title', lang)}"
        findings = d.get("key_findings_ar" if lang == "ar" else "key_findings") or d.get("key_findings") or []
        body = str(findings[0]) if kind == "monthly" and findings else str((d.get("paragraphs_ar" if lang == "ar" else "paragraphs") or d.get("paragraphs") or [""])[0])
        themes = [x["theme"] for x in sorted((d.get("stats") or {}).get("themes") or [], key=lambda x: -x.get("share", 0))]
        titles = [pages.t(d, "title", lang)] + [pages.t(h, "title", lang) for h in d.get("highlights") or []]
        link = url(cfg, f"{kind}/{lang}/{ident}.html")
    else:
        return None
    tags = hashtags.select(cfg, lang, themes, titles)[: int(settings(cfg, "x").get("max_tags") or 4)]
    def build(text_body: str, n_tags: int) -> str:
        parts = [head] + ([text_body] if text_body else []) + [link]
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
    return {"key": f"{kind}:{ident}:{lang}", "text": build(text_body, n_tags)}


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
            out += [("daily", yesterday, lang) for lang in langs if not done("daily", yesterday, lang)]
    return [x if network == "x" else x[:2] for x in out]


def archive_parse(iso: str | None) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


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
                print(f"Keys work: they can post as @{(me.get('data') or {}).get('username')}.")
            except Exception as e:  # noqa: BLE001
                print(f"Key check failed. {x_explain(e)}")
        else:
            print("X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET are not all set; nothing would be posted.")
        if not items:
            print("Nothing is due.")
        for kind, ident, lang in items:
            post = compose_x(cfg, kind, ident, lang)
            print(f"\n===== {kind} {ident} {lang} ({x_len(post['text']) if post else 0}/280)\n{post['text'] if post else '(no report)'}")
        return
    if not s["enabled"] or not keys:
        return
    xs = state.setdefault("x", {})
    posted = xs.setdefault("posted", {})
    for kind, ident, lang in items[: int(s["per_run"])]:
        post = compose_x(cfg, kind, ident, lang)
        if not post:
            continue
        try:
            res = x_call("POST", "tweets", keys, {"text": post["text"]})
        except Exception as e:  # noqa: BLE001
            xs["last_error"] = {"at": now.isoformat(timespec="seconds"), "item": post["key"], "error": x_explain(e)}
            print(f"X: {post['key']} not posted. {x_explain(e)} It is tried again at the next update.")
            return
        pid = (res.get("data") or {}).get("id")
        posted[post["key"]] = {"id": pid, "at": now.isoformat(timespec="seconds")}
        xs.pop("last_error", None)
        print(f"X: posted {post['key']} ({pid}).")
    trim(posted)


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
        preview_x = [(k, i, lang) for k, i in base for lang in settings(cfg, "x")["languages"]]
    if args.only in (None, "facebook"):
        run_facebook(cfg, state, now, preview_fb, check)
    if args.only in (None, "x"):
        run_x(cfg, state, now, preview_x, check)
    if not check and json.dumps(state, sort_keys=True) != before:
        save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
