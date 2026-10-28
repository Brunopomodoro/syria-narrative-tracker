#!/usr/bin/env python3
"""The website's health, search-engine (SEO) and security check, read from the built site in the repository (no
network, no extra packages). Prints a Markdown report: every check with how many pages fail it and a few examples.
Run weekly by the site check task; free.

  Health    broken internal links and files, raw link markup, JSON and feeds that do not parse, a stale update,
            PDFs older than their page, very large pages, "undefined"/"NaN" in page text
  SEO       titles and descriptions (present, length, unique), canonical and hreflang (present, matching, the
            other language exists and points back), one <h1>, social image, page language, JSON-LD that parses,
            the sitemap (every URL exists, every indexable page listed, no noindex page listed), robots.txt,
            images without alt text, the IndexNow key file
  Security  a Content-Security-Policy on every page, scripts only from the site itself, no inline scripts on
            static pages, new-tab links with rel="noopener", no http:// resources, forms over https, no secrets or
            personal email addresses in tracked files, workflows with pinned actions and declared permissions,
            pinned Python packages, the private validation folder untracked

Usage:  python scripts/site_check.py [--json FILE]
"""
import datetime as dt
import html as html_lib
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
from collections import defaultdict
from xml.etree import ElementTree

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", ".github", "validation"}
APP_PAGES = {"index.html", "ar/index.html", "how/en.html", "how/ar.html"}   # the app and the How it works walkthrough: same-origin scripts allowed; every other page has none
SECRETS = [("Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}"), ("AWS key", r"AKIA[0-9A-Z]{16}"),
           ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}"), ("Slack token", r"xox[baprs]-[A-Za-z0-9-]{10,}"),
           ("Google API key", r"AIza[0-9A-Za-z_\-]{35}"), ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
           ("Telegram session or bot token", r"\b\d{8,10}:AA[0-9A-Za-z_\-]{33}\b")]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?:gmail|googlemail|yahoo|hotmail|outlook|icloud|proton|protonmail)\.[a-z]{2,}", re.I)


class Report:
    def __init__(self):
        self.rows = []                                  # (area, check, failures, examples)

    def add(self, area: str, check: str, failures: list):
        self.rows.append((area, check, len(failures), failures[:5]))

    def markdown(self) -> str:
        out, now = [], dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        total = sum(1 for r in self.rows if r[2])
        out.append(f"# Site check, {now}\n\n{len(self.rows)} checks, {total} with findings.\n")
        for area in ("Health", "SEO", "Security"):
            out.append(f"## {area}\n")
            for a, check, n, ex in self.rows:
                if a != area:
                    continue
                out.append(f"- {'OK  ' if not n else 'FIND'} {check}" + (f": {n}" if n else ""))
                out.extend(f"    - {e}" for e in ex)
            out.append("")
        return "\n".join(out)


def site_pages() -> list:
    return sorted(p for p in ROOT.rglob("*.html") if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS))


def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT))


def base_url() -> str:
    try:
        import yaml
        return (yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}).get("site_url", "").rstrip("/") \
            or "https://www.syrianpulse.org"
    except Exception:  # noqa: BLE001
        return "https://www.syrianpulse.org"


def meta(html: str, name: str, attr: str = "name") -> str | None:
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', html)
    return m.group(1) if m else None


def tracked_files() -> list:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
        return [ROOT / f for f in out if f]
    except Exception:  # noqa: BLE001
        return []


