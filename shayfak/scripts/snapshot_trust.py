#!/usr/bin/env python3
"""Export the monthly trust aggregates from Firebase into the repository as open data.

Reads /monthly (public read, aggregates only, never individual votes) and writes:
  data/trust/YYYY-MM.json   one file per month: {official_id: {up, dn, inside: {...}, verified: {...}, stars: {sum, cnt}}}
  data/trust/latest.json    the current month, plus the previous month for "movers"
  data/trust/trust.csv      one row per official per month, for spreadsheets and R/Python
  data/trust/index.json     the government-wide trust index per month

Percentages are only computed when the sample reaches config.min_sample.

Usage: python shayfak/scripts/snapshot_trust.py [--db URL]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
TRUST = ROOT / "data" / "trust"


def load_cfg() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch_monthly(db_url: str) -> dict:
    r = requests.get(f"{db_url.rstrip('/')}/monthly.json", timeout=30)
    r.raise_for_status()
    return r.json() or {}


def flatten(monthly: dict) -> dict[str, dict[str, dict]]:
    """Firebase shape is monthly/{officialId}/{YYYY-MM}/{...}; return {month: {official_id: agg}}."""
    out: dict[str, dict[str, dict]] = {}
    for oid, months in monthly.items():
        for month, agg in (months or {}).items():
            out.setdefault(month, {})[str(oid)] = {
                "up": int(agg.get("up", 0)), "dn": int(agg.get("dn", 0)),
                "inside": {"up": int((agg.get("inside") or {}).get("up", 0)), "dn": int((agg.get("inside") or {}).get("dn", 0))},
                "verified": {"up": int((agg.get("verified") or {}).get("up", 0)), "dn": int((agg.get("verified") or {}).get("dn", 0))},
                "stars": {"sum": int((agg.get("stars") or {}).get("sum", 0)), "cnt": int((agg.get("stars") or {}).get("cnt", 0))},
            }
    return out


def pct(up: int, dn: int, min_sample: int):
    n = up + dn
    return round(100 * up / n, 1) if n >= min_sample else None


def index_for(month_data: dict, min_sample: int) -> dict:
    """Government-wide trust: pooled votes across officials, plus the per-official median where samples allow."""
    up = sum(a["up"] for a in month_data.values())
    dn = sum(a["dn"] for a in month_data.values())
    pcts = sorted(p for a in month_data.values() if (p := pct(a["up"], a["dn"], min_sample)) is not None)
    median = pcts[len(pcts) // 2] if pcts else None
    return {"votes": up + dn, "pooled_trust_pct": pct(up, dn, min_sample), "median_official_pct": median, "officials_with_sample": len(pcts)}


def write(months: dict, min_sample: int, officials_path: Path) -> None:
    TRUST.mkdir(parents=True, exist_ok=True)
    slugs = {}
    if officials_path.exists():
        with open(officials_path, encoding="utf-8") as f:
            slugs = {str(o["id"]): o.get("slug", "") for o in json.load(f).get("officials", [])}
    for month, data in months.items():
        with open(TRUST / f"{month}.json", "w", encoding="utf-8") as f:
            json.dump({"month": month, "min_sample": min_sample, "officials": data}, f, ensure_ascii=False, indent=1)
    ordered = sorted(months)
    cur = ordered[-1] if ordered else dt.date.today().strftime("%Y-%m")
    prev = ordered[-2] if len(ordered) > 1 else None
    latest = {"month": cur, "previous_month": prev, "min_sample": min_sample, "generated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
              "officials": months.get(cur, {}), "previous": months.get(prev, {}) if prev else {}}
    with open(TRUST / "latest.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)
    with open(TRUST / "index.json", "w", encoding="utf-8") as f:
        json.dump({"min_sample": min_sample, "months": {m: index_for(months[m], min_sample) for m in ordered}}, f, ensure_ascii=False, indent=1)
    with open(TRUST / "trust.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month", "official_id", "slug", "up", "dn", "trust_pct", "inside_up", "inside_dn", "verified_up", "verified_dn", "stars_sum", "stars_cnt"])
        for m in ordered:
            for oid, a in sorted(months[m].items(), key=lambda kv: int(kv[0])):
                w.writerow([m, oid, slugs.get(oid, ""), a["up"], a["dn"], pct(a["up"], a["dn"], min_sample) if pct(a["up"], a["dn"], min_sample) is not None else "",
                            a["inside"]["up"], a["inside"]["dn"], a["verified"]["up"], a["verified"]["dn"], a["stars"]["sum"], a["stars"]["cnt"]])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="Firebase database URL (default: config.yaml database_url)")
    args = ap.parse_args(argv)
    cfg = load_cfg()
    db = args.db or cfg.get("database_url")
    if not db:
        print("no database_url configured", file=sys.stderr)
        return 1
    try:
        monthly = fetch_monthly(db)
    except requests.RequestException as e:
        print(f"could not read {db}: {e}", file=sys.stderr)
        return 1
    months = flatten(monthly)
    write(months, int(cfg.get("min_sample", 30)), ROOT / "data" / "officials.json")
    print(f"snapshot: {len(months)} month(s), {sum(len(v) for v in months.values())} official-month rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
