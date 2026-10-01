#!/usr/bin/env python3
"""Keep data/officials.json in step with Syria's transitional government.

Runs on a schedule (see .github/workflows/shayfak-update.yml) and does four things:

1. Wikidata: resolves each official to a Wikidata item and reads "position held" (P39) statements.
   An end date on the current position is strong evidence the person left office.
2. News search: asks Claude (with web search) for appointments, resignations, reshuffles and deaths
   since the last check, then structures the findings as JSON with source URLs.
3. Decision: applies a change automatically only when the rules in config.yaml are met;
   everything else is written to data/pending_changes.json for a person to approve
   (python update_officials.py --approve <change_id>).
4. Photos and share pages: caches Wikipedia photo URLs and writes one static page per official
   with Open Graph tags, so links shared on Telegram, X and Facebook show the person and their trust score.

Every applied change is appended to data/changelog.json with its sources.

Usage:
  python shayfak/scripts/update_officials.py                # full run
  python shayfak/scripts/update_officials.py --dry-run      # no writes, no Claude calls
  python shayfak/scripts/update_officials.py --no-ai        # Wikidata + photos + pages only
  python shayfak/scripts/update_officials.py --approve ID   # apply one pending change
  python shayfak/scripts/update_officials.py --reject ID    # drop one pending change
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OFFICIALS = DATA / "officials.json"
CHANGELOG = DATA / "changelog.json"
PENDING = DATA / "pending_changes.json"
STATE = DATA / "update_state.json"
TRUST_LATEST = DATA / "trust" / "latest.json"
PAGES = ROOT / "p"

UA = "ShayfakBot/1.0 (https://github.com/brunopomodoro/syria-narrative-tracker; accountability project)"
WD_API = "https://www.wikidata.org/w/api.php"
WD_SPARQL = "https://query.wikidata.org/sparql"
WP_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"

PALETTE = [
    ("#1e3a8a", "#dbeafe"), ("#15803d", "#dcfce7"), ("#b45309", "#fef3c7"), ("#6d28d9", "#ede9fe"),
    ("#0f766e", "#ccfbf1"), ("#9d174d", "#fce7f3"), ("#075985", "#e0f2fe"), ("#b91c1c", "#fee2e2"),
]

CHANGE_TYPES = ("appointment", "resignation", "dismissal", "death", "reshuffle", "restructure")

# First names that mark a woman, for the honorific of a newly added official. Edit titleAr/titleEn in officials.json to correct any.
FEMALE_FIRST = {"فاطمة", "هند", "سارة", "مريم", "رنا", "ريم", "لينا", "آلاء", "أسماء", "رغد", "ديما", "هبة", "منى", "سمر", "رشا", "ليلى", "زينب",
                "خديجة", "عائشة", "عبير", "إيمان", "أمل", "غادة", "نسرين", "رهام", "رؤى", "بشرى", "ولاء", "وفاء", "سناء", "هناء", "صفاء", "دعاء",
                "شيماء", "لمى", "رنيم", "جمانة", "ربى", "بتول", "حنان", "سهام", "ميساء", "سوسن", "نهى", "مها", "منال", "ندى", "نجوى", "رجاء",
                "سلوى", "نادية", "سميرة", "رانيا", "روان", "لبنى", "هدى", "نورا", "محسنة", "سمية", "لارا", "هيفاء", "فرح", "ريما", "آية", "بيان"}


def honorific(name_ar: str, role_ar: str = "", bio: str = "") -> tuple[str, str, str]:
    """(gender, titleAr, titleEn) for a new official. Doctors and engineers keep their professional title."""
    first = (name_ar or "").split()[0] if name_ar else ""
    fem = first in FEMALE_FIRST or "وزيرة" in (role_ar or "") or "عضوة" in (role_ar or "")
    b = (bio or "").lower()
    if re.search(r"دكتوراه|phd|ph\.d|physician|طبيب", b):
        return ("f" if fem else "m", "الدكتورة" if fem else "الدكتور", "Dr.")
    if re.search(r"مهندس|engineer", b):
        return ("f" if fem else "m", "المهندسة" if fem else "المهندس", "Eng.")
    return ("f", "السيدة", "Ms.") if fem else ("m", "السيد", "Mr.")


def log(msg: str) -> None:
    print(f"[{dt.datetime.utcnow():%H:%M:%S}] {msg}", flush=True)


# ── files ──────────────────────────────────────────────────────────────────────

def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── helpers ────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "official"


def norm_name(s: str) -> str:
    """Loose matcher for names: lower-case, strip diacritics, 'al-' prefixes and punctuation."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(al|el|al-|el-)\s*-?", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def find_official(officials: list[dict], name_en: str | None, name_ar: str | None) -> dict | None:
    if name_ar:
        for o in officials:
            if o.get("nameAr") == name_ar:
                return o
    if name_en:
        key = norm_name(name_en)
        for o in officials:
            if norm_name(o.get("nameEn", "")) == key:
                return o
        # last-resort: all tokens of the shorter name appear in the longer one
        toks = set(key.split())
        if len(toks) >= 2:
            for o in officials:
                otoks = set(norm_name(o.get("nameEn", "")).split())
                if toks <= otoks or otoks <= toks:
                    return o
    return None


