#!/usr/bin/env python3
"""PDF copies of the monthly reports, weekly digests and daily briefs, made with the Chrome that GitHub's runners (and most
computers) already have: a .pdf next to each page. A PDF is remade when the report on its page has changed since the
PDF was made (a fingerprint of each report, without the menu and footer around it, is kept in data/pdf_state.json;
file times are no use on GitHub, where a fresh checkout gives every file the same time). Daily briefs get a PDF once
their day is over; those of the last RECENT_DAYS days are remade when they change, older ones only when missing, so
the repository does not fill with PDFs. Free, no Python packages. Without a Chrome or Chromium on the machine it prints a warning and does nothing.

Usage:  python scripts/report_pdf.py [--all]
"""
import glob
import hashlib
import json
import os
import re
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECENT_DAYS = 30


def fingerprint(page: pathlib.Path) -> str:
    """A fingerprint of the report itself (the <article>), so a change to the menu or footer remakes no PDF."""
    text = page.read_text(encoding="utf-8", errors="replace")
    start, end = text.find("<article"), text.rfind("</article>")
    report = text[start:end] if 0 <= start < end else text
    report = re.sub(r'<div class="share".*?</div>', "", report, flags=re.S)   # the share buttons (and the PDF link) are not printed
    return hashlib.sha256(report.encode()).hexdigest()[:16]


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
    made, state_file, new_days = 0, ROOT / "data" / "pdf_state.json", set()
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        state = {}
    import datetime as dt
    today = dt.datetime.now(dt.timezone.utc).date()
    recent = (today - dt.timedelta(days=RECENT_DAYS)).isoformat()
    days = [p for p in sorted((ROOT / "daily").glob("*/20??-??-??.html")) if p.stem < today.isoformat()]
    for page in sorted((ROOT / "monthly").glob("*/20??-??.html")) + sorted((ROOT / "weekly").glob("*/20??-W??.html")) + days:
        out, key = page.with_suffix(".pdf"), str(page.relative_to(ROOT))
        print_hash = fingerprint(page)
        if not everything and out.exists() and (state.get(key) == print_hash or (page.parent.parent.name == "daily" and page.stem < recent)):
            continue
        is_new = not out.exists()
        ok = render(binary, page, out)
        if ok and is_new and page.parent.parent.name == "daily":
            new_days.add(page.stem)
        print(f"{'ok  ' if ok else 'FAIL'} {out.relative_to(ROOT)}")
        if ok:
            state[key] = print_hash
        made += ok
    state_file.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if new_days:                                    # daily pages show their PDF link once the PDF exists
        sys.path.insert(0, str(ROOT / "scripts"))
        import pages
        import pipeline
        cfg = pipeline.load_config()
        pages.write_daily_pages(cfg, sorted(new_days))
        pages.write_daily_listing(cfg)
    print(f"{made} PDF(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
