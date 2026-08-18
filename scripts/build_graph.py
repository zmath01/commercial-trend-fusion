#!/usr/bin/env python3
"""build_graph.py — per-year and cumulative concept co-occurrence graphs.

Nodes = phrases (frequency >= hot_min_freq in the window).
Edges  = co-occurrence in the same paper, weight = number of papers
         containing both phrases (>= min_edge_weight).

Storage: scipy.sparse CSR — O(V + E) memory instead of Python dicts,
which is the concrete scaling difference vs naive implementations.

Outputs under data/graphs/:
  year=YYYY/{nodes.csv, edges.npz, meta.json}
  cum_YYYY_YYYY/{nodes.csv, edges.npz, meta.json}
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)


def read_annotation_years(years):
    """Yield (arxiv_id, phrases) across the requested year files."""
    ann = ROOT / CFG["paths"]["annotation_dir"] / "year"
    for y in years:
        fp = ann / f"year={y}.csv"
        if not fp.exists():
            continue
        with open(fp, newline="", encoding="utf-8") as fh:
            for row in csv.reader(fh):
                if not row or len(row) < 2:
                    continue
                phrases = [p for p in row[1].split("|") if p]
                yield row[0], phrases


def read_excluded_terms() -> set[str]:
    """Generic unigrams + boilerplate phrases excluded from graph nodes."""
    out = set()
    for name in ("generic_unigrams.txt", "boilerplate_phrases.txt"):
        fp = ROOT / "data" / name
        if not fp.exists():
            continue
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                out.add(line)
    return out


def build_graph(years: list[int]) -> tuple[list[str], sp.csr_matrix, dict]:
    """Build the co-occurrence graph for the given year window."""
    hot_min = CFG["annotation"]["hot_min_freq"]
    edge_min = CFG["graph"]["min_edge_weight"]
    excluded = read_excluded_terms()

    freq = Counter()
    doc_ph = {}
    for aid, phrases in read_annotation_years(years):
        doc_ph[aid] = phrases
        for p in phrases:
            freq[p] += 1

    # graph nodes = hot phrases minus generic unigrams / boilerplate phrases
    # (both would act as universal bridges and corrupt conductance values)
    hot = {p for p, c in freq.items() if c >= hot_min and p not in excluded}
    terms = sorted(hot)
    tid = {t: i for i, t in enumerate(terms)}

    edge_cnt = Counter()
    for aid, phrases in doc_ph.items():
        hs = [p for p in phrases if p in tid]
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                a, b = hs[i], hs[j]
                if a < b:
                    edge_cnt[(a, b)] += 1
                else:
                    edge_cnt[(b, a)] += 1

    rows, cols, data = [], [], []
    for (a, b), c in edge_cnt.items():
        if c >= edge_min:
            rows.append(tid[a])
            cols.append(tid[b])
            data.append(c)
    coo = sp.coo_matrix((data, (rows, cols)), shape=(len(terms), len(terms)))
    csr = coo.tocsr()
    csr = csr + csr.T  # symmetrize (defensive; we already ordered pairs)
    return terms, csr, dict(freq)


def save_graph(terms, csr, freq, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "nodes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "term", "freq"])
        for i, t in enumerate(terms):
            w.writerow([i, t, freq.get(t, 0)])
    coo = csr.tocoo()
    np.savez(out_dir / "edges.npz",
             rows=coo.row, cols=coo.col, data=coo.data,
             shape=np.array(coo.shape))
    with open(out_dir / "meta.json", "w", encoding="utf-8") as fh:
        json.dump({"n_nodes": len(terms), "n_edges": coo.nnz // 2,
                   "n_weighted_edges": coo.nnz}, fh, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=str, default=None,
                    help="comma list or RANGE like 2019-2022; default = all config years")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    all_years = CFG["corpus"]["years"]
    if args.years:
        if "-" in args.years and "," not in args.years:
            a, b = args.years.split("-")
            years = list(range(int(a), int(b) + 1))
        else:
            years = [int(x) for x in args.years.split(",")]
    else:
        years = all_years

    gdir = ROOT / CFG["paths"]["graph_dir"]

    # per-year graphs
    for y in years:
        if not (ROOT / CFG["paths"]["annotation_dir"] / "year" / f"year={y}.csv").exists():
            print(f"[graph] skip year={y} (no annotation)")
            continue
        terms, csr, freq = build_graph([y])
        save_graph(terms, csr, freq, gdir / f"year={y}")
        print(f"[graph] year={y}: nodes={len(terms)} edges={csr.nnz // 2}", flush=True)

    # cumulative graphs for the two analysis windows
    for label, ys in [("backtest", CFG["backtest"]["history_years"]),
                      ("test", CFG["backtest"]["test_years"]),
                      ("latest", CFG["predict"]["history_years"])]:
        if all((ROOT / CFG["paths"]["annotation_dir"] / "year" / f"year={y}.csv").exists()
               for y in ys):
            terms, csr, freq = build_graph(ys)
            tag = f"cum_{ys[0]}_{ys[-1]}"
            save_graph(terms, csr, freq, gdir / tag)
            print(f"[graph] {tag}: nodes={len(terms)} edges={csr.nnz // 2}", flush=True)


if __name__ == "__main__":
    main()
