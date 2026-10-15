"""What to watch: patterns in the numbers of the last updates that are worth keeping an eye on. Observations, not
forecasts: every item states what the data already shows (a story gaining for several updates in a row, people's
tone far from the coverage, people's tone falling, coordination signs two updates running). Worked out from
data/history.json and the previous snapshot, with no extra call to Claude. The items are saved in latest.json and
in the archive, so whether "gaining" stories went on gaining can be checked later.

Each item: {"type", "id", "key", "title", "title_ar", "share", ...numbers for its type}
  rising     share up in each of the last `updates` updates, from `from` to `to`
  new        first seen in this update and already at least NEW_SHARE of the discussion
  gap        people's tone (`public`) and the outlets' tone (`outlet`) at least GAP apart
  falling    people's tone down from `from` to `to` over the last `hours` hours
  signals    coordination signs at level `level` in this update and the one before
"""
import datetime as dt

MAX_ITEMS = 5
RISE_UPDATES = 3        # the share must grow in at least this many updates in a row (counting the current one)
RISE_MIN = 0.03         # ... by at least 3 points in all
RISE_FLOOR = 0.05       # ... to at least 5% of the discussion
NEW_SHARE = 0.10
GAP = 0.5
GAP_MIN_PUBLIC = 20     # people's posts in the story before their tone counts
FALL = 0.35
FALL_HOURS = 36
ORDER = {"signals": 0, "falling": 1, "gap": 2, "rising": 3, "new": 4}


def _time(s: str):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _base(n: dict, typ: str) -> dict:
    return {"type": typ, "id": n["id"], "key": n.get("key", ""), "title": n.get("title", ""),
            "title_ar": n.get("title_ar", ""), "share": n.get("share", 0)}


def compute(latest: dict, history: list, previous: dict | None) -> list:
    """latest: this update; history: data/history.json including this update as its last entry; previous: the
    snapshot of the update before (or None)."""
    now = _time(latest.get("generated_at", ""))
    past = history[:-1] if history and history[-1].get("time") == latest.get("generated_at") else history
    found = {}

    def add(item):
        if item["id"] not in found or ORDER[item["type"]] < ORDER[found[item["id"]]["type"]]:
            found[item["id"]] = item

    prev_sig = {n["id"]: (n.get("signals") or {}).get("level", "none") for n in (previous or {}).get("narratives") or []}
    for n in latest.get("narratives") or []:
        nid, share = n["id"], float(n.get("share") or 0)

        # gaining in every one of the last updates
        shares = [share]
        for h in reversed(past):
            s = next((float(x.get("share") or 0) for x in h.get("narratives") or [] if x.get("id") == nid), None)
            if s is None or s >= shares[-1]:
                break
            shares.append(s)
        if len(shares) >= RISE_UPDATES and share >= RISE_FLOOR and share - shares[-1] >= RISE_MIN:
            add({**_base(n, "rising"), "from": shares[-1], "to": share, "updates": len(shares) - 1})

        if n.get("first_seen") == latest.get("generated_at") and share >= NEW_SHARE:
            add(_base(n, "new"))

        pub, out = n.get("public_sentiment"), n.get("sentiment")
        if pub is not None and out is not None and (n.get("public_volume") or 0) >= GAP_MIN_PUBLIC and abs(pub - out) >= GAP:
            add({**_base(n, "gap"), "public": pub, "outlet": out})

        # people's tone falling (history keeps people's tone when there is one)
        if pub is not None and now:
            older = [(t, x.get("sentiment")) for h in past for x in h.get("narratives") or []
                     if x.get("id") == nid and x.get("sentiment") is not None
                     for t in [_time(h.get("time", ""))] if t and (now - t).total_seconds() <= FALL_HOURS * 3600]
            if len(older) >= 2:
                t0, first = older[0]
                if first - pub >= FALL and max(v for _, v in older[-2:]) > pub:
                    add({**_base(n, "falling"), "from": first, "to": pub, "hours": max(1, round((now - t0).total_seconds() / 3600))})

        level = (n.get("signals") or {}).get("level", "none")
        if level in ("medium", "high") and prev_sig.get(nid) in ("medium", "high"):
            add({**_base(n, "signals"), "level": level})

    items = sorted(found.values(), key=lambda i: (ORDER[i["type"]], -i["share"]))
    return items[:MAX_ITEMS]
