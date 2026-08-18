#!/usr/bin/env python3
"""corpus.py — shared corpus loading utilities.

The raw fetch writes one CSV per (category, year). This module:
  * unifies them into a single de-duplicated DataFrame
  * tokenizes on demand (shared by lexicon/annotation stages)
  * writes the small committed sample (data/corpus/sample) used by CI
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

RAW_DIR = ROOT / CFG["corpus"]["raw_dir"]
STOP_FILE = ROOT / "data" / "stopwords_en.txt"

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+\-.]*")
_SENT_RE = re.compile(r"[.!?;]+")

_STOP = None


def stopwords() -> set[str]:
    global _STOP
    if _STOP is None:
        _STOP = set()
        for line in STOP_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                _STOP.add(line)
    return _STOP


def tokenize(text: str) -> list[str]:
    """Lowercase tokenization with sentence boundaries removed.

    Returns tokens that are not stopwords and not length-1 noise.
    Interior stopwords are preserved so phrases like "state of the art"
    can form; sentence punctuation is dropped via _SENT_RE splitting.
    """
    toks = []
    if _STOP is None:
        stopwords()
    for sent in _SENT_RE.split((text or "").lower()):
        for t in _TOKEN_RE.findall(sent):
            if len(t) <= 1:
                continue
            if t in _STOP:
                continue
            if t.isdigit():
                continue
            toks.append(t)
    return toks


def load_corpus_df(use_sample: bool = False) -> pd.DataFrame:
    """Unified, de-duplicated corpus DataFrame.

    Columns: arxiv_id, title, abstract, primary_cat, cats, published, year
    Deduplication keeps the first occurrence (stable category order).
    """
    if use_sample:
        fp = ROOT / CFG["corpus"]["sample_dir"] / "sample.parquet"
        return pd.read_parquet(fp)

    files = sorted(RAW_DIR.glob("cat=*/year=*/papers.csv"))
    if not files:
        raise FileNotFoundError(
            "No raw corpus found. Run: python scripts/fetch_arxiv.py")
    frames = []
    for fp in files:
        year = int(fp.parent.name.split("=")[1])
        cat = fp.parent.parent.name.split("=")[1]
        df = pd.read_csv(fp, dtype={"arxiv_id": str}, keep_default_na=False)
        df["year"] = year
        df["primary_cat"] = cat
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["arxiv_id"], keep="first")
    df = df.sort_values(["year", "primary_cat"]).reset_index(drop=True)
    return df


def save_sample(n_per_cat_year: int = 15) -> None:
    """Write a tiny stratified sample for CI / out-of-the-box runs."""
    df = load_corpus_df()
    out_dir = ROOT / CFG["corpus"]["sample_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = __import__("numpy").random.default_rng(CFG["random_seed"])
    picked = []
    for (year, cat), g in df.groupby(["year", "primary_cat"]):
        idx = rng.choice(len(g), size=min(n_per_cat_year, len(g)), replace=False)
        picked.append(g.iloc[idx])
    sample = pd.concat(picked, ignore_index=True)
    sample.to_parquet(out_dir / "sample.parquet", index=False)
    print(f"sample: {len(sample)} papers -> {out_dir / 'sample.parquet'}")


if __name__ == "__main__":
    save_sample()