def group_for_role(role_en: str) -> str:
    r = (role_en or "").lower()
    if "president" in r and "vice" not in r:
        return "president"
    if "governor" in r:
        return "governor"
    if any(k in r for k in ("interior", "defence", "defense", "foreign", "intelligence", "security")):
        return "security"
    if "assembly" in r or "parliament" in r or r.startswith("mp"):
        return "parliament"
    return "gov"


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def change_id(ch: dict) -> str:
    raw = f"{ch.get('type')}|{ch.get('nameEn')}|{ch.get('roleEn')}|{ch.get('date')}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def month_str(d: dt.date | None = None) -> str:
    return (d or dt.date.today()).strftime("%Y-%m")


# ── Wikidata ───────────────────────────────────────────────────────────────────

def wd_get(params: dict, session: requests.Session) -> dict:
    params = {**params, "format": "json"}
    r = session.get(WD_API, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.json()


def wd_search_person(name_en: str, session: requests.Session) -> str | None:
    """Return the QID of a Wikidata item for this name whose description mentions Syria, else None."""
    try:
        res = wd_get({"action": "wbsearchentities", "search": name_en, "language": "en", "limit": 5, "type": "item"}, session)
    except requests.RequestException as e:
        log(f"  wikidata search failed for {name_en}: {e}")
        return None
    for hit in res.get("search", []):
        desc = (hit.get("description") or "").lower()
        if "syria" in desc:
            return hit["id"]
    return None


def wd_positions(qid: str, session: requests.Session) -> list[dict]:
    """Position-held statements: [{position_qid, label, start, end}] (dates as YYYY-MM-DD or None)."""
    try:
        res = wd_get({"action": "wbgetclaims", "entity": qid, "property": "P39"}, session)
    except requests.RequestException as e:
        log(f"  wikidata claims failed for {qid}: {e}")
        return []
    out = []
    for claim in res.get("claims", {}).get("P39", []):
        try:
            pos = claim["mainsnak"]["datavalue"]["value"]["id"]
        except KeyError:
            continue
        quals = claim.get("qualifiers", {})

        def qdate(prop):
            for q in quals.get(prop, []):
                try:
                    return q["datavalue"]["value"]["time"][1:11]
                except KeyError:
                    pass
            return None

        out.append({"position_qid": pos, "start": qdate("P580"), "end": qdate("P582")})
    if out:
        ids = "|".join(sorted({p["position_qid"] for p in out}))
        try:
            labels = wd_get({"action": "wbgetentities", "ids": ids, "props": "labels", "languages": "en"}, session)
            for p in out:
                p["label"] = labels.get("entities", {}).get(p["position_qid"], {}).get("labels", {}).get("en", {}).get("value", "")
        except requests.RequestException:
            for p in out:
                p["label"] = ""
    return out


def wikidata_signals(officials: list[dict], session: requests.Session, resolve_missing: bool = True) -> list[dict]:
    """Return candidate changes confirmed by Wikidata: an official's matching position has an end date."""
    changes = []
    for o in officials:
        if o.get("status") != "active":
            continue
        if not o.get("wikidata") and resolve_missing and o.get("wiki"):
            qid = wd_search_person(o["nameEn"], session)
            if qid:
                o["wikidata"] = qid
                log(f"  resolved {o['nameEn']} -> {qid}")
            time.sleep(0.3)
        if not o.get("wikidata"):
            continue
        positions = wd_positions(o["wikidata"], session)
        time.sleep(0.3)
        role_key = set(norm_name(o["roleEn"]).split()) - {"of", "the", "and", "syria", "syrian"}
        for p in positions:
            label_key = set(norm_name(p.get("label", "")).split())
            overlap = len(role_key & label_key)
            if overlap < max(1, len(role_key) // 2):
                continue
            if p["end"] and (not p["start"] or p["start"] >= (o["tenure"][-1].get("start") or "")[:7]):
                changes.append({
                    "type": "resignation",
                    "nameEn": o["nameEn"], "nameAr": o["nameAr"],
                    "roleEn": o["roleEn"], "roleAr": o["roleAr"],
                    "date": p["end"],
                    "detail_en": f"Wikidata records an end date ({p['end']}) on the position '{p.get('label')}'.",
                    "detail_ar": f"تسجّل ويكي بيانات تاريخ انتهاء ({p['end']}) للمنصب '{p.get('label')}'.",
                    "sources": [{"url": f"https://www.wikidata.org/wiki/{o['wikidata']}", "outlet": "wikidata.org", "title": p.get("label", "")}],
                    "confidence": "high", "official_source": False, "wikidata_confirmed": True,
                })
    return changes


# ── Claude news search ─────────────────────────────────────────────────────────

CHANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": list(CHANGE_TYPES)},
                    "nameEn": {"type": "string"},
                    "nameAr": {"type": "string"},
                    "roleEn": {"type": "string"},
                    "roleAr": {"type": "string"},
                    "previous_holder_en": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD if known, else YYYY-MM"},
                    "detail_en": {"type": "string"},
                    "detail_ar": {"type": "string"},
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"url": {"type": "string"}, "outlet": {"type": "string"}, "title": {"type": "string"}},
                            "required": ["url", "outlet", "title"],
                            "additionalProperties": False,
                        },
                    },
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["type", "nameEn", "nameAr", "roleEn", "roleAr", "previous_holder_en", "date", "detail_en", "detail_ar", "sources", "confidence"],
                "additionalProperties": False,
            },
        },
        "summary_en": {"type": "string"},
        "summary_ar": {"type": "string"},
    },
    "required": ["changes", "summary_en", "summary_ar"],
    "additionalProperties": False,
}


