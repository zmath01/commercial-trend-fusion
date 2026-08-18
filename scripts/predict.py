#!/usr/bin/env python3
"""predict.py — produce the live "commercialization radar" watchlists.

Task A (concepts):   rank terms by takeoff signal (hockey-stick ratio and
recent log-slope over the full history window). Publishes the top N with
freq series, PageRank in the latest cumulative graph, and field tag.

Task B (fusion):     pairs with no direct co-occurrence through the latest
year but with a 2-hop path; rank by full-network conductance G(2025).
For the published top pairs we also compute the per-year G series so the
site can show whether the coupling is rising (the "fusion in progress"
view). Honest caveat: watchlists are hypotheses, not investments.

Outputs under data/results/:
  concepts_radar.json, fusion_watchlist.json, fields.json, meta.json
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import signals  # noqa: E402
from backtest import load_graph, pivot_counts, _worker_init, _g_solve  # noqa: E402
from build_graph import read_excluded_terms  # noqa: E402

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

YEARS = CFG["predict"]["history_years"]
N_CONC = CFG["predict"]["n_concepts"]
N_PAIRS = CFG["predict"]["n_pairs"]
SEED = CFG["random_seed"]


def task_a() -> dict:
    counts = pd.read_csv(ROOT / CFG["paths"]["annotation_dir"] / "phrase_year_counts.csv")
    mat, terms = pivot_counts(counts, YEARS)
    freq_last = mat[:, -1]
    excluded = read_excluded_terms()
    # generic first-token set (furniture phrases often start with these)
    generic_first = set()
    gf = ROOT / "data" / "generic_unigrams.txt"
    if gf.exists():
        generic_first = {line.strip().lower()
                         for line in gf.read_text(encoding="utf-8").splitlines()
                         if line.strip() and not line.strip().startswith("#")}
    present_years = (mat > 0).sum(axis=1)
    first_tokens = np.array([t.split()[0] for t in terms])
    # universe: terms with real recent volume (freq >= 10), excluding generic
    # unigrams / boilerplate ("paper furniture"); also drop furniture-style
    # phrases that start with a generic word and only appeared recently
    furniture = np.array([ft in generic_first for ft in first_tokens]) & (present_years < 3)
    univ = np.where(
        (freq_last >= 10)
        & ((freq_last < 250) | np.array([" " in t for t in terms]))
        & (~np.array([t in excluded for t in terms]))
        & (~furniture)
    )[0]

    # field attribution from phrase_field_counts (latest year)
    pfc = pd.read_csv(ROOT / CFG["paths"]["annotation_dir"] / "phrase_field_counts.csv")
    pfc_latest = pfc[pfc["year"] == YEARS[-1]]
    field_of = (pfc_latest.groupby("term")["freq"].sum()
                .sort_values(ascending=False).index.tolist())
    top_field = {}
    for term in field_of:
        sub = pfc_latest[pfc_latest["term"] == term]
        top_field[term] = sub.sort_values("freq", ascending=False).iloc[0]["field"]

    # PageRank on the latest cumulative graph
    tag = f"cum_{YEARS[0]}_{YEARS[-1]}"
    g_terms, g_ids, g_csr = load_graph(tag)
    pr = signals.pagerank(g_csr)

    rows = []
    for i in univ:
        term = terms[i]
        slope, r2, _ = signals.log_slope(np.array(YEARS[-3:], dtype=float),
                                         mat[i, -3:])
        hk = signals.hockey_stick(mat[i, -4:], w=2)
        # stability: present in at least 2 of the last 4 years
        if int((mat[i, -4:] > 0).sum()) < 2:
            continue
        gid = g_ids.get(term, -1)
        rows.append({
            "term": term,
            "field": top_field.get(term, "Other"),
            "freq_series": [int(x) for x in mat[i]],
            "slope_recent": round(float(slope), 4),
            "hockey": round(float(hk[0]), 3) if hk else None,
            "pagerank": round(float(pr[gid]), 6) if gid >= 0 else 0.0,
            "freq_latest": int(freq_last[i]),
        })
    # rank by recent growth rate; hockey-stick ratio is a displayed badge
    # (a term that just appeared has hockey=99 but no track record)
    rows.sort(key=lambda r: (-r["slope_recent"], -(r["hockey"] if r["hockey"] is not None else -99)))
    top = rows[:N_CONC]
    # per-field top lists
    by_field = {}
    for r in rows[: max(N_CONC * 3, 300)]:
        by_field.setdefault(r["field"], []).append(r["term"])
    return {"top": top, "by_field": {k: v[:10] for k, v in by_field.items()}}


def per_year_g_series(pairs, terms, tag):
    """G series 2019..latest for the published pairs (parallel)."""
    series = {}
    for y in range(YEARS[0], YEARS[-1] + 1):
        t = f"year={y}"
        p = ROOT / CFG["paths"]["graph_dir"] / t
        if not (p / "edges.npz").exists():
            continue
        z = np.load(p / "edges.npz")
        coo = sp.coo_matrix((z["data"], (z["rows"], z["cols"])),
                            shape=tuple(z["shape"]))
        csr = coo.tocsr()
        ids = {}
        with open(p / "nodes.csv", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ids[row["term"]] = int(row["id"])
        jobs = []
        pair_ids = []
        for (a, b) in pairs:
            ia, ib = ids.get(a, -1), ids.get(b, -1)
            pair_ids.append((ia, ib))
            jobs.append((ia, ib))
        with mp.Pool(8, initializer=_worker_init,
                     initargs=(t, p / "edges.npz", p / "nodes.csv")) as pool:
            vals = pool.map(_g_solve, jobs, chunksize=4)
        for (a, b), (ia, ib), v in zip(pairs, pair_ids, vals):
            if ia >= 0 and ib >= 0:
                series.setdefault((a, b), {})[y] = round(float(v), 4)
    return series


def task_b() -> dict:
    tag = f"cum_{YEARS[0]}_{YEARS[-1]}"
    g_terms, g_ids, g_csr = load_graph(tag)
    freq = np.array([0] * len(g_terms))
    with open(ROOT / CFG["paths"]["graph_dir"] / tag / "nodes.csv",
              newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            freq[int(row["id"])] = int(row["freq"])
    from backtest import gen_candidates
    cands = gen_candidates(g_terms, g_ids, g_csr, freq, freq_thresh=20)
    print(f"[predict] fusion candidates: {len(cands)}", flush=True)

    jobs = [(c["A"], c["V"]) for c in cands]
    with mp.Pool(8, initializer=_worker_init,
                 initargs=(tag,
                           ROOT / CFG["paths"]["graph_dir"] / tag / "edges.npz",
                           ROOT / CFG["paths"]["graph_dir"] / tag / "nodes.csv")) as pool:
        gvals = pool.map(_g_solve, jobs, chunksize=16)
    for c, g in zip(cands, gvals):
        c["G"] = float(g)

    cands.sort(key=lambda c: -c["G"])
    top = cands[:N_PAIRS]

    pfc = pd.read_csv(ROOT / CFG["paths"]["annotation_dir"] / "phrase_field_counts.csv")
    pfc_latest = pfc[pfc["year"] == YEARS[-1]]
    top_field = {}
    for term, g in pfc_latest.groupby("term"):
        top_field[term] = g.sort_values("freq", ascending=False).iloc[0]["field"]

    pairs = [(g_terms[c["A"]], g_terms[c["V"]]) for c in top]
    series = per_year_g_series(pairs, g_terms, tag)

    rows = []
    for c in top:
        a, v = g_terms[c["A"]], g_terms[c["V"]]
        rows.append({
            "A": a, "B": v, "via": g_terms[c["W"]],
            "fieldA": top_field.get(a, "Other"),
            "fieldB": top_field.get(v, "Other"),
            "I": round(c["I"], 2),
            "G_latest": round(c["G"], 4),
            "G_series": series.get((a, v), {}),
        })
    return {"top": rows}


def fields_summary() -> dict:
    df = pd.read_csv(ROOT / CFG["paths"]["annotation_dir"] / "phrase_field_counts.csv")
    pfc = df[df["year"].isin(YEARS)]
    per_field_year = pfc.groupby(["field", "year"])["freq"].sum().unstack(fill_value=0)
    out = {}
    for field, row in per_field_year.iterrows():
        counts = row.reindex(YEARS, fill_value=0).astype(int).tolist()
        slope, _, _ = signals.log_slope(np.array(YEARS[-3:], dtype=float),
                                        np.array(counts[-3:], dtype=float))
        out[field] = {"counts": counts, "slope_recent": round(float(slope), 4)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["a", "b", "fields", "all"], default="all")
    args = ap.parse_args()

    rdir = ROOT / CFG["paths"]["results_dir"]
    rdir.mkdir(parents=True, exist_ok=True)
    if args.task in ("a", "all"):
        res = task_a()
        (rdir / "concepts_radar.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1))
        print("[predict] task A (concepts) saved", flush=True)
    if args.task in ("b", "all"):
        res = task_b()
        (rdir / "fusion_watchlist.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1))
        print("[predict] task B (fusion) saved", flush=True)
    if args.task in ("fields", "all"):
        res = fields_summary()
        (rdir / "fields.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1))
        print("[predict] fields saved", flush=True)


if __name__ == "__main__":
    main()
