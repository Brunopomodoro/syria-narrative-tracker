#!/usr/bin/env python3
"""
Validation study, step 2: compare human coding with the tracker's labels.

Takes the coded sample (the CSV from the "validation-sample" maintenance job, with the coder columns
filled in) and reports how well the tracker's story-level labels match human judgement:
  - theme: share of posts where the coder's theme equals the tracker's, and Cohen's kappa
  - tone: Pearson correlation, mean absolute error, and agreement on the direction (negative / neutral / positive)
  - with two coders: the same numbers between the coders, as the ceiling the tracker can be held to
The summary is written to data/validation.json, which the website's Accuracy section displays.

Usage:  python scripts/validation_compare.py coded-sample.csv [--coders 2] [--note "..."] [--note-ar "..."]

Coder columns (any that are filled in count): coder1_theme, coder1_tone, coder2_theme, coder2_tone.
Tones are numbers from -1 to 1 (for example -1, -0.5, 0, 0.5, 1); rows without a tracker label or a coder label are skipped.
No post text is written anywhere by this script.
"""
import argparse
import csv
import datetime as dt
import json
import math
import pathlib
import sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def num(v):
    try:
        return float(str(v).strip().replace("٫", ".").replace("−", "-"))
    except ValueError:
        return None


def sign(v: float) -> str:
    return "neg" if v <= -0.15 else "pos" if v >= 0.15 else "neu"


def kappa(a: list, b: list) -> float | None:
    """Cohen's kappa for two label lists."""
    n = len(a)
    if not n:
        return None
    cats = set(a) | set(b)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def pearson(x: list, y: list) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((v - mx) ** 2 for v in x)),
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    if not sx[0] or not sy:
        return None
    return round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx[0] * sy), 3)


def compare(rows: list, theme_col: str, tone_col: str, ref_theme: str, ref_tone: str) -> dict:
    th = [(r[theme_col].strip().lower(), r[ref_theme].strip().lower()) for r in rows if r.get(theme_col, "").strip() and r.get(ref_theme, "").strip()]
    tn = [(num(r[tone_col]), num(r[ref_tone])) for r in rows if num(r.get(tone_col)) is not None and num(r.get(ref_tone)) is not None]
    out = {"theme_n": len(th), "tone_n": len(tn)}
    if th:
        out["theme_agreement"] = round(sum(1 for a, b in th if a == b) / len(th), 3)
        out["theme_kappa"] = kappa([a for a, _ in th], [b for _, b in th])
    if tn:
        x, y = [a for a, _ in tn], [b for _, b in tn]
        out["sentiment_correlation"] = pearson(x, y)
        out["sentiment_mae"] = round(sum(abs(a - b) for a, b in tn) / len(tn), 3)
        out["sentiment_sign_agreement"] = round(sum(1 for a, b in tn if sign(a) == sign(b)) / len(tn), 3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--coders", type=int, default=None, help="how many coders coded the sample (default: detected)")
    ap.add_argument("--note", default="", help="a sentence for the website, e.g. who coded and how")
    ap.add_argument("--note-ar", default="")
    args = ap.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("The file has no rows.")
        return 1
    coders = [c for c in ("coder1", "coder2", "coder3") if any(r.get(f"{c}_theme", "").strip() or r.get(f"{c}_tone", "").strip() for r in rows)]
    if not coders:
        print("No coder columns are filled in (coder1_theme, coder1_tone, ...).")
        return 1
    result = {"date": dt.date.today().isoformat(), "sample": len(rows), "coders": args.coders or len(coders), "sample_file": pathlib.Path(args.csv).name}
    per = {}
    for c in coders:
        per[c] = compare(rows, f"{c}_theme", f"{c}_tone", "tracker_theme", "tracker_tone")
        print(f"{c} vs tracker: {per[c]}")
    # headline numbers: the mean over coders
    for key in ("theme_agreement", "theme_kappa", "sentiment_correlation", "sentiment_mae", "sentiment_sign_agreement"):
        vals = [per[c][key] for c in coders if per[c].get(key) is not None]
        if vals:
            result[key] = round(sum(vals) / len(vals), 3)
    if len(coders) >= 2:
        inter = compare(rows, f"{coders[0]}_theme", f"{coders[0]}_tone", f"{coders[1]}_theme", f"{coders[1]}_tone")
        result["between_coders"] = {k: v for k, v in inter.items() if k in ("theme_agreement", "theme_kappa", "sentiment_correlation", "sentiment_sign_agreement", "sentiment_mae")}
        print(f"between coders: {result['between_coders']}")
    result["per_coder"] = per
    if args.note:
        result["note"] = args.note
    if args.note_ar:
        result["note_ar"] = args.note_ar
    (DATA / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nWritten to data/validation.json. Commit that file to show the results on the website's Accuracy section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
