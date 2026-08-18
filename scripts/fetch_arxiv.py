#!/usr/bin/env python3
"""fetch_arxiv.py — pull arXiv metadata (title+abstract+dates) for tracked
categories and years via the official arXiv Atom API.

Why this source: arXiv is open, key-less, and directly reachable without a
proxy; every other signal source (Semantic Scholar, GitHub, PyPI, funding
databases) is documented as an optional extension in docs/data_sources.md.

Sampling note (read before interpreting anything):
  The default per-category-year cap (config.yaml -> corpus.per_year_cap)
  keeps the fetch small enough to run on a laptop and inside CI. Papers are
  taken in reverse submission-date order, so the sample is the *most recent
  N papers of that category-year*. Frequencies are therefore comparable
  within a category across years, but NOT across categories with different
  sampling rates. For production-grade numbers run with --no-cap and the
  full year range (see docs/data_sources.md for the official metadata dump).

Usage:
  python scripts/fetch_arxiv.py                 # config-driven
  python scripts/fetch_arxiv.py --year 2024     # single year
  python scripts/fetch_arxiv.py --no-cap        # full fetch (slow, polite)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

API = "https://export.arxiv.org/api/query"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ")
    s = TAG_RE.sub(" ", s)
    # arXiv admin notes are boilerplate, drop them
    s = re.sub(r"arxiv admin note[^.]*\.", " ", s, flags=re.I)
    return WS_RE.sub(" ", s).strip()


def fetch_page(cat: str, year: int, start: int, max_results: int,
               delay: float, retries: int):
    """One paginated call; returns list of dicts or raises."""
    q = f"cat:{cat} AND submittedDate:[{year}01010000 TO {year}12312359]"
    params = {
        "search_query": q,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": start,
        "max_results": max_results,
    }
    last_err = None
    sess = requests.Session()
    sess.trust_env = False  # arXiv is directly reachable; skip dead local proxies
    for attempt in range(retries):
        try:
            r = sess.get(API, params=params, timeout=45)
            if r.status_code == 429:
                # arXiv rate limit: back off long, then retry
                wait = 60 * (attempt + 1)
                print(f"  [429] {cat}/{year} start={start} sleeping {wait}s",
                      flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            root = ET.fromstring(r.content)
            out = []
            for entry in root.findall("a:entry", NS):
                eid = (entry.findtext("a:id", default="", namespaces=NS)
                       .strip().rsplit("/", 1)[-1])
                title = clean_text(entry.findtext("a:title", default="", namespaces=NS))
                summary = clean_text(entry.findtext("a:summary", default="", namespaces=NS))
                published = entry.findtext("a:published", default="", namespaces=NS)
                cats = [c.get("term") for c in entry.findall("arxiv:category", NS)]
                primary = (entry.find("arxiv:primary_category", NS)
                           .get("term") if entry.find("arxiv:primary_category", NS) is not None
                           else (cats[0] if cats else ""))
                out.append({
                    "arxiv_id": eid,
                    "title": title,
                    "abstract": summary,
                    "primary_cat": primary,
                    "cats": " ".join(cats),
                    "published": published[:10],
                    "year": year,
                })
            return out
        except Exception as e:  # noqa: BLE001 — network flakiness
            last_err = e
            time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"fetch failed cat={cat} year={year} start={start}: {last_err}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=None, help="only this year")
    ap.add_argument("--no-cap", action="store_true",
                    help="fetch every paper (no per-category-year cap)")
    args = ap.parse_args()

    cats = CFG["categories"]
    years = [args.year] if args.year else CFG["corpus"]["years"]
    cap = 0 if args.no_cap else CFG["corpus"]["per_year_cap"]
    delay = CFG["corpus"]["api_delay"]
    retries = CFG["corpus"]["api_retries"]
    raw_dir = ROOT / CFG["corpus"]["raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    cache_path = ROOT / CFG["corpus"]["dir"] / "_fetched_ids.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    total = 0
    for c in cats:
        cat = c["cat"]
        for year in years:
            out_dir = raw_dir / f"cat={cat}" / f"year={year}"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_csv = out_dir / "papers.csv"
            key = f"{cat}/{year}"
            done = set(cache.get(key, []))
            # pre-existing rows
            if out_csv.exists():
                import csv
                with open(out_csv, newline="", encoding="utf-8") as fh:
                    done |= {row["arxiv_id"] for row in csv.DictReader(fh)}
            if cap and len(done) >= cap:
                print(f"[{key}] already at cap ({len(done)}) — skip", flush=True)
                continue
            start = 0
            fetched_this = 0
            empty_pages = 0
            while True:
                if cap and fetched_this >= cap:
                    break
                page = fetch_page(cat, year, start, 100, delay, retries)
                # NOTE: cat: queries match any category field, so many hits
                # have a different primary category. We keep them (the raw
                # file is a *sampling frame* for the searched category) but
                # retain each paper's true primary_cat for field attribution.
                new_rows = [p for p in page if p["arxiv_id"] not in done]
                if new_rows:
                    import csv
                    fresh = not out_csv.exists()
                    with open(out_csv, "a", newline="", encoding="utf-8") as fh:
                        w = csv.DictWriter(fh, fieldnames=list(new_rows[0].keys()))
                        if fresh:
                            w.writeheader()
                        for p in new_rows:
                            w.writerow(p)
                    done |= {p["arxiv_id"] for p in new_rows}
                    fetched_this += len(new_rows)
                    total += len(new_rows)
                    print(f"[{key}] +{len(new_rows)} (total {fetched_this})",
                          flush=True)
                if len(page) < 100:
                    empty_pages += 1
                    if empty_pages >= 2 or len(page) == 0:
                        break
                start += 100
                time.sleep(delay)
            cache[key] = sorted(done)
            cache_path.write_text(json.dumps(cache))
    print(f"\nDONE: {total} new papers fetched.")


if __name__ == "__main__":
    main()
