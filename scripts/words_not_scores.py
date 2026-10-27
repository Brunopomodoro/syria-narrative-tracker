#!/usr/bin/env python3
"""Rewrite the tone scores in past report texts as words. Reports written before the prompts asked for words quote the
site's -1 to +1 tone measure ("tone improved from -0.20 to -0.15", "a 33-point gap"), which readers do not know.
For every weekly digest, monthly review and Media and experts analysis, the text fields that carry a score go to
Claude, which rewrites only the parts with scores in plain words; a rewrite that still has a score, loses a link,
changes language or changes length a lot is dropped and the old text kept. Then the pages are rebuilt.

A cent or two per report.  Usage:  python scripts/words_not_scores.py [--auto]
  --auto  after each update: only texts not tried before (data/no_scores_tried.json), so a text that cannot be
          rewritten is not sent again and again; nothing to do costs nothing.
"""
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import arabic  # noqa: E402
import archive  # noqa: E402
import experts  # noqa: E402
import pages  # noqa: E402
import pipeline as P  # noqa: E402

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬−", "0123456789.,-")
SCORE = re.compile(r"(?<![\d.,])[-+]?0[.,]\d+|[-+]\d[.,]\d+|\b\d+\s*-?\s*(?:points?|pts)\b|\d+\s*(?:نقطة|نقاط)")
LINK = re.compile(r"\]\([0-9a-f]{14}\)")
TRIED = archive.DATA / "no_scores_tried.json"
PROMPT = """Each text below is from a report of the Syria Narrative Tracker and quotes tone scores: the site's measure of
tone from -1 (very negative) to +1 (very positive), or changes of it in "points". Readers do not know this measure.
Rewrite each text so that every score, range of scores or change in points is said in plain words instead ("slightly
less negative than the week before", "the angriest reactions of the week", "far more upbeat than people", "mostly
neutral"). Change nothing else: keep every other word, name, date, count, percentage and link markup such as
[name](0123456789abcdef) exactly, keep the language of each text (Arabic stays Arabic, English stays English), keep the
length about the same, and do not use the long dash. Return every key."""


def has_score(text: str) -> bool:
    return bool(SCORE.search(str(text).translate(DIGITS)))


def walk(node, path=()):
    """(path, text) of every string in a report that carries a score."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, path + (i,))
    elif isinstance(node, str) and has_score(node) and "url" not in str(path[-1] if path else ""):
        yield path, node


def put(node, path, value):
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value


def acceptable(old: str, new: str) -> bool:
    new = new.strip()
    return (bool(new) and not has_score(new) and sorted(LINK.findall(old)) == sorted(LINK.findall(new))
            and arabic.is_arabic(old) == arabic.is_arabic(new) and 0.5 <= len(new) / max(1, len(old)) <= 1.5)


def rewrite(cfg: dict, texts: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=P.secret("ANTHROPIC_API_KEY"))
    schema = {"type": "object", "additionalProperties": False, "required": ["items"],
              "properties": {"items": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["key", "text"],
                                                                   "properties": {"key": {"type": "string"}, "text": {"type": "string"}}}}}}
    with client.messages.stream(model=cfg.get("model", "claude-sonnet-5"), max_tokens=16000,
                                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                                messages=[{"role": "user", "content": PROMPT + arabic.rules() + "\n\n" + json.dumps(texts, ensure_ascii=False, indent=1)}]) as stream:
        resp = stream.get_final_message()
    got = P.extract_json("".join(b.text for b in resp.content if b.type == "text")).get("items") or []
    return {x["key"]: x["text"] for x in got if x.get("key") in texts}


def digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def main() -> int:
    auto = "--auto" in sys.argv[1:]
    cfg = P.load_config()
    if not P.secret("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.")
        return 0 if auto else 1
    tried = set(archive._load(TRIED, []) or []) if auto else set()
    files = [f for d in (archive.DATA / "weekly", archive.DATA / "monthly", experts.PERIODS) for f in sorted(d.glob("*.json")) if f.name != "index.json"]
    changed = 0
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        found = [(path, text) for path, text in walk(data) if digest(text) not in tried]
        if not found:
            continue
        if auto:
            tried.update(digest(text) for _, text in found)
            TRIED.write_text(json.dumps(sorted(tried)[-2000:], indent=0) + "\n", encoding="utf-8")
        texts = {str(i): text for i, (_, text) in enumerate(found)}
        try:
            new = rewrite(cfg, texts)
        except Exception as e:  # noqa: BLE001
            print(f"{f.name}: rewrite failed ({type(e).__name__}); left as it is.")
            continue
        done = 0
        for i, (path, old) in enumerate(found):
            text = new.get(str(i), "")
            text = arabic.tidy(text) if arabic.is_arabic(old) else text
            if acceptable(old, text):
                put(data, path, text.strip())
                done += 1
        if done:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            changed += 1
        print(f"{f.relative_to(archive.ROOT)}: {done} of {len(found)} texts rewritten in words.")
    if changed:
        import rebuild_pages
        rebuild_pages.main()
        for e in archive._load(experts.INDEX, []):
            a = archive._load(experts.PERIODS / f"{e['id']}.json", None)
            if a:
                experts.write_pages(cfg, a)
        experts.write_listing(cfg)
    if changed or not auto:
        print(f"{changed} report(s) changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
