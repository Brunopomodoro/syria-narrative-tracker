#!/usr/bin/env python3
"""Rebuild every static page from the archive: a page per archived story (both languages), the story
listings, the weekly listings and feeds, the sitemap and the crawlable block in index.html.
Free (no Claude call). Run it after changing scripts/pages.py.

Usage:  python scripts/rebuild_pages.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pages  # noqa: E402
import pipeline as P  # noqa: E402


def main() -> int:
    cfg = P.load_config()
    latest_by_key, latest_run = {}, None
    cache = {}
    for date in archive.all_days():
        day = archive.load_day(date)
        cache[date] = day
        for r in day.get("runs") or []:
            for n in r.get("narratives") or []:
                n.setdefault("key", archive.story_key(n))
                latest_by_key[n["key"]] = (r, n)        # the last run's analysis of each story wins
            latest_run = r
    if not latest_run:
        print("No archive yet.")
        return 0
    # the story index: rebuilt from every run, oldest first
    index = {}
    for date in archive.all_days():
        for r in cache[date].get("runs") or []:
            pages.update_story_index({"generated_at": r.get("generated_at"), "narratives": r.get("narratives") or []})
    written = 0
    for key, (r, n) in latest_by_key.items():
        written += pages.write_story_pages(cfg, {"generated_at": r.get("generated_at")}, [n], cache)
    latest = archive._load(archive.DATA / "latest.json", {}) or {"generated_at": latest_run.get("generated_at"), "narratives": latest_run.get("narratives")}
    pages.write_story_listing(cfg)
    digests = pages.load_digests()
    for d in [archive._load(pages.DATA / "weekly" / f"{x['week']}.json", None) for x in digests]:
        if d:
            pages.write_weekly_pages(cfg, d)
    pages.write_weekly_listing(cfg, digests)
    pages.write_feeds(cfg, digests)
    reviews = pages.load_reviews()
    for r in [archive._load(pages.DATA / "monthly" / f"{x['month']}.json", None) for x in reviews]:
        if r:
            pages.write_monthly_pages(cfg, r)
    pages.write_monthly_listing(cfg, reviews)
    pages.write_monthly_feeds(cfg, reviews)
    daily = pages.write_daily_pages(cfg, archive.all_days())
    pages.write_daily_listing(cfg)
    pages.write_sitemap(cfg, digests, reviews)
    pages.write_privacy_pages(cfg)
    pages.prerender_index(cfg, latest)
    print(f"{written} story pages, {len(index) or len(pages.load_story_index())} stories in the index, {daily} daily briefs, {len(digests)} digests, {len(reviews)} monthly reports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
