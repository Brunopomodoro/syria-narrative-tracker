#!/usr/bin/env python3
"""The newsletter: emails the daily brief, the weekly digest and the monthly report to the readers who signed up for
them on subscribe/en.html or subscribe/ar.html (GUIDE.md, "Newsletter by email"). Runs after every update and sends
each report once per language, through Brevo, to the Brevo list of the readers who chose it:

  syrianpulse-daily-ar, syrianpulse-daily-en, syrianpulse-weekly-ar, ... (made by `setup`)

The sign-up itself (the form, the confirmation email, adding people to the lists) is the Cloudflare Worker in worker/.
Subscribers' addresses are kept only in Brevo, never in this repository. What has been sent is recorded in
data/newsletter.json (no addresses), so nothing goes out twice.

Secret: BREVO_API_KEY. Settings: `newsletter:` in config.yaml (nothing is sent until enabled: true).

Usage:  python scripts/newsletter.py            send what is due
        python scripts/newsletter.py setup      make the six lists in Brevo (once)
        python scripts/newsletter.py --preview  print what is due and the lists' sizes, and write sample emails to
                                                .newsletter-sample/ (to open in a browser); send nothing
"""
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import experts  # noqa: E402
import pages  # noqa: E402
import pipeline as P  # noqa: E402

API = "https://api.brevo.com/v3"
STATE = pages.DATA / "newsletter.json"
KINDS = ("daily", "weekly", "monthly")
FOLDER = "Syrian Pulse newsletter"
DAILY_LIMIT = 300                          # Brevo's free plan: emails a day

W = {"en": {"daily": "Daily brief", "weekly": "Weekly digest", "monthly": "Monthly report", "points": "The main points",
            "findings": "Key findings", "stories": "The stories that mattered", "people": "What people said",
            "media": "What the media and experts said", "read": {"daily": "Read the full brief", "weekly": "Read the full digest", "monthly": "Read the full report"},
            "pdf": "Download the PDF", "mood": "People's mood", "media_mood": "The media", "why": "You receive this because you signed up at",
            "change": "Change your choices", "unsub": "Unsubscribe", "note": "An automatic summary of what is said online, not of what is true."},
     "ar": {"daily": "الموجز اليومي", "weekly": "الملخص الأسبوعي", "monthly": "التقرير الشهري", "points": "أبرز النقاط",
            "findings": "أبرز النتائج", "stories": "القصص الأبرز", "people": "ما قاله الناس",
            "media": "ما قاله الإعلام والخبراء", "read": {"daily": "اقرأ الموجز كاملاً", "weekly": "اقرأ الملخص كاملاً", "monthly": "اقرأ التقرير كاملاً"},
            "pdf": "تنزيل ملف PDF", "mood": "مزاج الناس", "media_mood": "وسائل الإعلام", "why": "تصلك هذه الرسالة لأنك اشتركت عبر",
            "change": "تغيير اختياراتك", "unsub": "إلغاء الاشتراك", "note": "ملخص آلي لما يُقال على الإنترنت، لا لما هو صحيح."}}


def settings(cfg: dict) -> dict:
    s = {"enabled": False, "sender_email": "", "daily": True, "weekly": True, "monthly": True, "daily_after_utc": 5}
    s.update(cfg.get("newsletter") or {})
    return s


def list_name(kind: str, lang: str) -> str:
    return f"syrianpulse-{kind}-{lang}"            # the same names as worker/newsletter.js


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- Brevo

