# Syria Narrative Tracker

A website that updates itself every hour with the main narratives in public Syrian online discussion, and the tone around each one.

It reads Arabic, Kurdish and English posts from about 50 sources: Telegram channels (official, independent, opposition-origin, Kurdish-run, local, minority-community and regional outlets), news sites, YouTube comments (by search and under selected channels), Reddit, X and, optionally, Telegram comments and groups, Bluesky, Threads and Instagram hashtag posts.

- `index.html` is the website (Tracker, Trends, Reports, Data and About pages); `stories/`, `daily/`, `weekly/` and `monthly/` hold the generated story pages, daily briefs, weekly digests and monthly reports, each with share links and a print layout (digests and reports also as PDFs, made by `scripts/report_pdf.py` with the Chrome on GitHub's runners); `feed.xml` and `feed-ar.xml` are the digest feeds, `feed-monthly.xml` and `feed-monthly-ar.xml` the report feeds (full text, for newsletter services)
- `config.yaml` holds your settings and sources (the only file you normally edit)
- `scripts/pipeline.py` collects posts, asks Claude to find narratives, and writes `data/` (including `data/snapshots/`, the full analysis of every hour, which the website opens when you click a past hour), `data/stories.json` and `data/headlines.json` (what the website's search box looks through: stories from the past 14 days and outlet headlines from the past 7 days; posts by individuals are never stored)
- `.github/workflows/update.yml` runs the pipeline every hour on GitHub Actions

## Security

- **Secrets** live only in the repository's Actions secrets (see GUIDE.md); none are in the code or the git history. `.gitignore` blocks env files, keys and session files.
- **The page** loads its script from `assets/app.js` and its policy (`<meta>` in `index.html`, `_headers`) allows scripts only from this origin: injected markup cannot run code. Generated story and digest pages allow no scripts at all. All text from posts and from the model is escaped before it reaches a page. After editing `assets/app.js`, bump the `?v=` on its `<script>` tag so browsers fetch the new file.
- **Headers.** `_headers` adds framing protection, HSTS and the rest. Cloudflare Pages and Netlify apply it automatically. GitHub Pages ignores it; if the site stays on GitHub Pages behind Cloudflare, add the same headers once under Cloudflare, Rules, Transform Rules, Modify Response Header.
- **Individuals' posts are never published.** The test-sources task logs only source, platform, language and length, never post text, because Actions logs of a public repository are public. The validation-sample task refuses to run unless the repository is private, because its artifact contains excerpts of individuals' posts.
- **Dependencies.** Dependabot opens a weekly pull request for outdated actions and Python packages.

## Data files

Everything the tracker produces is in `data/` and can be downloaded or read directly (licence: CC BY 4.0, see the website's Data page):

- `data/archive/YYYY-MM-DD.json`: every run of that day in full, plus that day's outlet headlines. Permanent.
- `data/archive/index.json`: one summary per day: volume and tone overall, per theme, per language and per source type. Feeds the Trends page.
- `data/exports/YYYY-MM/`: flat tables per month for spreadsheets, R and Python: `runs.csv`, `stories.csv` (one row per story per run), `themes.csv`, `headlines.csv`, and `stories.json` (one entry per story with its full analysis). `data/exports/index.json` lists them with column names.
- `data/methodology.json`: sources, themes, sampling settings, model, the exact analysis instructions, and the method changelog.
- `data/latest.json`, `data/history.json`, `data/snapshots/`, `data/stories.json`, `data/headlines.json`: what the live site uses (the last 14 days).

- `data/weekly/`: the weekly digests (text in both languages and the week's numbers).
- `data/validation.json`: the results of the validation study, once one has been run (GUIDE.md, "Validation study").

Posts by individuals are never stored; the archive holds analyses and outlet headlines only. Licence: CC BY 4.0 (`LICENSE-DATA.md`); citation details in `CITATION.cff` and on the website's Data page.

Maintenance jobs (Actions -> Maintenance -> Run workflow): rebuild the index and downloads after editing themes or events in `config.yaml`, give themes to stories archived before themes existed, or rebuild the archive from the git history.

**Setup instructions: see [GUIDE.md](GUIDE.md).**

Run it on your own computer (optional):

```
pip install -r requirements.txt
python scripts/pipeline.py --dry-run     # test your sources, no cost
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/pipeline.py               # full run, writes data/
python -m http.server                    # then open http://localhost:8000
```
