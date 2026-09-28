#!/usr/bin/env python3
"""Recompute data/archive/index.json, every month's downloads and data/methodology.json from the archive.
Free (no Claude call). Run it after editing themes, events or the changelog in config.yaml.

Usage:  python scripts/rebuild_index.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import archive  # noqa: E402
import pipeline as P  # noqa: E402


def main() -> int:
    cfg = P.load_config()
    index = archive.update_index(cfg, None)
    months = sorted({d[:7] for d in archive.all_days()})
    archive.write_exports(cfg, months)
    archive.write_methodology(cfg, P.system_prompt(cfg), P.FORMAT_VERSION)
    print(f"Index: {len(index['days'])} days ({index['first_day']} to {index['last_day']}); exports for {', '.join(months) or 'no months'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
