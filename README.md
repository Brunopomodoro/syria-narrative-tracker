# Syria Narrative Tracker

A website that updates itself every hour with the main narratives in public Syrian online discussion, and the tone around each one.

It reads Arabic, Kurdish and English posts from about 50 sources: Telegram channels (official, independent, opposition-origin, Kurdish-run, local, minority-community and regional outlets), news sites, YouTube comments (by search and under selected channels), Reddit, X and, optionally, Telegram comments and groups, Bluesky, Threads and Instagram hashtag posts.

- `index.html` is the website (Tracker, Trends, Data and About pages); `stories/` and `weekly/` hold the generated story pages and weekly digests; `feed.xml` and `feed-ar.xml` are the digest feeds
- `config.yaml` holds your settings and sources (the only file you normally edit)
- `scripts/pipeline.py` collects posts, asks Claude to find narratives, and writes `data/` (including `data/snapshots/`, the full analysis of every hour, which the website opens when you click a past hour), `data/stories.json` and `data/headlines.json` (what the website's search box looks through: stories from the past 14 days and outlet headlines from the past 7 days; posts by individuals are never stored)
- `.github/workflows/update.yml` runs the pipeline every hour on GitHub Actions

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

## Shayfak (شايفك)

`shayfak/` holds a second site that shares this repository: an accountability directory of the transitional government's officials with a monthly, anonymous trust vote. Its roster is kept up to date by `.github/workflows/shayfak-update.yml`. Setup and the privacy model are in [shayfak/README.md](shayfak/README.md).
