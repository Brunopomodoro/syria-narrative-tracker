#!/usr/bin/env python3
"""PDF copies of the monthly reports and weekly digests, made with the Chrome that GitHub's runners (and most
computers) already have: a .pdf next to each page. A PDF is remade when its page is newer. Free, no Python
packages. Without a Chrome or Chromium on the machine it prints a warning and does nothing.

Usage:  python scripts/report_pdf.py [--all]
"""
import glob
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
    made = 0
    for page in sorted((ROOT / "monthly").glob("*/20??-??.html")) + sorted((ROOT / "weekly").glob("*/20??-W??.html")):
        out = page.with_suffix(".pdf")
        if not everything and out.exists() and out.stat().st_mtime >= page.stat().st_mtime:
            continue
        ok = render(binary, page, out)
        print(f"{'ok  ' if ok else 'FAIL'} {out.relative_to(ROOT)}")
        made += ok
    print(f"{made} PDF(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