def search_news_with_claude(cfg: dict, officials: list[dict], since: dt.date) -> dict:
    """Two calls: one with web search to gather findings, one to structure them as JSON."""
    import anthropic

    client = anthropic.Anthropic()
    model = cfg.get("model", "claude-opus-5-5")
    today = dt.date.today().isoformat()
    roster = "\n".join(f"- {o['nameEn']} ({o['nameAr']}): {o['roleEn']}" for o in officials if o.get("status") == "active")
    sources = ", ".join(cfg.get("official_sources", []) + cfg.get("preferred_sources", []))

    system = (
        "You monitor personnel changes in Syria's transitional government for Shayfak, a public accountability site. "
        "You report only what the sources say, with a URL for every claim. Appointments announced by presidential decree, "
        "resignations, dismissals, deaths and cabinet reshuffles all count. Rumours and analysis pieces do not. "
        "Prefer official Syrian sources and major outlets. Search in Arabic as well as English."
    )
    research_prompt = (
        f"Today is {today}. Find every change to the people below (or to the positions they hold) announced between "
        f"{since.isoformat()} and today. Also report any newly created ministries or governorships and their holders.\n\n"
        f"Preferred sources: {sources}\n\nCurrent roster:\n{roster}\n\n"
        "For each change give: type, the person's name in English and Arabic, the position in English and Arabic, "
        "the date, a one-sentence description, and the URLs you relied on. If you find nothing, say so."
    )
    with client.beta.messages.stream(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=system,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}],
        messages=[{"role": "user", "content": research_prompt}],
    ) as stream:
        research = stream.get_final_message()
    if research.stop_reason == "refusal":
        raise RuntimeError("model declined the research request")
    findings = "\n".join(b.text for b in research.content if b.type == "text")

    structured = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system="Convert research notes about Syrian government personnel changes into the JSON schema. "
               "Keep only changes that have at least one source URL. Rate confidence 'high' only when an official "
               "source or two independent outlets report the same change with a date.",
        messages=[{"role": "user", "content": f"Research notes:\n\n{findings}"}],
        output_config={"format": {"type": "json_schema", "schema": CHANGE_SCHEMA}},
    )
    text = next(b.text for b in structured.content if b.type == "text")
    data = json.loads(text)
    data["_usage"] = {
        "research": research.usage.to_dict() if hasattr(research.usage, "to_dict") else {},
        "structured": structured.usage.to_dict() if hasattr(structured.usage, "to_dict") else {},
    }
    return data


