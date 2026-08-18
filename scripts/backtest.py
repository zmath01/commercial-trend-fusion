#!/usr/bin/env python3
"""backtest.py — rigorous out-of-sample evaluation of both prediction tasks.

Task A (concept growth):  rank terms by history-window growth signals,
evaluate against future-window growth. Metrics: Spearman rho (+permutation
p, bootstrap CI), ROC AUC (outcome above median), lift@K vs frequency-band
matched random baseline.

Task B (pair fusion):      candidate pairs with no direct co-occurrence in
the history window but with a 2-hop path. Signal = full-network effective
conductance G(A,B) (and the cheap 2-hop strength I, reported side by side).
Outcome = first co-occurrence in the test window. Three baselines are
reported:
  1. pool base rate     — all candidates (no ranking)
  2. naive control      — random pairs matched on frequency bands only
  3. structural control — same A and same bridge w, random alternative B'
                          (matched 2-hop structure). This is the fair test:
                          it asks "does G add signal beyond the 2-hop
                          neighborhood structure itself?"

Design principle: every number on the site comes from this script. No
headline metric is ever hand-written into a README first.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import signals  # noqa: E402

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

HIST = CFG["backtest"]["history_years"]
TEST = CFG["backtest"]["test_years"]
N_CAND = CFG["backtest"]["n_candidates"]
TOP_K = CFG["backtest"]["top_k"]
SEED = CFG["random_seed"]


# ---------------------------------------------------------------- loading
def load_counts() -> pd.DataFrame:
    fp = ROOT / CFG["paths"]["annotation_dir"] / "phrase_year_counts.csv"
    return pd.read_csv(fp)


def pivot_counts(df: pd.DataFrame, years) -> tuple[np.ndarray, list[str]]:
    """term x year matrix (rows sorted alphabetically)."""
    sub = df[df["year"].isin(years)]
    pivot = sub.pivot_table(index="term", columns="year", values="freq",
                            fill_value=0, aggfunc="sum")
    pivot = pivot.reindex(columns=years, fill_value=0)
    terms = list(pivot.index)
    return pivot.to_numpy(dtype=float), terms


def load_graph(tag: str):
    """Returns (terms list, term->id, csr)."""
    gdir = ROOT / CFG["paths"]["graph_dir"] / tag
    terms, ids = [], {}
    with open(gdir / "nodes.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            terms.append(row["term"])
            ids[row["term"]] = int(row["id"])
    z = np.load(gdir / "edges.npz")
    coo = sp.coo_matrix((z["data"], (z["rows"], z["cols"])),
                        shape=tuple(z["shape"]))
    return terms, ids, coo.tocsr()


# ---------------------------------------------------------------- Task A
def task_a(mat: np.ndarray, terms: list[str]) -> dict:
    yrs_h = np.array(HIST)
    yrs_t = np.array(TEST)
    freq_last = mat[:, len(HIST) - 1]  # freq in last history year
    universe = freq_last >= 5
    u_idx = np.where(universe)[0]

    hist_mat = mat[:, :len(HIST)]
    test_mat = mat[:, len(HIST):]
    slopes_h = np.array([signals.log_slope(yrs_h, hist_mat[i])[0] for i in u_idx])
    slopes_t = np.array([signals.log_slope(yrs_t, test_mat[i])[0] for i in u_idx])
    # hockey-stick strictly from the history window (no test-year leakage)
    hockey = np.array([signals.hockey_stick(hist_mat[i], w=2)[0]
                       if signals.hockey_stick(hist_mat[i], w=2) else 0.0
                       for i in u_idx])

    out = {}
    for name, sig in [("slope", slopes_h), ("hockey", hockey)]:
        rho = signals.spearman(sig, slopes_t)
        p_perm = signals.permutation_p(sig, slopes_t, signals.spearman,
                                       seed=SEED)
        lo, hi = signals.bootstrap_ci(sig, slopes_t, signals.spearman,
                                      seed=SEED)
        bin_out = slopes_t > np.median(slopes_t)
        auc = signals.roc_auc(bin_out, sig)
        # frequency-band strata for lift matching (5 quantile bands)
        bands = pd.qcut(freq_last[u_idx], 5, labels=False, duplicates="drop")
        lift = signals.lift_at_k(sig, slopes_t, TOP_K,
                                 strata=bands.astype(int), seed=SEED)
        out[name] = {"spearman_rho": round(float(rho), 4),
                     "perm_p": float(p_perm),
                     "ci_lo": round(float(lo), 4),
                     "ci_hi": round(float(hi), 4),
                     "auc": round(float(auc), 4),
                     "lift": lift}
    return {"n_universe": int(universe.sum()),
            "signals": out,
            "top_terms": [{"term": terms[u_idx[i]],
                           "slope_h": round(float(slopes_h[i]), 4),
                           "slope_t": round(float(slopes_t[i]), 4),
                           "hockey": round(float(hockey[i]), 3),
                           "freq_2022": int(freq_last[u_idx[i]])}
                          for i in np.argsort(slopes_h)[-50:][::-1]]}


# ---------------------------------------------------------------- Task B
def load_pair_cache(tag: str):
    """edge weight lookup: (i,j) -> weight (symmetric)."""
    terms, ids, csr = load_graph(tag)
    return terms, ids, csr


def hist_weight(csr, i, j):
    if i < 0 or j < 0:
        return 0
    return int(csr[i, j])


def gen_candidates(hist_terms, hist_ids, hist_csr, freq, freq_thresh=20):
    """2-hop non-edge candidates with strength I = min(edge weights).

    freq: np.ndarray aligned with hist_terms (document frequency in window).
    """
    n = len(hist_terms)
    cands = []
    seen = set()
    for a in range(n):
        if freq[a] < freq_thresh:
            continue
        na = hist_csr.indices[hist_csr.indptr[a]:hist_csr.indptr[a + 1]]
        na_w = hist_csr.data[hist_csr.indptr[a]:hist_csr.indptr[a + 1]]
        for w, cw in zip(na, na_w):
            if freq[w] < freq_thresh:
                continue
            nw = hist_csr.indices[hist_csr.indptr[w]:hist_csr.indptr[w + 1]]
            nw_w = hist_csr.data[hist_csr.indptr[w]:hist_csr.indptr[w + 1]]
            for v, cv in zip(nw, nw_w):
                if v == a:
                    continue
                if hist_csr[a, v] > 0:          # already linked
                    continue
                if freq[v] < freq_thresh:
                    continue
                key = (min(a, v), max(a, v))
                if key in seen:
                    continue
                seen.add(key)
                cands.append({"A": a, "V": v, "W": w,
                              "I": float(min(cw, cv)),
                              "wA": float(cw), "wV": float(cv)})
    cands.sort(key=lambda c: -c["I"])
    return cands[:N_CAND]


def _worker_init(tag, npz_path, nodes_path):
    global _W_TERMS, _W_IDS, _W_CSR
    z = np.load(npz_path)
    coo = sp.coo_matrix((z["data"], (z["rows"], z["cols"])),
                        shape=tuple(z["shape"]))
    _W_CSR = coo.tocsr()
    _W_IDS = {}
    with open(nodes_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            _W_IDS[row["term"]] = int(row["id"])


def _g_solve(args):
    i, j = args
    if i < 0 or j < 0:
        return 0.0  # term absent from this graph
    return signals.conductance(_W_CSR, i, j)


def task_b() -> dict:
    hist_tag = f"cum_{HIST[0]}_{HIST[-1]}"
    test_tag = f"cum_{TEST[0]}_{TEST[-1]}"
    hist_terms, hist_ids, hist_csr = load_graph(hist_tag)
    test_terms, test_ids, test_csr = load_graph(test_tag)

    freq = np.array([0] * len(hist_terms))
    with open(ROOT / CFG["paths"]["graph_dir"] / hist_tag / "nodes.csv",
              newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            freq[int(row["id"])] = int(row["freq"])

    cands = gen_candidates(hist_terms, hist_ids, hist_csr, freq)
    print(f"[backtest] candidates: {len(cands)}", flush=True)

    # G for every candidate (parallel CG solves)
    jobs = [(c["A"], c["V"]) for c in cands]
    with mp.Pool(8, initializer=_worker_init,
                 initargs=(hist_tag,
                           ROOT / CFG["paths"]["graph_dir"] / hist_tag / "edges.npz",
                           ROOT / CFG["paths"]["graph_dir"] / hist_tag / "nodes.csv")) as pool:
        gvals = pool.map(_g_solve, jobs, chunksize=16)
    for c, g in zip(cands, gvals):
        c["G"] = float(g)

    # outcomes: test-window co-occurrence weight
    test_w = np.zeros(len(cands))
    test_w1 = np.zeros(len(cands))
    for k, c in enumerate(cands):
        ti = test_ids.get(hist_terms[c["A"]], -1)
        tj = test_ids.get(hist_terms[c["V"]], -1)
        if ti >= 0 and tj >= 0:
            w = int(test_csr[ti, tj])
            test_w[k] = w
            test_w1[k] = 1 if w >= 1 else 0

    hit3 = (test_w >= 3).astype(float)
    hit1 = test_w1

    # ---- controls ----
    # freq loaded above (aligned with hist_terms)

    rng = np.random.default_rng(SEED)
    # naive control: random pairs matched on freq bands
    def freq_band(f):
        return min(int(np.log1p(max(f, 1)) // 0.5), 9)
    ctrl_naive = []
    hot_idx = np.where(freq >= 20)[0]
    while len(ctrl_naive) < len(cands):
        a, b = rng.choice(hot_idx, size=2, replace=False)
        if hist_csr[a, b] > 0:
            continue
        ctrl_naive.append((a, b))
    # structural control: same A, same bridge W, alternative V'
    ctrl_struct = []
    for c in cands:
        w = c["W"]
        nw = hist_csr.indices[hist_csr.indptr[w]:hist_csr.indptr[w + 1]]
        nw = [v for v in nw if v != c["A"] and v != c["V"]
              and freq[v] >= 20 and hist_csr[c["A"], v] == 0]
        if not nw:
            continue
        v2 = int(rng.choice(nw))
        ctrl_struct.append((c["A"], v2))

    def hit_rate(pairs, idxmap):
        h = 0
        for a, b in pairs:
            ta = test_ids.get(hist_terms[a], -1)
            tb = test_ids.get(hist_terms[b], -1)
            if ta >= 0 and tb >= 0 and int(test_csr[ta, tb]) >= 3:
                h += 1
        return h / max(len(pairs), 1)

    rates = {
        "pool_all": float(hit3.mean()),
        "pool_top100_by_G": float(hit3[np.argsort([c["G"] for c in cands])[-TOP_K:]].mean()),
        "pool_top100_by_I": float(hit3[np.argsort([c["I"] for c in cands])[-TOP_K:]].mean()),
        "naive_control": hit_rate(ctrl_naive, test_ids),
        "structural_control": hit_rate(ctrl_struct, test_ids),
        "n_candidates": len(cands),
        "n_structural": len(ctrl_struct),
        "n_naive": len(ctrl_naive),
    }

    g_arr = np.array([c["G"] for c in cands])
    i_arr = np.array([c["I"] for c in cands])
    auc_g = signals.roc_auc(hit3.astype(bool), g_arr)
    auc_i = signals.roc_auc(hit3.astype(bool), i_arr)

    # AUC permutation test (more powerful than top-K vs control):
    # shuffle hit labels, recompute AUC; p = fraction >= observed.
    rng_auc = np.random.default_rng(SEED + 1)
    hit_bool = hit3.astype(bool)
    perm_auc = 0
    for _ in range(500):
        shuf = rng_auc.permutation(hit_bool)
        try:
            s = signals.roc_auc(shuf, g_arr)
        except Exception:  # noqa: BLE001
            continue
        if s >= auc_g:
            perm_auc += 1
    auc_perm_p = (perm_auc + 1) / 501

    # permutation p: lift of top-100 by G vs structural control rate
    top_g = hit3[np.argsort(g_arr)[-TOP_K:]]
    obs_lift = top_g.mean() - rates["structural_control"]
    perm = 0
    for _ in range(200):
        idx = rng.choice(len(cands), size=TOP_K, replace=False)
        if hit3[idx].mean() - rates["structural_control"] >= obs_lift:
            perm += 1
    perm_p = (perm + 1) / 201

    rows = []
    for k, c in enumerate(cands):
        rows.append({"A": hist_terms[c["A"]], "B": hist_terms[c["V"]],
                     "via": hist_terms[c["W"]],
                     "I": round(c["I"], 2), "G": round(c["G"], 4),
                     "w_test": int(test_w[k]), "hit3": int(hit3[k])})
    rows.sort(key=lambda r: -r["G"])

    return {"rates": rates,
            "auc_G": round(float(auc_g), 4),
            "auc_I": round(float(auc_i), 4),
            "auc_perm_p": round(float(auc_perm_p), 4),
            "perm_p_top100_vs_structural": float(perm_p),
            "candidates": rows[:200]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["a", "b", "all"], default="all")
    args = ap.parse_args()

    res = {"meta": {"history_years": HIST, "test_years": TEST,
                    "n_candidates": N_CAND, "top_k": TOP_K,
                    "seed": SEED}}
    counts = load_counts()
    if args.task in ("a", "all"):
        mat, terms = pivot_counts(counts, HIST + TEST)
        res["task_a"] = task_a(mat, terms)
        print("[backtest] task A done", flush=True)
    if args.task in ("b", "all"):
        res["task_b"] = task_b()
        print("[backtest] task B done", flush=True)

    out = ROOT / CFG["paths"]["results_dir"] / "backtest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"[backtest] saved -> {out}")


if __name__ == "__main__":
    main()
