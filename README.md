# Syria narrative tracker

A website that updates itself every hour with the main narratives in public Syrian online discussion, and the tone around each one.

- `index.html` is the website
- `config.yaml` holds your settings and sources (the only file you normally edit)
- `scripts/pipeline.py` collects posts, asks Claude to find narratives, and writes `data/`
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