# ── decision and apply ─────────────────────────────────────────────────────────

def should_auto_apply(ch: dict, cfg: dict) -> tuple[bool, str]:
    if ch.get("wikidata_confirmed"):
        return True, "confirmed by Wikidata"
    if ch.get("confidence") != "high":
        return False, f"confidence {ch.get('confidence')}"
    official = set(cfg.get("official_sources", []))
    srcs = ch.get("sources") or []
    domains = {domain(s.get("url", "")) for s in srcs} - {""}
    if domains & official:
        return True, "official source"
    if len(domains) >= int(cfg.get("min_independent_sources", 2)):
        return True, f"{len(domains)} independent outlets"
    return False, "needs a second source"


def next_id(officials: list[dict]) -> int:
    return max((o["id"] for o in officials), default=0) + 1


def apply_change(ch: dict, officials: list[dict], today: str) -> dict:
    """Mutate the roster in place. Returns the changelog entry."""
    ctype = ch["type"]
    date = (ch.get("date") or today)[:10]
    existing = find_official(officials, ch.get("nameEn"), ch.get("nameAr"))
    entry = {"date": date, "applied_on": today, "type": ctype, "nameEn": ch.get("nameEn"), "nameAr": ch.get("nameAr"),
             "roleEn": ch.get("roleEn"), "roleAr": ch.get("roleAr"), "detail_en": ch.get("detail_en"), "detail_ar": ch.get("detail_ar"),
             "sources": ch.get("sources", []), "applied_by": ch.get("applied_by", "auto"), "reason": ch.get("reason", "")}

    if ctype in ("resignation", "dismissal", "death"):
        if not existing:
            raise ValueError(f"{ctype} for unknown official {ch.get('nameEn')}")
        existing["status"] = "former" if ctype != "death" else "deceased"
        if existing["tenure"] and not existing["tenure"][-1].get("end"):
            existing["tenure"][-1]["end"] = date[:7]
            existing["tenure"][-1]["source"] = (ch.get("sources") or [{}])[0].get("url")
        existing.setdefault("sources", []).extend(ch.get("sources", []))
        entry["official_id"] = existing["id"]
        return entry

    if ctype in ("appointment", "reshuffle", "restructure"):
        # close the previous holder's tenure for this role, if we know them
        prev_name = ch.get("previous_holder_en") or ""
        prev = find_official(officials, prev_name, None) if prev_name else None
        if prev and prev is not existing and prev.get("status") == "active":
            prev["status"] = "former"
            if prev["tenure"] and not prev["tenure"][-1].get("end"):
                prev["tenure"][-1]["end"] = date[:7]
            entry["previous_official_id"] = prev["id"]
        if existing:
            if existing["tenure"] and not existing["tenure"][-1].get("end") and existing["roleEn"] != ch.get("roleEn"):
                existing["tenure"][-1]["end"] = date[:7]
            if existing["roleEn"] != ch.get("roleEn"):
                existing["tenure"].append({"roleAr": ch.get("roleAr"), "roleEn": ch.get("roleEn"), "start": date[:7], "end": None,
                                           "source": (ch.get("sources") or [{}])[0].get("url")})
                existing["roleEn"], existing["roleAr"] = ch.get("roleEn"), ch.get("roleAr")
                existing["grp"] = group_for_role(ch.get("roleEn", ""))
                existing["since"] = date[:7]
            existing["status"] = "active"
            existing.setdefault("sources", []).extend(ch.get("sources", []))
            entry["official_id"] = existing["id"]
            return entry
        nid = next_id(officials)
        col, bg = PALETTE[nid % len(PALETTE)]
        gender, title_ar, title_en = honorific(ch.get("nameAr", ""), ch.get("roleAr", ""), ch.get("detail_en", "") + ch.get("detail_ar", ""))
        new = {
            "id": nid, "slug": slugify(ch.get("nameEn", f"official-{nid}")), "grp": group_for_role(ch.get("roleEn", "")), "status": "active",
            "gender": gender, "titleAr": title_ar, "titleEn": title_en,
            "nameAr": ch.get("nameAr", ""), "nameEn": ch.get("nameEn", ""), "roleAr": ch.get("roleAr", ""), "roleEn": ch.get("roleEn", ""),
            "minAr": "", "minEn": "", "partyAr": "الحكومة الانتقالية", "partyEn": "Transitional Government",
            "since": date[:7], "locAr": "دمشق", "locEn": "Damascus", "wiki": None, "wikidata": None, "photo": None,
            "ini": (ch.get("nameAr") or "?")[0], "col": col, "bg": bg, "issAr": [], "issEn": [],
            "bioAr": ch.get("detail_ar", ""), "bioEn": ch.get("detail_en", ""),
            "cv": [{"y": f"{date[:4]}–الآن / present", "r": {"ar": ch.get("roleAr", ""), "en": ch.get("roleEn", "")},
                    "o": {"ar": "الحكومة الانتقالية السورية", "en": "Syrian Transitional Government"}}],
            "tenure": [{"roleAr": ch.get("roleAr"), "roleEn": ch.get("roleEn"), "start": date[:7], "end": None,
                        "source": (ch.get("sources") or [{}])[0].get("url")}],
            "proms": [], "allegs": [], "sources": list(ch.get("sources", [])),
        }
        existing_slugs = {o["slug"] for o in officials}
        base, i = new["slug"], 2
        while new["slug"] in existing_slugs:
            new["slug"] = f"{base}-{i}"
            i += 1
        officials.append(new)
        entry["official_id"] = nid
        entry["created"] = True
        return entry

    raise ValueError(f"unknown change type {ctype}")


