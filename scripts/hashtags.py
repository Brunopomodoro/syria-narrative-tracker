"""Hashtags for the share links (X, Facebook, Telegram) of daily briefs, weekly digests, monthly reports and
story pages, chosen from the page itself: the tags that go on every share, then the places and names found in
the page's story titles, then the tags of its main themes, then the site's own tag. The list is cut to what fits
in a post on X. The lists live under `share_hashtags:` in config.yaml; these are the defaults when it is absent.
"""
import re

DEFAULTS = {
    "always": {"en": ["Syria"], "ar": ["سوريا", "Syria"]},
    "brand": "SyrianPulse",
    "max": 7,
    "themes": {
        "economy": {"en": ["SyrianEconomy"], "ar": ["الاقتصاد_السوري"]},
        "security": {"en": [], "ar": []},
        "northeast-kurdish": {"en": ["NorthEastSyria", "SDF"], "ar": ["شمال_شرق_سوريا", "قسد"]},
        "suwayda-druze": {"en": ["Suwayda"], "ar": ["السويداء"]},
        "coast-alawite": {"en": ["SyrianCoast", "Latakia"], "ar": ["الساحل_السوري", "اللاذقية"]},
        "justice": {"en": ["TransitionalJustice"], "ar": ["العدالة_الانتقالية"]},
        "governance": {"en": ["SyrianGovernment"], "ar": ["الحكومة_السورية"]},
        "israel-south": {"en": ["Israel", "Golan"], "ar": ["إسرائيل", "الجولان"]},
        "international": {"en": ["MiddleEast"], "ar": ["الشرق_الأوسط"]},
        "refugees": {"en": ["SyrianRefugees"], "ar": ["اللاجئين_السوريين"]},
        "society": {"en": [], "ar": []},
    },
    # en/ar: the tag in each language; match: the spellings looked for in the titles (Arabic ones match inside words,
    # so prefixes like "بـ" and "و" are fine; Latin ones match whole words, and all-capital ones exactly)
    "places": [
        {"en": "Damascus", "ar": "دمشق", "match": ["Damascus", "دمشق"]},
        {"en": "Aleppo", "ar": "حلب", "match": ["Aleppo", "حلب"]},
        {"en": "Homs", "ar": "حمص", "match": ["Homs", "حمص"]},
        {"en": "Hama", "ar": "حماة", "match": ["Hama", "حماة"]},
        {"en": "Latakia", "ar": "اللاذقية", "match": ["Latakia", "Lattakia", "اللاذقية"]},
        {"en": "Tartus", "ar": "طرطوس", "match": ["Tartus", "Tartous", "طرطوس"]},
        {"en": "Idlib", "ar": "إدلب", "match": ["Idlib", "إدلب", "ادلب"]},
        {"en": "Daraa", "ar": "درعا", "match": ["Daraa", "Deraa", "درعا"]},
        {"en": "Suwayda", "ar": "السويداء", "match": ["Suwayda", "Sweida", "Suweida", "السويداء"]},
        {"en": "Quneitra", "ar": "القنيطرة", "match": ["Quneitra", "Qunaitra", "القنيطرة"]},
        {"en": "DeirEzzor", "ar": "دير_الزور", "match": ["Deir ez-Zor", "Deir Ezzor", "Deir al-Zor", "Deir Ezzour", "دير الزور"]},
        {"en": "Raqqa", "ar": "الرقة", "match": ["Raqqa", "Raqqah", "الرقة"]},
        {"en": "Hasakah", "ar": "الحسكة", "match": ["Hasakah", "Hasaka", "Hassakeh", "Hasakeh", "الحسكة"]},
        {"en": "Qamishli", "ar": "القامشلي", "match": ["Qamishli", "Qamishlo", "القامشلي"]},
        {"en": "Kobani", "ar": "عين_العرب", "match": ["Kobani", "Kobane", "Ain al-Arab", "كوباني", "عين العرب"]},
        {"en": "Manbij", "ar": "منبج", "match": ["Manbij", "منبج"]},
        {"en": "Afrin", "ar": "عفرين", "match": ["Afrin", "عفرين"]},
        {"en": "Golan", "ar": "الجولان", "match": ["Golan", "الجولان"]},
        {"en": "Euphrates", "ar": "الفرات", "match": ["Euphrates", "الفرات"]},
        {"en": "Lebanon", "ar": "لبنان", "match": ["Lebanon", "Lebanese", "لبنان", "اللبناني"]},
        {"en": "Turkey", "ar": "تركيا", "match": ["Turkey", "Türkiye", "Turkish", "تركيا", "التركي"]},
        {"en": "Iraq", "ar": "العراق", "match": ["Iraq", "Iraqi", "العراق", "العراقي"]},
        {"en": "Jordan", "ar": "الأردن", "match": ["Jordan", "Jordanian", "الأردن", "الأردني"]},
        {"en": "Israel", "ar": "إسرائيل", "match": ["Israel", "Israeli", "إسرائيل", "اسرائيل", "الإسرائيلي"]},
        {"en": "SDF", "ar": "قسد", "match": ["SDF", "Syrian Democratic Forces", "قسد"]},
        {"en": "ISIS", "ar": "داعش", "match": ["ISIS", "Daesh", "Islamic State", "داعش", "تنظيم الدولة"]},
        {"en": "AlSharaa", "ar": "الشرع", "match": ["al-Sharaa", "Sharaa", "al-Shara", "الشرع"]},
        {"en": "Captagon", "ar": "كبتاغون", "match": ["Captagon", "كبتاغون", "الكبتاغون", "الكبتاجون"]},
        {"en": "UN", "ar": "الأمم_المتحدة", "match": ["UN", "United Nations", "الأمم المتحدة"]},
    ],
}

ARABIC = re.compile(r"[؀-ۿ]")


def _matches(term: str, text: str) -> bool:
    if ARABIC.search(term):
        return term in text
    if term.isupper():
        return re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text) is not None
    return re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text, re.I) is not None


def settings(cfg: dict) -> dict:
    s = dict(DEFAULTS)
    s.update(cfg.get("share_hashtags") or {})
    return s


def select(cfg: dict, lang: str, themes: list, titles: list) -> list:
    """The page's hashtags without '#', most relevant first. themes: theme ids, main one first. titles: the story
    titles on the page, in its language."""
    s = settings(cfg)
    tags = list((s.get("always") or {}).get(lang) or [])
    text = "\n".join(str(x or "") for x in titles)
    found = []
    for place in s.get("places") or []:
        tag = place.get(lang)
        if not tag:
            continue
        n = sum(1 for term in place.get("match") or [] if _matches(term, text))
        if n:
            found.append((n, tag))
    found.sort(key=lambda x: -x[0])
    tags += [tag for _, tag in found[:3]]
    for theme in themes[:3]:
        tags += list(((s.get("themes") or {}).get(theme) or {}).get(lang) or [])
    if s.get("brand"):
        tags.append(s["brand"])
    out, seen = [], set()
    for tag in tags:
        tag = str(tag).strip().lstrip("#").replace(" ", "_")
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out[: int(s.get("max") or 7)]


def fit(tags: list, text: str, limit: int = 280, url_length: int = 23) -> list:
    """The leading tags that keep a post on X within its limit: the text, a space, the link, then '#tag' each
    with a space. Arabic and Latin letters both count as one."""
    room = limit - len(text) - 1 - url_length - 3
    out = []
    for tag in tags:
        cost = len(tag) + 2
        if cost > room:
            break
        out.append(tag)
        room -= cost
    return out
