#!/usr/bin/env python3
"""Tells search engines that take part in IndexNow (Bing, Yandex, Seznam, Naver and others) which pages changed in
the last commit, so new daily briefs, stories and analyses are crawled within hours. The key in config.yaml
(indexnow_key) is public by design: search engines check it against the file <key>.txt at the site's root.
Never fails the workflow.

Usage:  python scripts/indexnow.py            pages changed in the last commit
        python scripts/indexnow.py FILE ...   these files
"""
import json
import pathlib
import subprocess
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402

PAGES = ("stories/", "daily/", "weekly/", "monthly/", "experts/", "sources/")


def url_of(base: str, path: str) -> str | None:
    if path == "index.html":
        return base + "/"
    if path == "ar/index.html":
        return base + "/ar/"
    if path.endswith(".html") and path.startswith(PAGES):
        return f"{base}/{path}"
    return None


def main() -> int:
    cfg = P.load_config()
    key = str(cfg.get("indexnow_key") or "").strip()
    base = str(cfg.get("site_url") or "").rstrip("/")
    if not key or not base:
        print("IndexNow: no key or site_url in config.yaml; skipped.")
        return 0
    files = sys.argv[1:] or subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], capture_output=True, text=True).stdout.split()
    urls = sorted({u for u in (url_of(base, f) for f in files) if u})
    if not urls:
        print("IndexNow: no changed pages.")
        return 0
    host = base.split("://", 1)[1]
    try:
        r = requests.post("https://api.indexnow.org/indexnow", timeout=30, headers={"Content-Type": "application/json; charset=utf-8"},
                          data=json.dumps({"host": host, "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls[:10000]}))
        print(f"IndexNow: {len(urls)} pages sent, answer {r.status_code}.")
    except requests.RequestException as e:
        print(f"IndexNow: not sent ({type(e).__name__}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