def process_changes(found: list[dict], officials: list[dict], cfg: dict, pending: dict, changelog: list, today: str) -> dict:
    """Apply what the rules allow, queue the rest. Returns counts."""
    applied, queued, skipped = 0, 0, 0
    known_pending = {c["id"] for c in pending["changes"]}
    logged = {(c.get("type"), norm_name(c.get("nameEn", "")), (c.get("date") or "")[:7]) for c in changelog}
    for ch in found:
        if ch.get("type") not in CHANGE_TYPES:
            skipped += 1
            continue
        cid = change_id(ch)
        key = (ch["type"], norm_name(ch.get("nameEn", "")), (ch.get("date") or "")[:7])
        if key in logged or cid in known_pending:
            skipped += 1
            continue
        # a resignation we already reflect (official not active) is noise
        target = find_official(officials, ch.get("nameEn"), ch.get("nameAr"))
        if ch["type"] in ("resignation", "dismissal", "death") and (not target or target.get("status") != "active"):
            skipped += 1
            continue
        if ch["type"] in ("appointment", "reshuffle") and target and target.get("status") == "active" and norm_name(target["roleEn"]) == norm_name(ch.get("roleEn", "")):
            skipped += 1
            continue
        ok, reason = should_auto_apply(ch, cfg)
        if ok:
            ch["reason"] = reason
            try:
                changelog.append(apply_change(ch, officials, today))
                applied += 1
                log(f"  applied {ch['type']}: {ch.get('nameEn')} ({reason})")
            except ValueError as e:
                log(f"  could not apply: {e}; queued instead")
                pending["changes"].append({**ch, "id": cid, "found_on": today, "reason": str(e)})
                queued += 1
        else:
            pending["changes"].append({**ch, "id": cid, "found_on": today, "reason": reason})
            queued += 1
            log(f"  queued {ch['type']}: {ch.get('nameEn')} ({reason})")
    return {"applied": applied, "queued": queued, "skipped": skipped}


