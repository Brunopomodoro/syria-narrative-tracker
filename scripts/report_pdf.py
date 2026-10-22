#!/usr/bin/env python3
"""PDF copies of the monthly reports and weekly digests, made with the Chrome that GitHub's runners (and most
computers) already have: a .pdf next to each page. A PDF is remade when its page has changed since the PDF was made
(a fingerprint of each page is kept in data/pdf_state.json; file times are no use on GitHub, where a fresh checkout
gives every file the same time). Free, no Python packages. Without a Chrome or Chromium on the machine it prints a warning and does nothing.

Usage:  python scripts/report_pdf.py [--all]
"""
import glob
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def chrome() -> str | None:
    for name in (os.environ.get("CHROME_BIN", ""), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if name and shutil.which(name):
            return shutil.which(name)
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux*/chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


def render(binary: str, page: pathlib.Path, out: pathlib.Path) -> bool:
    cmd = [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--run-all-compositor-stages-before-draw",
           "--virtual-time-budget=10000", "--no-pdf-header-footer", f"--print-to-pdf={out}", page.resolve().as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return out.exists() and out.stat().st_size > 1000


def main() -> int:
    everything = "--all" in sys.argv
    binary = chrome()
    if not binary:
        print("No Chrome or Chromium found; PDFs not made (they are made on GitHub's runners).")
        return 0
    made, state_file = 0, ROOT / "data" / "pdf_state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        state = {}
    for page in sorted((ROOT / "monthly").glob("*/20??-??.html")) + sorted((ROOT / "weekly").glob("*/20??-W??.html")):
        out, key = page.with_suffix(".pdf"), str(page.relative_to(ROOT))
        print_hash = hashlib.sha256(page.read_bytes()).hexdigest()[:16]
        if not everything and out.exists() and state.get(key) == print_hash:
            continue
        ok = render(binary, page, out)
        print(f"{'ok  ' if ok else 'FAIL'} {out.relative_to(ROOT)}")
        if ok:
            state[key] = print_hash
        made += ok
    state_file.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{made} PDF(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
