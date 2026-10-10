#!/usr/bin/env python3
"""Checks candidate Telegram channels before they are added to config.yaml: for each name, whether its public
web preview (https://t.me/s/NAME) has posts, the channel's title, its subscriber count, the date of its last post,
and the share of its recent posts that mention Syria. Prints no post text. Free.

Usage:  python scripts/probe_telegram.py [NAME ...]      (no names: the candidate list below)
"""
import datetime as dt
import html
import re
import sys
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
SYRIA = re.compile(r"سوري|سورية|دمشق|حلب|حمص|حماة|اللاذقية|طرطوس|إدلب|ادلب|درعا|السويداء|القنيطرة|دير الزور|الرقة|الحسكة|القامشلي|"
                   r"عفرين|منبج|كوباني|جبلة|بانياس|الشرع|قسد|syria|damascus|aleppo|homs|hama|latakia|idlib|daraa|suwayda|raqqa|"
                   r"deir|hasakah|qamishli|rojava|sdf", re.I)

CANDIDATES = [
    # state and official
    "SANAArabic", "sana_ar", "SANA_Syria", "sananews", "SyrianMOFA", "SyMinInfo", "MOI_Syria",
    # national independent and opposition-origin
    "SyriaTV", "syr_tv", "syriatelevision", "SyriaTVNews", "alwatansy", "alwatan_sy", "snacksyrian", "SnackSyrian",
    "zamanalwsl", "zamanalwasl", "orientnews", "baladinews", "baladi_news", "stepagency", "step_agency", "stepnewsagency",
    "syriadirect", "alsouria_net", "alsouria", "alhalnet", "hashtagsyria", "sohr_arabic", "syriahroe", "aljumhuriya",
    "shamfm", "SyriaNow", "syrianow_news", "aksalser", "eqtsad", "eqtsadnet", "jesrpress", "smartnews_agency", "smart_news",
    "nedaa_syria", "nedaasyria", "syrianobserver", "thesyrianobserver", "horrya_press", "alsouriapress",
    # cities and governorates
    "DamascusNow", "damascus_now", "dimashqalaan", "damascusvoice", "HomsNow", "homs_now", "homsnews", "Hama_now", "hamanow",
    "aleppo24news", "Aleppo24", "halabnow", "aleppo_now", "lattakia_now", "LattakiaNews", "latakianews", "tartousnow", "tartus_news",
    "daraa24", "Daraa_24", "ahrarhoran", "horanfl", "quneitra24", "DeirEzzor24", "deirezzor24net", "deirezzor24", "euphratespost",
    "EuphratesPost", "raqqa24", "raqqapost", "idlibpost", "idlib_post", "SuwaydaNow", "suwaydanow", "sweida24", "jableh_now",
    # Kurdish and north-east
    "anhaenglish", "hawarnewsenglish", "ronahitv", "rojnews", "rojava_news", "kurdistan24", "rudawarabic_tv", "nrtarabic",
    # regional (Syria posts only, with filter: true)
    "bbcarabic", "skynewsarabia", "france24_ar", "alhadath", "dw_arabic", "alaraby", "arabi21news", "independentarabia",
]


def probe(name: str) -> dict:
    out = {"name": name, "ok": False}
    try:
        r = requests.get(f"https://t.me/s/{name}", headers=HEADERS, timeout=25, allow_redirects=True)
    except requests.RequestException as e:
        out["note"] = type(e).__name__
        return out
    page = r.text
    if r.status_code != 200 or "/s/" not in r.url:
        out["note"] = f"no public preview (HTTP {r.status_code})"
        return out
    t = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    out["title"] = html.unescape(t.group(1)) if t else ""
    subs = re.search(r'<span class="counter_value">([^<]+)</span>\s*<span class="counter_type">subscribers?</span>', page)
    out["subscribers"] = subs.group(1) if subs else "?"
    texts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', page, re.S)
    times = re.findall(r'<time datetime="([^"]+)"', page)
    out["posts"] = len(texts)
    if not texts:
        out["note"] = "preview has no posts"
        return out
    plain = [re.sub(r"<[^>]+>", " ", html.unescape(x)) for x in texts]
    out["syria_share"] = round(sum(1 for x in plain if SYRIA.search(x)) / len(plain), 2)
    last = max(times) if times else ""
    out["last_post"] = last[:10]
    try:
        age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last)).days
    except ValueError:
        age = 999
    out["days_since_post"] = age
    out["ok"] = age <= 14
    if not out["ok"]:
        out["note"] = "inactive"
    return out


def main() -> int:
    names = sys.argv[1:] or CANDIDATES
    rows = []
    for name in names:
        rows.append(probe(name))
        time.sleep(1.2)       # be gentle with t.me
    print(f"{'channel':22s} {'ok':3s} {'subs':>7s} {'posts':>5s} {'syria':>5s} {'last':10s}  title / note")
    for x in rows:
        print(f"{x['name']:22s} {'yes' if x['ok'] else 'no ':3s} {x.get('subscribers', ''):>7s} {str(x.get('posts', '')):>5s} "
              f"{str(x.get('syria_share', '')):>5s} {x.get('last_post', ''):10s}  {x.get('title', '')} {('(' + x['note'] + ')') if x.get('note') else ''}")
    good = [x["name"] for x in rows if x["ok"]]
    print(f"\n{len(good)} of {len(rows)} active: {' '.join(good)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