def brevo(method: str, path: str, body: dict | None = None) -> dict:
    r = requests.request(method, API + path, json=body, timeout=60,
                         headers={"api-key": os.environ.get("BREVO_API_KEY", "").strip(), "accept": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"Brevo said: HTTP {r.status_code} {r.text[:300]}")
    return r.json() if r.text.strip() else {}


def our_lists() -> dict:
    """{list name: {"id", "subscribers"}} of the newsletter's lists in Brevo."""
    out = {}
    for x in brevo("GET", "/contacts/lists?limit=50&offset=0").get("lists") or []:
        if str(x.get("name", "")).startswith("syrianpulse-"):
            out[x["name"]] = {"id": x["id"], "subscribers": int(x.get("uniqueSubscribers", x.get("totalSubscribers", 0)) or 0)}
    return out


def setup() -> int:
    have = our_lists()
    folders = brevo("GET", "/contacts/folders?limit=50&offset=0").get("folders") or []
    folder = next((f["id"] for f in folders if f.get("name") == FOLDER), None) or brevo("POST", "/contacts/folders", {"name": FOLDER})["id"]
    for kind in KINDS:
        for lang in pages.LANGS:
            name = list_name(kind, lang)
            if name in have:
                print(f"{name}: already there (id {have[name]['id']}).")
            else:
                print(f"{name}: made (id {brevo('POST', '/contacts/lists', {'name': name, 'folderId': folder})['id']}).")
    return 0


# ---------------------------------------------------------------- what is due

def due(cfg: dict, state: dict, now: dt.datetime) -> list:
    """(kind, ident) of the reports to send now: yesterday's daily brief (once the media and experts analysis of the
    day is in, or from daily_after_utc), the latest weekly digest (within 3 days) and monthly report (within 7)."""
    s, sent, out = settings(cfg), state.get("sent") or {}, []
    for kind, days in (("monthly", 7), ("weekly", 3)):
        idx = archive._load(pages.DATA / kind / "index.json", []) or []
        if s[kind] and idx:
            item = idx[-1]
            ident = item["month" if kind == "monthly" else "week"]
            made = parse(item.get("generated_at"))
            if made and now - made < dt.timedelta(days=days) and any(f"{kind}:{ident}:{lang}" not in sent for lang in pages.LANGS):
                out.append((kind, ident))
    yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
    analysed = (experts.PERIODS / f"{yesterday}.json").exists()
    if s["daily"] and yesterday in archive.all_days() and (analysed or now.hour >= int(s["daily_after_utc"])) \
            and any(f"daily:{yesterday}:{lang}" not in sent for lang in pages.LANGS):
        out.append(("daily", yesterday))
    return out


def parse(iso) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- the email

E = html.escape


def button(url: str, label: str, solid: bool = True) -> str:
    style = ("background:#8A6420;color:#ffffff;" if solid else "background:transparent;color:#8A6420;border:1px solid #8A6420;")
    return (f'<a href="{E(url)}" style="{style}text-decoration:none;padding:11px 20px;border-radius:999px;font-weight:bold;'
            f'display:inline-block;margin:4px 6px 4px 0">{E(label)}</a>')


def section(title: str, inner: str) -> str:
    return f'<h2 style="font-size:17px;margin:26px 0 8px;color:#5a4416;border-bottom:2px solid #E2D9C5;padding-bottom:4px">{E(title)}</h2>{inner}'


def bullets(items: list) -> str:
    return '<ul style="margin:0;padding-inline-start:20px">' + "".join(f'<li style="margin:0 0 8px">{x}</li>' for x in items) + "</ul>"


def frame(cfg: dict, lang: str, eyebrow: str, title: str, body: str) -> str:
    w, base, ar = W[lang], pages.site_url(cfg), lang == "ar"
    dirn, align = ("rtl", "right") if ar else ("ltr", "left")
    font = "Tahoma,Arial,sans-serif" if ar else "Georgia,'Times New Roman',serif"
    return f"""<!doctype html><html lang="{lang}" dir="{dirn}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#F7F1E3">
<div dir="{dirn}" style="max-width:620px;margin:0 auto;padding:24px 22px;background:#F7F1E3;color:#1A1814;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.6;text-align:{align}">
<div style="border-top:6px solid #8A6420;padding-top:14px"><a href="{E(base)}/{'ar/' if ar else ''}" style="color:#8A6420;font-weight:bold;text-decoration:none">{E(pages.site_title(cfg, lang))}</a></div>
<p style="margin:18px 0 4px;color:#8A6420;font-weight:bold;font-size:14px">{E(eyebrow)}</p>
<h1 style="font-family:{font};font-size:25px;line-height:1.3;margin:0 0 6px">{E(title)}</h1>
{body}
<p style="margin:30px 0 0;padding-top:12px;border-top:1px solid #E2D9C5;font-size:12px;color:#6B6559">{E(w['note'])}<br>
{E(w['why'])} <a href="{E(base)}/subscribe/{lang}.html" style="color:#6B6559">syrianpulse.org</a>.
<a href="{E(base)}/subscribe/{lang}.html" style="color:#6B6559">{E(w['change'])}</a> · <a href="{{{{ unsubscribe }}}}" style="color:#6B6559">{E(w['unsub'])}</a></p>
</div></body></html>"""


def mood_line(lang: str, people, media) -> str:
    w = W[lang]
    parts = []
    if people is not None:
        parts.append(f"{w['mood']}: <b>{E(pages.tone_label(people, lang))}</b>")
    if media is not None:
        parts.append(f"{w['media_mood']}: <b>{E(pages.tone_label(media, lang))}</b>")
    return f'<p style="margin:6px 0 0;color:#45413A;font-size:15px">{" · ".join(parts)}</p>' if parts else ""


def story_links(cfg: dict, lang: str, items: list) -> list:
    base = pages.site_url(cfg)
    out = []
    for key, title, why in items:
        link = f'<a href="{E(base)}/stories/{lang}/{E(key)}.html" style="color:#1A1814;font-weight:bold">{E(title)}</a>' if key else f"<b>{E(title)}</b>"
        out.append(link + (f'<br><span style="color:#45413A">{E(why)}</span>' if why else ""))
    return out


def compose(cfg: dict, kind: str, ident: str, lang: str) -> dict | None:
    """{"subject", "html"} of one report's email in one language; None when the report does not exist."""
    w, base = W[lang], pages.site_url(cfg)
    folder = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}[kind]
    page_url = f"{base}/{folder}/{lang}/{ident}.html"
    pdf = (pages.ROOT / folder / lang / f"{ident}.pdf").exists()
    buttons = button(page_url, w["read"][kind]) + (button(f"{base}/{folder}/{lang}/{ident}.pdf", w["pdf"], solid=False) if pdf else "")
    if kind == "daily":
        s = pages.daily_summary(cfg, archive.load_day(ident))
        if not s or not s["stories"]:
            return None
        ov = s["overall"]
        when = pages.fmt_date(ident, lang)
        title = str(pages.t(s["stories"][0], "title", lang) or "")
        brief = re.sub(r"\s+", " ", str(pages.t(ov, "brief", lang) or ""))
        body = mood_line(lang, s.get("public_sentiment"), s.get("outlet_sentiment")) + f"<p>{E(brief)}</p>"
        body += section(w["stories"], bullets(story_links(cfg, lang, [(e.get("key"), pages.t(e, "title", lang), "") for e in s["stories"][:6]])))
        a = archive._load(experts.PERIODS / f"{ident}.json", None)
        if a and a.get("overall"):
            d = a["overall"]
            body += section(w["media"], f"<p><b>{E(experts.plain(pages.t(d, 'title', lang)))}</b><br>{E(experts.plain(pages.t(d, 'lede', lang)))}</p>")
        eyebrow, subject = f"{w['daily']} · {when}", f"{w['daily']} · {when}: {title}"
    else:
        d = archive._load(pages.DATA / kind / f"{ident}.json", None)
        if not d:
            return None
        when = (f"{pages.fmt_date(d['from'], lang)} – {pages.fmt_date(d['to'], lang)}" if kind == "weekly" else pages.fmt_month(ident, lang))
        title = str(pages.t(d, "title", lang) or "")
        st = d.get("stats") or {}
        lead = (d.get("key_findings_ar" if lang == "ar" else "key_findings") if kind == "monthly" else d.get("key_points_ar" if lang == "ar" else "key_points")) or []
        body = mood_line(lang, st.get("public_sentiment"), st.get("outlet_sentiment"))
        if lead:
            body += section(w["findings" if kind == "monthly" else "points"], bullets([E(str(x)) for x in lead[:5]]))
        hl = [(h.get("key"), pages.t(h, "title", lang), pages.t(h, "why", lang)) for h in (d.get("highlights") or [])[:4]]
        if hl:
            body += section(w["stories"], bullets(story_links(cfg, lang, hl)))
        eyebrow, subject = f"{w[kind]} · {when}", f"{w[kind]}: {title}"
    body += f'<p style="margin:24px 0 0">{buttons}</p>'
    return {"subject": subject[:180], "html": frame(cfg, lang, eyebrow, title, body)}