# ── photos ─────────────────────────────────────────────────────────────────────

def cache_photos(officials: list[dict], session: requests.Session, refresh: bool = False) -> int:
    n = 0
    for o in officials:
        if not o.get("wiki") or (o.get("photo") and not refresh):
            continue
        try:
            r = session.get(WP_SUMMARY.format(o["wiki"]), headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                continue
            d = r.json()
            src = (d.get("thumbnail") or {}).get("source")
            if src:
                o["photo"] = src
                n += 1
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return n


# ── share pages ────────────────────────────────────────────────────────────────

def write_share_pages(officials: list[dict], cfg: dict, trust: dict | None) -> int:
    """One tiny static page per official with Open Graph tags; it forwards to the app."""
    PAGES.mkdir(parents=True, exist_ok=True)
    site = (cfg.get("site_url") or "").rstrip("/")
    min_sample = int(cfg.get("min_sample", 30))
    written = 0
    for o in officials:
        t = (trust or {}).get(str(o["id"])) or {}
        up, dn = int(t.get("up", 0)), int(t.get("dn", 0))
        n = up + dn
        pct = f"{round(100 * up / n)}% trust · {n} votes this month" if n >= min_sample else "Vote now"
        pct_ar = f"{round(100 * up / n)}% ثقة · {n} صوت هذا الشهر" if n >= min_sample else "صوّت الآن"
        name_ar = f"{o.get('titleAr', '')} {o['nameAr']}".strip()
        name_en = f"{o.get('titleEn', '')} {o['nameEn']}".strip()
        title = f"{name_ar} — شايفك"
        desc = f"{o['roleAr']} · {pct_ar} | {name_en}, {o['roleEn']} · {pct}"
        img = o.get("photo") or f"{site}/assets/og-default.png"
        target = f"../#p{o['id']}"
        page = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:type" content="profile"><meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}"><meta property="og:image" content="{html.escape(img)}">
<meta property="og:url" content="{html.escape(site)}/p/{o['slug']}.html">
<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}"><meta name="twitter:image" content="{html.escape(img)}">
<meta http-equiv="refresh" content="0; url={target}"><link rel="canonical" href="{html.escape(site)}/#p{o['id']}">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;padding:2rem;text-align:center"><p>{html.escape(o['nameAr'])} · {html.escape(o['nameEn'])}</p>
<p><a href="{target}">افتح الملف على شايفك · Open on Shayfak</a></p></body></html>
"""
        (PAGES / f"{o['slug']}.html").write_text(page, encoding="utf-8")
        written += 1
    return written


# ── main ───────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="no writes, no Claude calls")
    ap.add_argument("--no-ai", action="store_true", help="skip the Claude news search")
    ap.add_argument("--no-wikidata", action="store_true")
    ap.add_argument("--no-photos", action="store_true")
    ap.add_argument("--refresh-photos", action="store_true")
    ap.add_argument("--approve", metavar="ID", help="apply one pending change by id")
    ap.add_argument("--reject", metavar="ID", help="drop one pending change by id")
    args = ap.parse_args(argv)

    cfg = load_config()
    doc = load_json(OFFICIALS, {"meta": {}, "officials": []})
    officials = doc["officials"]
    changelog = load_json(CHANGELOG, [])
    pending = load_json(PENDING, {"meta": {"updated": None}, "changes": []})
    state = load_json(STATE, {})
    today = dt.date.today().isoformat()
    session = requests.Session()

    if args.approve or args.reject:
        cid = args.approve or args.reject
        ch = next((c for c in pending["changes"] if c["id"] == cid), None)
        if not ch:
            log(f"no pending change with id {cid}")
            return 1
        pending["changes"] = [c for c in pending["changes"] if c["id"] != cid]
        if args.approve:
            ch["applied_by"] = "manual"
            ch["reason"] = "approved by maintainer"
            changelog.append(apply_change(ch, officials, today))
            log(f"applied {ch['type']} for {ch.get('nameEn')}")
        else:
            log(f"rejected {ch['type']} for {ch.get('nameEn')}")
        if not args.dry_run:
            pending["meta"]["updated"] = today
            doc["meta"]["updated"] = today
            doc["meta"]["count"] = len(officials)
            save_json(PENDING, pending)
            save_json(CHANGELOG, changelog)
            save_json(OFFICIALS, doc)
            write_share_pages(officials, cfg, load_json(TRUST_LATEST, {}).get("officials"))
        return 0

    found: list[dict] = []

    if not args.no_wikidata:
        log("Wikidata: checking positions...")
        try:
            wd = wikidata_signals(officials, session, resolve_missing=not args.dry_run)
            log(f"  {len(wd)} signal(s)")
            found.extend(wd)
        except Exception as e:  # network trouble must not stop the rest of the run
            log(f"  wikidata step failed: {e}")

    if not args.no_ai and not args.dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log("ANTHROPIC_API_KEY not set; skipping news search")
        else:
            last = state.get("last_news_check")
            since = dt.date.fromisoformat(last) if last else dt.date.today() - dt.timedelta(days=int(cfg.get("lookback_days", 45)))
            since = max(since, dt.date.today() - dt.timedelta(days=int(cfg.get("lookback_days", 45))))
            log(f"News search since {since} with {cfg.get('model')}...")
            try:
                res = search_news_with_claude(cfg, officials, since)
                log(f"  {len(res.get('changes', []))} candidate change(s): {res.get('summary_en', '')[:200]}")
                found.extend(res.get("changes", []))
                state["last_news_check"] = today
                state["last_news_summary_en"] = res.get("summary_en")
                state["last_news_summary_ar"] = res.get("summary_ar")
                state["last_usage"] = res.get("_usage")
            except Exception as e:
                log(f"  news search failed: {e}")

    counts = process_changes(found, officials, cfg, pending, changelog, today)
    log(f"changes: {counts}")

    if not args.no_photos and not args.dry_run:
        n = cache_photos(officials, session, refresh=args.refresh_photos)
        log(f"photos cached: {n}")

    if args.dry_run:
        log("dry run: nothing written")
        return 0

    doc["meta"]["updated"] = today
    doc["meta"]["count"] = len(officials)
    doc["meta"]["active"] = sum(1 for o in officials if o.get("status") == "active")
    pending["meta"]["updated"] = today
    state["last_run"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_json(OFFICIALS, doc)
    save_json(CHANGELOG, changelog)
    save_json(PENDING, pending)
    save_json(STATE, state)
    n = write_share_pages(officials, cfg, load_json(TRUST_LATEST, {}).get("officials"))
    log(f"share pages written: {n}")
    # the workflow reads this to decide whether to open an issue
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"pending={len(pending['changes'])}\napplied={counts['applied']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
