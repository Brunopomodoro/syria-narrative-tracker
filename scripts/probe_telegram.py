#!/usr/bin/env python3
"""Checks candidate Telegram channels before they are added to config.yaml: for each name, whether its public
web preview (https://t.me/s/NAME) has posts, the channel's title, its subscriber count, the date of its last post,
and the share of its recent posts that mention Syria. Prints no post text. Free.

Usage:  python scripts/probe_telegram.py [NAME ...]      (no names: the candidate list below)
        python scripts/probe_telegram.py --discover      find candidates: the channels that the configured channels
                                                         forward from or link to, and the Telegram links on Syrian
                                                         outlets' websites; then check them all
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


SITES = ["https://www.syria.tv", "https://alwatan.sy", "https://www.enabbaladi.net", "https://www.zamanalwsl.net", "https://orient-news.net",
         "https://www.baladi-news.com", "https://stepagency-sy.net", "https://aljumhuriya.net", "https://www.eqtsad.net", "https://smartnews-agency.com",
         "https://nedaa-sy.com", "https://7al.net", "https://snacksyrian.com", "https://www.syriahr.com", "https://horrya.net", "https://www.alsouria.net",
         "https://jesrpress.com", "https://www.aksalser.com", "https://hashtagsyria.com", "https://athrpress.com", "https://euphratespost.net",
         "https://deirezzor24.net", "https://sana.sy", "https://www.alikhbaria.sy", "https://npasyria.com", "https://hawarnews.com", "https://halabtodaytv.net",
         "https://shaam.org", "https://syriadirect.org", "https://levant24.com", "https://suwayda24.com", "https://www.syria-report.com", "https://daraa24.org",
         "https://www.sham.fm", "https://www.almodon.com", "https://www.thenewarab.com", "https://www.syriaobserver.com", "https://sy-24.com",
         "https://www.damascusv.com", "https://raqqa-sl.com", "https://www.ahrarhoran.net", "https://stj-sy.org", "https://www.irfaasawtak.com"]
SKIP = {"share", "joinchat", "s", "c", "addstickers", "proxy", "iv", "addlist", "boost", "contact", "telegram", "durov", "socks", "setlanguage"}
HANDLE = r"(?:https?:)?//(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{4,31})\b"


def discover(seeds: list) -> list:
    """Candidate handles, most often seen first: forwards and links in the seed channels' recent posts, and the
    Telegram links on outlets' websites."""
    counts: dict = {}
    def add(h, w=1):
        if h.lower() in SKIP or h.lower() in {x.lower() for x in seeds}:
            return
        counts[h] = counts.get(h, 0) + w
    for seed in seeds:
        try:
            page = requests.get(f"https://t.me/s/{seed}", headers=HEADERS, timeout=25).text
        except requests.RequestException:
            continue
        for h in re.findall(r'tgme_widget_message_forwarded_from_name" href="https://t\.me/([A-Za-z][A-Za-z0-9_]{4,31})', page):
            add(h, 3)
        for block in re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', page, re.S):
            for h in re.findall(HANDLE, block):
                add(h)
        time.sleep(1.0)
    for site in SITES:
        try:
            page = requests.get(site, headers=HEADERS, timeout=20).text
        except requests.RequestException:
            continue
        for h in set(re.findall(HANDLE, page)):
            add(h, 2)
    return [h for h, _ in sorted(counts.items(), key=lambda x: -x[1])]


def main() -> int:
    if sys.argv[1:2] == ["--discover"]:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
        import pipeline as P
        known = {c["name"].lower() for c in P.load_config().get("telegram_channels") or []}
        if sys.argv[2:]:                      # snowball: discover from the channels given, skip the websites
            global SITES
            SITES, seeds = [], sys.argv[2:]
        else:
            seeds = sorted(known)
        skip = known | {x.lower() for x in seeds}
        names = [n for n in discover(seeds) if n.lower() not in skip][:150]
        print(f"{len(names)} candidates found from {len(seeds)} channels and {len(SITES)} websites.\n")
    else:
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
    focused = sorted((x for x in rows if x["ok"] and x.get("syria_share", 0) >= 0.3), key=lambda x: -x.get("syria_share", 0))
    print(f"Active and Syria-focused (at least 30% of recent posts): {' '.join(x['name'] for x in focused)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
