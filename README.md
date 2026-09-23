# Syria Narrative Tracker

A website that updates itself every hour with the main narratives in public Syrian online discussion, and the tone around each one.

It reads Arabic, Kurdish and English posts from about 30 sources: Telegram channels (official, independent, opposition-origin, Kurdish-run and regional outlets), news sites, YouTube comments, Reddit, X and, optionally, Telegram comments and Bluesky.

- `index.html` is the website
- `config.yaml` holds your settings and sources (the only file you normally edit)
- `scripts/pipeline.py` collects posts, asks Claude to find narratives, and writes `data/` (including `data/snapshots/`, the full analysis of every hour, which the website opens when you click a past hour), `data/stories.json` and `data/headlines.json` (what the website's search box looks through: stories from the past 14 days and outlet headlines from the past 7 days; posts by individuals are never stored)
- `.github/workflows/update.yml` runs the pipeline every hour on GitHub Actions

**Setup instructions: see [GUIDE.md](GUIDE.md).**

Run it on your own computer (optional):

```
pip install -r requirements.txt
python scripts/pipeline.py --dry-run     # test your sources, no cost
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/pipeline.py               # full run, writes data/
python -m http.server                    # then open http://localhost:8000
```