def main() -> int:
    R, base = Report(), base_url()
    pages = site_pages()
    html_of = {p: p.read_text(encoding="utf-8", errors="replace") for p in pages}
    head_of = {p: h.split("</head>")[0] for p, h in html_of.items()}
    noindex = {p for p, h in head_of.items() if re.search(r'<meta name="robots" content="[^"]*noindex', h)}
    indexable = [p for p in pages if p not in noindex and p.name not in ("404.html",) and "google" not in p.name]

    # ---------------------------------------------------------------- health
    broken, raw, junk, big = [], [], [], []
    for p, h in html_of.items():
        for u in re.findall(r'(?:href|src)="([^"]+)"', h):
            if u.startswith(("http:", "https:", "mailto:", "#", "data:", "javascript:", "tel:", "//")):
                continue
            path = urllib.parse.unquote(u.split("#")[0].split("?")[0])
            if not path:
                continue
            t = ((ROOT / path.lstrip("/")) if path.startswith("/") else (p.parent / path)).resolve()
            if t.is_dir():
                t = t / "index.html"
            if not t.exists():
                broken.append(f"{rel(p)} -> {u}")
        if re.search(r"\]\([0-9a-f٠-٩]{14}\)", h):
            raw.append(rel(p))
        text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", h, flags=re.S)
        if re.search(r"\bundefined\b|\bNaN\b|\[object Object\]", text):
            junk.append(rel(p))
        if len(h.encode()) > 600_000:
            big.append(f"{rel(p)} ({len(h.encode()) // 1000} KB)")
    R.add("Health", "Internal links and files that exist", broken)
    R.add("Health", "No raw link markup in page text", raw)
    R.add("Health", "No 'undefined', 'NaN' or '[object Object]' in page text", junk)
    R.add("Health", "Pages under 600 KB", big)
    bad_json = []
    for f in (ROOT / "data").rglob("*.json"):
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            bad_json.append(f"{rel(f)}: {str(e)[:60]}")
    R.add("Health", "Data files that parse as JSON", bad_json)
    bad_xml = []
    for f in list(ROOT.glob("feed*.xml")) + [ROOT / "sitemap.xml"]:
        try:
            ElementTree.parse(f)
        except Exception as e:  # noqa: BLE001
            bad_xml.append(f"{rel(f)}: {str(e)[:60]}")
    R.add("Health", "Feeds and sitemap that parse as XML", bad_xml)
    stale = []
    try:
        latest = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(latest["generated_at"].replace("Z", "+00:00"))
        if age > dt.timedelta(hours=8):
            stale.append(f"last update {age.total_seconds() / 3600:.0f} hours ago")
    except Exception as e:  # noqa: BLE001
        stale.append(f"data/latest.json unreadable: {e}")
    R.add("Health", "An update in the last 8 hours", stale)
    sys.path.insert(0, str(ROOT / "scripts"))
    from report_pdf import RECENT_DAYS, fingerprint as pdf_fingerprint
    try:
        made = json.loads((ROOT / "data" / "pdf_state.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        made = {}
    old_pdf = []
    today = dt.datetime.now(dt.timezone.utc).date()
    recent_days = [p for p in ROOT.glob("daily/*/20??-??-??.html")
                   if (today - dt.timedelta(days=RECENT_DAYS)).isoformat() <= p.stem < today.isoformat()]
    for p in list(ROOT.glob("weekly/*/20??-W??.html")) + list(ROOT.glob("monthly/*/20??-??.html")) + recent_days:
        if not p.with_suffix(".pdf").exists():
            old_pdf.append(f"{rel(p)}: no PDF")
        elif made.get(rel(p)) != pdf_fingerprint(p):
            old_pdf.append(f"{rel(p)}: page changed since its PDF was made (remade at the next update)")
    R.add("Health", "Report and daily brief PDFs present and remade after their report changed", old_pdf)

    # ---------------------------------------------------------------- SEO
    titles, no_title, long_title, no_desc, bad_desc, canon, hreflang, h1s, og, lang, ld = (defaultdict(list), [], [], [], [], [], [], [], [], [], [])
    for p in indexable:
        h, hd, r = html_of[p], head_of[p], rel(p)
        m = re.search(r"<title>([^<]*)</title>", hd)
        t = html_lib.unescape(m.group(1).strip()) if m else ""
        if not t:
            no_title.append(r)
        else:
            titles[t].append(r)
            if len(t) > 70:
                long_title.append(f"{r} ({len(t)} characters)")
        d = html_lib.unescape(meta(hd, "description") or "")
        if not d:
            no_desc.append(r)
        elif not 50 <= len(d) <= 170:
            bad_desc.append(f"{r} ({len(d)} characters)")
        c = re.search(r'<link rel="canonical" href="([^"]+)"', hd)
        expected = f"{base}/{r}".replace("/index.html", "/index.html")
        if not c:
            canon.append(f"{r}: missing")
        elif c.group(1) not in (expected, expected.replace("index.html", ""), f"{base}/" if r == "index.html" else expected, f"{base}/ar/" if r == "ar/index.html" else expected):
            canon.append(f"{r}: {c.group(1)}")
        alts = dict(re.findall(r'<link rel="alternate" hreflang="(\w+)" href="([^"]+)"', hd))
        if p.parts[-1] and ("en" in alts or "ar" in alts):
            for lg, url in alts.items():
                f = url.replace(base + "/", "")
                f = f or "index.html"
                f = f + "index.html" if f.endswith("/") else f
                if not (ROOT / f).exists():
                    hreflang.append(f"{r}: {lg} -> {url} (missing)")
                elif lg not in ("x-default",) and f != r:
                    back = dict(re.findall(r'<link rel="alternate" hreflang="(\w+)" href="([^"]+)"', head_of.get(ROOT / f, "")))
                    if not any(v.replace(base + "/", "") in (r, r.replace("index.html", "")) for v in back.values()):
                        hreflang.append(f"{r}: {lg} page does not point back")
        elif r not in ("404.html",):
            hreflang.append(f"{r}: no hreflang")
        if len(re.findall(r"<h1[ >]", h)) != 1 and r not in APP_PAGES:
            h1s.append(f"{r} ({len(re.findall(r'<h1[ >]', h))} h1)")
        if not meta(hd, "og:image", "property"):
            og.append(r)
        if not re.search(r'<html lang="(en|ar)"', h):
            lang.append(r)
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try:
                json.loads(block)
            except Exception as e:  # noqa: BLE001
                ld.append(f"{r}: {str(e)[:50]}")
    R.add("SEO", "Every indexable page has a title", no_title)
    R.add("SEO", "Titles unique", [f"{t[:60]}: {len(v)} pages, e.g. {v[0]}" for t, v in titles.items() if len(v) > 1])
    R.add("SEO", "Titles at most 70 characters (search results cut longer ones)", long_title)
    R.add("SEO", "Every indexable page has a meta description", no_desc)
    R.add("SEO", "Descriptions 50-170 characters", bad_desc)
    R.add("SEO", "Canonical link present and pointing to the page itself", canon)
    R.add("SEO", "English/Arabic hreflang links present, existing and reciprocal", hreflang)
    R.add("SEO", "Exactly one h1 per page", h1s)
    R.add("SEO", "Social sharing image (og:image)", og)
    R.add("SEO", "Page language declared (<html lang>)", lang)
    R.add("SEO", "Structured data (JSON-LD) parses", ld)
    in_map, map_missing, map_extra, map_noindex = set(), [], [], []
    try:
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in ElementTree.parse(ROOT / "sitemap.xml").getroot().findall(".//s:loc", ns):
            f = (loc.text or "").replace(base + "/", "") or "index.html"
            f = f + "index.html" if f.endswith("/") else f
            in_map.add(f)
            if not (ROOT / f).exists():
                map_missing.append(loc.text)
            elif ROOT / f in noindex:
                map_noindex.append(loc.text)
    except Exception as e:  # noqa: BLE001
        map_missing.append(f"sitemap unreadable: {e}")
    map_extra = [rel(p) for p in indexable if rel(p) not in in_map]
    R.add("SEO", "Every sitemap URL exists", map_missing)
    R.add("SEO", "Every indexable page is in the sitemap", map_extra)
    R.add("SEO", "No noindex page in the sitemap", map_noindex)
    robots = (ROOT / "robots.txt").read_text() if (ROOT / "robots.txt").exists() else ""
    R.add("SEO", "robots.txt allows crawling and names the sitemap",
          [] if ("Sitemap:" in robots and not re.search(r"^Disallow:\s*/\s*$", robots, re.M)) else ["robots.txt"])
    no_alt = [rel(p) for p, h in html_of.items() if re.search(r"<img(?![^>]*\balt=)[^>]*>", h)]
    R.add("SEO", "Images have alt text", no_alt)
    key_issue = []
    try:
        import yaml
        key = (yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}).get("indexnow_key", "")
        if key and not (ROOT / f"{key}.txt").exists():
            key_issue.append(f"{key}.txt missing")
    except Exception:  # noqa: BLE001
        pass
    R.add("SEO", "IndexNow key file in place", key_issue)

    # ---------------------------------------------------------------- security
    no_csp, scripts, inline, opener, http, forms = [], [], [], [], [], []
    for p, h in html_of.items():
        r, hd = rel(p), head_of[p]
        csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', hd)
        if not csp:
            no_csp.append(r)
        elif r not in APP_PAGES and "script-src 'none'" not in csp.group(1):
            no_csp.append(f"{r}: scripts not blocked ({csp.group(1)[:60]})")
        for src in re.findall(r'<script[^>]*\bsrc="([^"]+)"', h):
            if src.startswith(("http:", "https:", "//")):
                scripts.append(f"{r}: {src}")
        if r not in APP_PAGES and re.search(r"<script(?![^>]*application/ld\+json)(?![^>]*\bsrc=)[^>]*>\s*\S", h):
            inline.append(r)
        for tag in re.findall(r"<a [^>]*target=\"_blank\"[^>]*>", h):
            if "noopener" not in tag:
                opener.append(f"{r}: {tag[:80]}")
        for u in re.findall(r'(?:src|href|action)="(http://[^"]+)"', h):
            http.append(f"{r}: {u}")
        for act in re.findall(r'<form[^>]*action="([^"]+)"', h):
            if not act.startswith("https://"):
                forms.append(f"{r}: {act}")
    R.add("Security", "Content-Security-Policy on every page (scripts blocked outside the app)", no_csp)
    R.add("Security", "Scripts only from the site itself", scripts)
    R.add("Security", "No inline scripts on static pages", inline)
    R.add("Security", "New-tab links carry rel=\"noopener\"", opener)
    R.add("Security", "No http:// resources or links (mixed content)", http)
    R.add("Security", "Forms submit over https", forms)
    secrets, emails = [], []
    for f in tracked_files():
        if f.suffix in (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".ttf") or not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for label, pat in SECRETS:
            if re.search(pat, text):
                secrets.append(f"{rel(f)}: looks like a {label}")
        if f.suffix in (".html", ".xml", ".json", ".js", ".txt", ".csv") and not rel(f).startswith((".github", "scripts")):
            for e in set(EMAIL.findall(text)):
                emails.append(f"{rel(f)}: {e[:3]}…@{e.split('@')[1]}")
    R.add("Security", "No secrets (API keys, tokens, private keys) in tracked files", secrets)
    R.add("Security", "No personal email addresses in published files", emails)
    wf = []
    for f in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = f.read_text(encoding="utf-8")
        for u in re.findall(r"uses:\s*([^\s#]+)", text):
            if "@" in u and not re.search(r"@[0-9a-f]{40}$", u):
                wf.append(f"{f.name}: {u} not pinned to a commit")
        if not re.search(r"^permissions:", text, re.M):
            wf.append(f"{f.name}: no permissions block (gets the default token rights)")
        if "pull_request_target" in text:
            wf.append(f"{f.name}: uses pull_request_target")
        if re.search(r"echo[^\n]*\$\{\{\s*secrets\.", text):
            wf.append(f"{f.name}: prints a secret")
    R.add("Security", "Workflows: actions pinned, permissions declared, secrets never printed", wf)
    req = (ROOT / "requirements.txt").read_text() if (ROOT / "requirements.txt").exists() else ""
    R.add("Security", "Python packages pinned to versions",
          [l for l in req.splitlines() if re.match(r"^[A-Za-z0-9][\w.\-\[\],]*\s*([<>=!~;]|$)", l) and "==" not in l])
    R.add("Security", "The private validation folder is not tracked",
          [rel(f) for f in tracked_files() if rel(f).startswith("validation/")])

    print(R.markdown())
    if "--json" in sys.argv:
        out = pathlib.Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps({"time": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   "checks": [{"area": a, "check": c, "failures": n, "examples": e} for a, c, n, e in R.rows]},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
