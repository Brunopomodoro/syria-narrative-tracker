#!/usr/bin/env python3
"""The site in a real browser: the main pages and every tab of the app, in English and Arabic, at desktop and phone
width, checking for script errors, failed requests to the site, sideways scrolling on phones, pages with almost no
text, and "undefined"/"NaN" in what readers see. Serves the repository locally; needs Playwright with a Chromium
(run where the site check task runs; not on GitHub). Free.

Usage:  python scripts/browser_check.py [extra pages ...]
"""
import functools
import glob
import http.server
import pathlib
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ["/", "/#experts", "/#trends", "/#reports", "/#data", "/#about",
         "/ar/", "/ar/#experts", "/ar/#trends", "/ar/#reports", "/ar/#data", "/ar/#about",
         "/experts/en/index.html", "/experts/ar/index.html", "/sources/en.html", "/sources/ar.html",
         "/timeline/en.html", "/timeline/ar.html", "/contact/en.html", "/contact/ar.html",
         "/stories/en/index.html", "/stories/ar/index.html", "/weekly/en/index.html", "/daily/ar/index.html", "/monthly/en/index.html"]


def newest(pattern: str) -> list:
    found = sorted(glob.glob(str(ROOT / pattern)))
    return ["/" + str(pathlib.Path(found[-1]).relative_to(ROOT))] if found else []


def main() -> int:
    from playwright.sync_api import sync_playwright
    pages = PAGES + newest("weekly/en/20??-W??.html") + newest("weekly/ar/20??-W??.html") + newest("monthly/en/20??-??.html") \
        + newest("experts/en/20??-W??.html") + newest("experts/ar/20??-??-??.html") + newest("stories/en/20??-*.html") + sys.argv[1:]
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))), None)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        for width, height in ((1280, 900), (390, 844)):
            ctx = browser.new_context(viewport={"width": width, "height": height})
            for url in pages:
                pg, errs = ctx.new_page(), []
                pg.on("console", lambda m: errs.append(f"console error: {m.text[:120]}") if m.type == "error" and "fonts.g" not in m.text and "ERR_CERT" not in m.text else None)
                pg.on("pageerror", lambda e: errs.append(f"script error: {str(e)[:120]}"))
                pg.on("response", lambda r: errs.append(f"HTTP {r.status}: {r.url[len(base):]}") if r.status >= 400 and r.url.startswith(base) else None)
                pg.goto(base + url, wait_until="networkidle")
                pg.wait_for_timeout(600)
                info = pg.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
                    text: document.body.innerText.length, bad: (document.body.innerText.match(/\\bundefined\\b|\\bNaN\\b|\\[object Object\\]/g) || []).slice(0, 3)})""")
                if info["sw"] > info["cw"] + 1:
                    errs.append(f"sideways scrolling ({info['sw']} > {info['cw']} px)")
                if info["text"] < 300:
                    errs.append(f"almost no text ({info['text']} characters)")
                if info["bad"]:
                    errs.append(f"bad values shown: {info['bad']}")
                if errs:
                    problems.append(f"{width}px {url}: " + "; ".join(errs[:4]))
                pg.close()
            ctx.close()
        browser.close()
    server.shutdown()
    print(f"# Browser check\n\n{len(pages) * 2} page views, {len(problems)} with problems.\n")
    print("\n".join(f"- {x}" for x in problems) or "- none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
