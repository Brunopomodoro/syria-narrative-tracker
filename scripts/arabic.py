"""Arabic text quality: the writing rules added to every prompt that writes Arabic, the glossary of fixed terms from
config.yaml ("arabic_terms"), and the fixes applied to every generated Arabic text afterwards (quotation marks,
Syrian month names, digits, and the glossary's known wrong forms). No call to Claude.

  rules()   the style rules and the glossary, to append to a prompt
  tidy(v)   fix a generated text (or list or dict of texts); English text is left as it is
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARABIC = re.compile("[؀-ۿ]")
LATIN = re.compile("[A-Za-z]")
L = "ء-يٮ-ۓۺ-ۿ"      # Arabic letters, without Arabic punctuation and digits
D = "0-9٠-٩"                              # Western and Arabic-Indic digits
_TERMS: list | None = None

STYLE = """Arabic style, for every Arabic text you write:
- Write it as an editor at a Syrian newsroom would write it for Syrian readers, not as a translation of the English: rebuild each sentence in natural Arabic order, start with the verb where Arabic would, and link ideas with و، ف، إذ، بينما، في حين instead of chains of short English-shaped sentences.
- Check agreement: a verb before a feminine or non-human plural subject is feminine (تهيمن المخاوف، تتواصل التوغلات، تراوحت الردود).
- Never transliterate English jargon (أوسينت، فريمينغ، ترند، بوست): use the Arabic terms in the glossary below, or a plain Arabic phrase.
- Keep the register neutral: no word that carries a judgement the English does not (for example التبجح، أبواق، شبيحة، ذباب إلكتروني), unless it is clearly attributed as the posters' own word.
- Dates use the Syrian month names: كانون الثاني، شباط، آذار، نيسان، أيار، حزيران، تموز، آب، أيلول، تشرين الأول، تشرين الثاني، كانون الأول (for example ١٩ تشرين الأول).
- Use «» for quotation marks, and the Arabic comma ، and question mark ؟.
- A region of Syria is not an adjective: "outlets in the north-east" is وسائل إعلام في شمال شرق سوريا, never وسائل إعلام شمال شرقية.
- Use the same Arabic word for the same English term throughout a text."""


def terms() -> list:
    """The glossary from config.yaml: [{"en", "ar", "avoid": [...]}, ...], read once."""
    global _TERMS
    if _TERMS is None:
        try:
            import yaml
            cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
            _TERMS = [t for t in cfg.get("arabic_terms") or [] if t.get("en") and t.get("ar")]
        except Exception:  # noqa: BLE001  (no glossary is better than a failed update)
            _TERMS = []
    return _TERMS


def rules() -> str:
    glossary = "\n".join(f"- {t['en']}: {t['ar']}" for t in terms())
    return "\n\n" + STYLE + ("\n\nArabic glossary (English term: the Arabic to use):\n" + glossary if glossary else "")


MONTHS = {"يناير": "كانون الثاني", "فبراير": "شباط", "مارس": "آذار", "أبريل": "نيسان", "إبريل": "نيسان", "ابريل": "نيسان",
          "مايو": "أيار", "يونيو": "حزيران", "يونيه": "حزيران", "يوليو": "تموز", "يوليه": "تموز", "أغسطس": "آب",
          "اغسطس": "آب", "سبتمبر": "أيلول", "أكتوبر": "تشرين الأول", "اكتوبر": "تشرين الأول", "نوفمبر": "تشرين الثاني",
          "ديسمبر": "كانون الأول"}
_M = "|".join(sorted(MONTHS, key=len, reverse=True))
# only after a day number or the word شهر, or before a year, so the verb مارس ("practised") is never touched
MONTH_DATE = re.compile(f"(?:(?<=[{D}] )|(?<=شهر ))({_M})(?![{L}])|({_M})(?= [{D}]{{4}})")
Q = "'\"“”‘’"                   # straight and curly quotation marks
QUOTED = re.compile(f"(?:(?<=^)|(?<=[\\s(وبلفك]))[{Q}]([^{Q}«»\\n]{{1,120}}?)[{Q}](?=$|[\\s.,،؛:!?؟)])")
DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
LINK_TARGET = re.compile(r"(\]\([0-9a-f]{14}\))")         # the item id of an Expert view link, never changed
NUMBER = re.compile(r"(?<![A-Za-z0-9_\-/])\d+(?:[.,]\d+)*%?(?![A-Za-z0-9_\-/])")   # not inside i24NEWS or COVID-19


def _number(m: re.Match) -> str:
    s = re.sub(r"(?<=\d)\.(?=\d)", "٫", m.group(0))      # Arabic decimal separator
    s = re.sub(r"(?<=\d),(?=\d)", "٬", s)                 # Arabic thousands separator
    return s.replace("%", "٪").translate(DIGITS)


def is_arabic(s: str) -> bool:
    return len(ARABIC.findall(s)) > len(LATIN.findall(s))


def tidy(v):
    if isinstance(v, list):
        return [tidy(x) for x in v]
    if isinstance(v, dict):
        return {k: tidy(x) for k, x in v.items()}
    if not isinstance(v, str) or not is_arabic(v):
        return v
    for t in terms():
        if "/" in t["ar"]:
            continue                                # a choice of forms: the prompt handles it, no automatic fix
        for wrong in sorted(t.get("avoid") or [], key=len, reverse=True):
            if wrong:                               # whole words only, so a longer word is never cut
                v = re.sub(f"(?<![{L}]){re.escape(wrong)}(?![{L}])", t["ar"], v)
    v = MONTH_DATE.sub(lambda m: MONTHS[m.group(1) or m.group(2)], v)
    v = QUOTED.sub(lambda m: f"«{m.group(1).strip()}»" if ARABIC.search(m.group(1)) else m.group(0), v)
    v = "".join(part if LINK_TARGET.fullmatch(part) else NUMBER.sub(_number, part) for part in LINK_TARGET.split(v))
    v = re.sub(f"(?<=[{L}»\u066A\u0660-\u0669])\\s*,(?=\\s)", "،", v)            # a Latin comma after Arabic text
    v = re.sub(f"(?<=[{L}])\\s?\\?", "؟", v)
    return v
