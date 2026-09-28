#!/usr/bin/env python3
"""One-off: give a theme to archived stories that were analysed before themes existed.

Each story without a valid theme is classified once, from its title and summary, into the fixed
themes in config.yaml. The theme is then written wherever that story appears: the archive,
the saved hours (data/snapshots), history.json, latest.json and stories.json, and the per-day index
and downloads are rebuilt. Costs a few cents; runs in GitHub Actions (Actions -> Maintenance).

Usage:  ANTHROPIC_API_KEY=... python scripts/backfill_themes.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pipeline as P  # noqa: E402

BATCH = 40


def classify(client, model: str, themes: list, items: list) -> dict:
    """items: [(n, title, summary)] -> {n: theme_id}"""
    theme_lines = "\n".join(f"- {t['id']}: {t['label']}. {t['about']}" for t in themes)
    lines = "\n".join(f"[{n}] {title}\n    {summary[:300]}" for n, title, summary in items)
    msg = (f"File each story under exactly one theme. Themes (id: what belongs there):\n{theme_lines}\n\n"
           f"Stories:\n{lines}\n\nReply with ONLY a JSON object mapping each story number to a theme id, "
           f"for example {{\"1\": \"economy\", \"2\": \"other\"}}.")
    resp = client.messages.create(model=model, max_tokens=4000, messages=[{"role": "user", "content": msg}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    ids = {t["id"] for t in themes}
    out = {}
    for k, v in P.extract_json(text).items():
        try:
            out[int(k)] = str(v).strip().lower() if str(v).strip().lower() in ids else "other"
        except ValueError:
            continue
    return out


def main() -> int:
    import anthropic
    cfg = P.load_config()
    themes = archive.theme_catalog(cfg)
    ids = {t["id"] for t in themes}
    model = cfg.get("model", "claude-sonnet-5")

    todo = {}   # story key -> (title, summary)
    for date in archive.all_days():
        for r in archive.load_day(date).get("runs") or []:
            for n in r.get("narratives") or []:
                if n.get("theme") not in ids:
                    todo.setdefault(n.get("key") or archive.story_key(n), (n.get("title", ""), n.get("summary", "")))
    if not todo:
        print("Every archived story already has a theme.")
        return 0
    print(f"{len(todo)} stories to classify with {model}...")
    client = anthropic.Anthropic(api_key=P.secret("ANTHROPIC_API_KEY"))
    keys = list(todo)
    assigned = {}
    for i in range(0, len(keys), BATCH):
        chunk = keys[i:i + BATCH]
        items = [(j + 1, todo[k][0], todo[k][1]) for j, k in enumerate(chunk)]
        result = classify(client, model, themes, items)
        for j, k in enumerate(chunk):
            assigned[k] = result.get(j + 1, "other")
        print(f"  {min(i + BATCH, len(keys))}/{len(keys)}")

    def apply(narratives: list) -> int:
        changed = 0
        for n in narratives or []:
            key = n.get("key") or archive.story_key(n)
            if n.get("theme") not in ids and key in assigned:
                n["key"], n["theme"], changed = key, assigned[key], changed + 1
        return changed

    total = 0
    for date in archive.all_days():
        day = archive.load_day(date)
        if sum(apply(r.get("narratives")) for r in day.get("runs") or []):
            archive._save(archive.day_path(date), day)
            total += 1
    for f in archive.DATA.glob("snapshots/*.json"):
        snap = archive._load(f, {})
        if apply(snap.get("narratives")):
            archive._save(f, snap)
    for name in ("latest.json", "stories.json"):
        path = archive.DATA / name
        obj = archive._load(path, None)
        if isinstance(obj, dict) and apply(obj.get("narratives")):
            P.save_json(path, obj)
        elif isinstance(obj, list) and apply(obj):
            archive._save(path, obj)
    history = archive._load(archive.DATA / "history.json", [])
    if sum(apply(h.get("narratives")) for h in history):
        P.save_json(archive.DATA / "history.json", history)
    archive.update_index(cfg, None)
    archive.write_exports(cfg, sorted({d[:7] for d in archive.all_days()}))
    print(f"Done: {len(assigned)} stories classified, {total} archive days updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