# ---------------------------------------------------------------- sending

def send(cfg: dict, state: dict, now: dt.datetime) -> None:
    s = settings(cfg)
    items = due(cfg, state, now)
    if not items:
        return
    lists = our_lists()
    sent = state.setdefault("sent", {})
    today = now.date().isoformat()
    spent = sum(int(v.get("recipients") or 0) for v in sent.values() if str(v.get("at", "")).startswith(today))
    for kind, ident in items:
        for lang in pages.LANGS:
            key = f"{kind}:{ident}:{lang}"
            if key in sent:
                continue
            lst = lists.get(list_name(kind, lang))
            if not lst:
                print(f"Newsletter: the list {list_name(kind, lang)} does not exist; run the newsletter-setup task.")
                return
            stamp = now.isoformat(timespec="seconds")
            if lst["subscribers"] == 0:
                sent[key] = {"at": stamp, "recipients": 0}
                continue
            if spent + lst["subscribers"] > DAILY_LIMIT:
                print(f"Newsletter: {key} would pass Brevo's {DAILY_LIMIT} emails a day ({spent} sent today); it waits for tomorrow. "
                      "Time for a paid Brevo plan (GUIDE.md, Newsletter by email).")
                continue
            mail = compose(cfg, kind, ident, lang)
            if not mail:
                continue
            camp = brevo("POST", "/emailCampaigns", {
                "name": f"{key} {stamp}", "subject": mail["subject"], "htmlContent": mail["html"],
                "sender": {"name": pages.site_title(cfg, lang), "email": s["sender_email"]},
                "recipients": {"listIds": [lst["id"]]}, "inlineImageActivation": False})
            brevo("POST", f"/emailCampaigns/{camp['id']}/sendNow")
            sent[key] = {"at": stamp, "campaign": camp["id"], "recipients": lst["subscribers"]}
            spent += lst["subscribers"]
            print(f"Newsletter: sent {key} to {lst['subscribers']} subscriber(s) (campaign {camp['id']}).")
    for k in sorted(sent, key=lambda k: sent[k].get("at", ""))[:-300]:
        sent.pop(k)


