#!/usr/bin/env python3
"""annotate.py — tag each paper with lexicon phrases; aggregate year counts.

Approach: for each paper, build its own set of n-grams (n = 1..max_n) once,
then test lexicon phrases for membership in that set (paper-side iteration:
~10^3 lookups per paper instead of 10^4+ lexicon-side lookups).

Outputs:
  data/annotation/year=YYYY.csv         arxiv_id, phrases ('|'-joined)
  data/annotation/phrase_year_counts.csv  term, year, freq
  data/annotation/phrase_field_counts.csv term, field, year, freq
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from corpus import load_corpus_df, tokenize  # noqa: E402

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

FIELD_OF_CAT = {c["cat"]: c["field"] for c in CFG["categories"]}


def load_lexicon() -> tuple[dict, list]:
    """Returns (set of phrase tuples, lexicon rows sorted by freq desc)."""
    fp = ROOT / CFG["paths"]["lexicon"]
    rows = []
    with open(fp, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            term = r["term"].strip().lower()
            rows.append((tuple(term.split()), int(r["freq"])))
    rows.sort(key=lambda r: -r[1])
    return {p for p, _ in rows}, rows


def paper_ngrams(tokens, max_n):
    """Set of all contiguous n-grams (n=1..max_n) of the token list."""
    ngrams = set(tokens)
    for n in range(2, max_n + 1):
        for i in range(len(tokens) - n + 1):
            ngrams.add(tuple(tokens[i:i + n]))
    return ngrams


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    lex_set, lex_ranked = load_lexicon()
    rank = {p: i for i, (p, _) in enumerate(lex_ranked)}
    max_n = CFG["lexicon"]["max_n"]
    top_k = CFG["lexicon"]["top_k_per_paper"]
    ann_dir = ROOT / CFG["paths"]["annotation_dir"]

    print("[annotate] loading corpus ...", flush=True)
    df = load_corpus_df(use_sample=args.sample)
    text = (df["title"].fillna("") + ". " + df["abstract"].fillna(""))
    years = df["year"].tolist()
    cats = df["primary_cat"].tolist()

    pyc = Counter()   # (term, year) -> freq
    pfc = Counter()   # (term, field, year) -> freq

    (ann_dir / "year").mkdir(parents=True, exist_ok=True)
    per_year = {}     # year -> csv.writer

    n_papers = len(df)
    for i in range(n_papers):
        year = int(years[i])
        toks = tokenize(text.iloc[i])
        ng = paper_ngrams(toks, max_n)
        matched = [p for p in ng if p in lex_set]
        matched.sort(key=lambda p: rank[p])
        matched = matched[:top_k]
        if not matched:
            continue
        field = FIELD_OF_CAT.get(cats[i], "Other")
        for p in matched:
            term = " ".join(p)
            pyc[(term, year)] += 1
            pfc[(term, field, year)] += 1
        if year not in per_year:
            fp = ann_dir / "year" / f"year={year}.csv"
            fh = open(fp, "w", newline="", encoding="utf-8")
            per_year[year] = (fh, csv.writer(fh))
            per_year[year][1].writerow(["arxiv_id", "phrases"])
        per_year[year][1].writerow(
            [df["arxiv_id"].iloc[i], "|".join(" ".join(p) for p in matched)])
        if (i + 1) % 5000 == 0:
            print(f"[annotate] {i + 1}/{n_papers}", flush=True)

    for fh, _w in per_year.values():
        fh.close()

    with open(ann_dir / "phrase_year_counts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["term", "year", "freq"])
        for (term, year), c in sorted(pyc.items()):
            w.writerow([term, year, c])
    with open(ann_dir / "phrase_field_counts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["term", "field", "year", "freq"])
        for (term, field, year), c in sorted(pfc.items()):
            w.writerow([term, field, year, c])
    print(f"[annotate] done: {len(pyc)} term-year cells, {len(pfc)} term-field-year cells")


if __name__ == "__main__":
    main()
