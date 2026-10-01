"""Offline tests for the decision rules and roster edits in update_officials.py (no network, no API key)."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import update_officials as uo  # noqa: E402
import snapshot_trust as st  # noqa: E402

CFG = {"official_sources": ["sana.sy", "presidency.gov.sy"], "min_independent_sources": 2, "site_url": "https://example.org", "min_sample": 30}


def roster():
    return [
        {"id": 1, "slug": "a-b", "grp": "gov", "status": "active", "nameEn": "Ali al-Bakr", "nameAr": "علي البكر",
         "roleEn": "Minister of Health", "roleAr": "وزير الصحة", "since": "2025-03",
         "tenure": [{"roleEn": "Minister of Health", "roleAr": "وزير الصحة", "start": "2025-03", "end": None, "source": None}],
         "sources": [], "proms": [], "allegs": [], "cv": []},
        {"id": 2, "slug": "s-k", "grp": "governor", "status": "active", "nameEn": "Sara Khalil", "nameAr": "سارة خليل",
         "roleEn": "Governor of Homs", "roleAr": "محافظ حمص", "since": "2025-01",
         "tenure": [{"roleEn": "Governor of Homs", "roleAr": "محافظ حمص", "start": "2025-01", "end": None, "source": None}],
         "sources": [], "proms": [], "allegs": [], "cv": []},
    ]


def change(**kw):
    base = {"type": "resignation", "nameEn": "Ali al-Bakr", "nameAr": "علي البكر", "roleEn": "Minister of Health", "roleAr": "وزير الصحة",
            "previous_holder_en": "", "date": "2026-09-15", "detail_en": "x", "detail_ar": "y", "confidence": "high",
            "sources": [{"url": "https://www.sana.sy/?p=1", "outlet": "SANA", "title": "t"}]}
    base.update(kw)
    return base


def test_auto_apply_rules():
    assert uo.should_auto_apply(change(), CFG)[0]  # official source
    assert not uo.should_auto_apply(change(confidence="medium"), CFG)[0]
    one_blog = change(sources=[{"url": "https://blog.example.com/a", "outlet": "blog", "title": "t"}])
    assert not uo.should_auto_apply(one_blog, CFG)[0]
    two = change(sources=[{"url": "https://aljazeera.net/a", "outlet": "AJ", "title": "t"}, {"url": "https://reuters.com/b", "outlet": "R", "title": "t"}])
    assert uo.should_auto_apply(two, CFG)[0]
    same_domain_twice = change(sources=[{"url": "https://x.com/a", "outlet": "x", "title": "t"}, {"url": "https://www.x.com/b", "outlet": "x", "title": "t"}])
    assert not uo.should_auto_apply(same_domain_twice, CFG)[0]
    assert uo.should_auto_apply(change(confidence="low", wikidata_confirmed=True), CFG)[0]


def test_find_official_tolerates_prefixes_and_order():
    r = roster()
    assert uo.find_official(r, "Ali Bakr", None)["id"] == 1
    assert uo.find_official(r, "ali al bakr", None)["id"] == 1
    assert uo.find_official(r, None, "سارة خليل")["id"] == 2
    assert uo.find_official(r, "Nobody Here", None) is None


def test_resignation_marks_former_and_closes_tenure():
    r = roster()
    entry = uo.apply_change(change(), r, "2026-10-01")
    assert r[0]["status"] == "former"
    assert r[0]["tenure"][-1]["end"] == "2026-09"
    assert entry["official_id"] == 1 and entry["type"] == "resignation"


def test_appointment_creates_new_official_and_closes_predecessor():
    r = roster()
    ch = change(type="appointment", nameEn="Nour Hamdan", nameAr="نور حمدان", previous_holder_en="Ali al-Bakr")
    entry = uo.apply_change(ch, r, "2026-10-01")
    assert entry.get("created") and len(r) == 3
    new = r[-1]
    assert new["status"] == "active" and new["grp"] == "gov" and new["slug"] == "nour-hamdan"
    assert r[0]["status"] == "former" and r[0]["tenure"][-1]["end"] == "2026-09"
    assert entry["previous_official_id"] == 1


def test_reshuffle_moves_existing_official():
    r = roster()
    ch = change(type="reshuffle", nameEn="Sara Khalil", nameAr="سارة خليل", roleEn="Minister of Tourism", roleAr="وزير السياحة")
    uo.apply_change(ch, r, "2026-10-01")
    s = r[1]
    assert s["roleEn"] == "Minister of Tourism" and s["grp"] == "gov" and len(s["tenure"]) == 2
    assert s["tenure"][0]["end"] == "2026-09" and s["tenure"][1]["end"] is None


def test_process_changes_dedupes_and_queues():
    r = roster()
    pending = {"meta": {}, "changes": []}
    changelog = []
    weak = change(type="appointment", nameEn="Nour Hamdan", nameAr="نور حمدان", confidence="medium")
    counts = uo.process_changes([change(), weak, change()], r, CFG, pending, changelog, "2026-10-01")
    assert counts == {"applied": 1, "queued": 1, "skipped": 1}
    assert len(pending["changes"]) == 1 and pending["changes"][0]["id"] == uo.change_id(weak)
    # second run with the same findings: everything is a duplicate
    counts2 = uo.process_changes([change(), weak], r, CFG, pending, changelog, "2026-10-02")
    assert counts2 == {"applied": 0, "queued": 0, "skipped": 2}


def test_appointment_of_current_holder_is_noise():
    r = roster()
    pending = {"meta": {}, "changes": []}
    ch = change(type="appointment")  # Ali is already Minister of Health
    counts = uo.process_changes([ch], r, CFG, pending, [], "2026-10-01")
    assert counts["skipped"] == 1 and r[0]["status"] == "active"


def test_share_pages_hide_small_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(uo, "PAGES", tmp_path)
    r = roster()
    trust = {"1": {"up": 10, "dn": 5}, "2": {"up": 80, "dn": 20}}
    assert uo.write_share_pages(r, CFG, trust) == 2
    small = (tmp_path / "a-b.html").read_text(encoding="utf-8")
    big = (tmp_path / "s-k.html").read_text(encoding="utf-8")
    assert "Vote now" in small and "80% trust" in big and 'url=../#p2' in big


def test_snapshot_flatten_and_index():
    monthly = {"1": {"2026-09": {"up": 40, "dn": 10, "inside": {"up": 30, "dn": 5}}, "2026-10": {"up": 5, "dn": 5}},
               "2": {"2026-09": {"up": 10, "dn": 30, "stars": {"sum": 50, "cnt": 20}}}}
    months = st.flatten(monthly)
    assert set(months) == {"2026-09", "2026-10"}
    assert months["2026-09"]["1"]["inside"]["up"] == 30 and months["2026-09"]["2"]["stars"]["cnt"] == 20
    idx = st.index_for(months["2026-09"], 30)
    assert idx["votes"] == 90 and idx["pooled_trust_pct"] == 55.6 and idx["officials_with_sample"] == 2
    assert st.pct(5, 5, 30) is None


def test_real_data_file_is_clean():
    doc = json.loads((Path(__file__).resolve().parent.parent / "data" / "officials.json").read_text(encoding="utf-8"))
    ids = [o["id"] for o in doc["officials"]]
    assert len(ids) == len(set(ids))
    for o in doc["officials"]:
        for k in ("bUp", "bDn", "bRSum", "bRCnt", "sbd"):
            assert k not in o, f"seeded count {k} still present on {o['nameEn']}"
        assert o["tenure"] and o["status"] in ("active", "former", "deceased")


def test_honorific_defaults():
    assert uo.honorific("هند قبوات", "وزيرة الشؤون الاجتماعية") == ("f", "السيدة", "Ms.")
    assert uo.honorific("محمد العلي", "وزير الصحة", "physician, PhD") == ("m", "الدكتور", "Dr.")
    assert uo.honorific("أحمد خالد", "محافظ حلب", "civil engineer") == ("m", "المهندس", "Eng.")
    assert uo.honorific("خالد سعيد", "عضو مجلس الشعب") == ("m", "السيد", "Mr.")


def test_new_official_gets_title():
    r = roster()
    ch = change(type="appointment", nameEn="Nour Hamdan", nameAr="هند حمدان", previous_holder_en="")
    uo.apply_change(ch, r, "2026-10-01")
    assert r[-1]["titleEn"] == "Ms." and r[-1]["gender"] == "f"