def preview(cfg: dict, state: dict, now: dt.datetime) -> None:
    out = pages.ROOT / ".newsletter-sample"
    out.mkdir(exist_ok=True)
    print(f"Newsletter {'on' if settings(cfg)['enabled'] else 'off (enabled: false)'}; sender {settings(cfg)['sender_email']}.")
    if os.environ.get("BREVO_API_KEY", "").strip():
        try:
            lists = our_lists()
            print("Lists: " + (", ".join(f"{n} {v['subscribers']}" for n, v in sorted(lists.items())) or "none yet (run newsletter-setup)"))
        except Exception as e:  # noqa: BLE001
            print(f"Brevo check failed: {e}")
    else:
        print("BREVO_API_KEY is not set.")
    print("Due now: " + (", ".join(f"{k} {i}" for k, i in due(cfg, state, now)) or "nothing"))
    yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
    samples = [("daily", yesterday)] + [(k, x[-1]["month" if k == "monthly" else "week"]) for k in ("weekly", "monthly")
                                         if (x := archive._load(pages.DATA / k / "index.json", []))]
    for kind, ident in samples:
        for lang in pages.LANGS:
            mail = compose(cfg, kind, ident, lang)
            if mail:
                (out / f"{kind}-{lang}.html").write_text(mail["html"], encoding="utf-8")
                print(f"  {kind} {lang}: {mail['subject']}")
    print(f"Sample emails in {out}/")


def main() -> int:
    cfg = P.load_config()
    now = dt.datetime.now(dt.timezone.utc)
    state = load_state()
    if "setup" in sys.argv:
        return setup()
    if "--preview" in sys.argv:
        preview(cfg, state, now)
        return 0
    if not settings(cfg)["enabled"] or not os.environ.get("BREVO_API_KEY", "").strip():
        return 0
    before = json.dumps(state, sort_keys=True)
    try:
        send(cfg, state, now)
    except Exception as e:  # noqa: BLE001  (an update never fails because of the newsletter)
        print(f"Newsletter: {e}")
    if json.dumps(state, sort_keys=True) != before:
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
