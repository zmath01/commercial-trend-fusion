#!/usr/bin/env python3
"""signals.py — signal computation library (the math core).

All functions are pure (numpy/scipy); no I/O. Every metric here is
computed from data the repo itself produces, so every headline number
is reproducible by `python scripts/run_all.py`.

Signals:
  * log_slope      — log-linear growth rate over a year window
  * hockey_stick   — recent-vs-prior slope ratio ("takeoff" detector)
  * pagerank       — power iteration on sparse CSR (alpha=0.85)
  * conductance    — effective resistance / conductance between two nodes
                     via sparse Laplacian solve (conjugate gradient).
                     This is the full-network quantity: R_eff = (e_i-e_j)^T x
                     where L x = e_i - e_j (Klein & Randić 1993).
  * roc_auc        — exact ROC AUC via rank sums (no sklearn needed)
  * lift_at_k      — top-K lift vs frequency-matched random baseline
  * bootstrap_ci   — percentile bootstrap confidence intervals
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import cg
from scipy.stats import linregress, spearmanr


def log_slope(years: np.ndarray, counts: np.ndarray):
    """log1p-linear regression slope. Returns (slope, r2, p)."""
    x = years.astype(float)
    y = np.log1p(np.asarray(counts, dtype=float))
    res = linregress(x, y)
    return float(res.slope), float(res.rvalue ** 2), float(res.pvalue)


def hockey_stick(counts: np.ndarray, w: int = 2):
    """Takeoff detector: slope of last w years vs previous w years.

    Returns (ratio, recent_slope, prior_slope). ratio > 1 means the term
    is accelerating relative to its own past; ratio < 0 means recent
    decline after prior growth. Requires len(counts) >= 2*w.
    """
    n = len(counts)
    if n < 2 * w:
        return None
    x = np.arange(n)
    y = np.log1p(np.asarray(counts, dtype=float))
    recent = linregress(x[n - w:], y[n - w:]).slope
    prior = linregress(x[n - 2 * w:n - w], y[n - 2 * w:n - w]).slope
    if abs(prior) < 1e-9:
        ratio = 0.0 if recent <= 0 else 99.0
    else:
        ratio = recent / prior
    return float(ratio), float(recent), float(prior)


def pagerank(csr: sp.csr_matrix, alpha: float = 0.85,
             max_iter: int = 200, tol: float = 1e-8) -> np.ndarray:
    """PageRank via power iteration on the row-stochastic matrix."""
    n = csr.shape[0]
    deg = np.asarray(csr.sum(axis=1)).ravel()
    out = np.zeros(n)
    dangling = deg == 0
    out[dangling] = 1.0
    row_sum = np.where(deg > 0, deg, 1.0)
    P = sp.diags(1.0 / row_sum) @ csr
    r = np.full(n, 1.0 / n)
    for _ in range(max_iter):
        r_new = alpha * (P.T @ r + (r @ out) * (1.0 / n)) + (1 - alpha) / n
        if np.linalg.norm(r_new - r, ord=1) < tol:
            break
        r = r_new
    return r


def _reachable(csr: sp.csr_matrix, i: int, n: int) -> np.ndarray:
    """BFS from i over undirected graph; returns bool mask."""
    visited = np.zeros(n, dtype=bool)
    stack = [i]
    visited[i] = True
    indptr, indices = csr.indptr, csr.indices
    while stack:
        u = stack.pop()
        for v in indices[indptr[u]:indptr[u + 1]]:
            if not visited[v]:
                visited[v] = True
                stack.append(v)
    return visited


def conductance(csr: sp.csr_matrix, i: int, j: int,
                max_iter: int = 3000, tol: float = 1e-7) -> float:
    """Effective conductance G(i,j) = 1 / R_eff(i,j) on the full graph.

    R_eff is the resistance distance: solve L x = e_i - e_j with sparse CG
    (Jacobi preconditioner), then R_eff = x_i - x_j. Disconnected pairs
    get G = 0. Complexity ~ O(E * sqrt(kappa)) per pair.
    """
    n = csr.shape[0]
    if i == j:
        return float("inf")
    mask = _reachable(csr, i, n)
    if not mask[j]:
        return 0.0
    # restrict to the component containing i (keeps CG small & stable)
    idx = np.where(mask)[0]
    sub = csr[idx][:, idx].tocsr()
    comp = {v: k for k, v in enumerate(idx)}
    a, b = comp[i], comp[j]
    deg = np.asarray(sub.sum(axis=1)).ravel().astype(float)
    L = sp.diags(deg) - sub
    bvec = np.zeros(len(idx))
    bvec[a] = 1.0
    bvec[b] = -1.0
    M = sp.diags(1.0 / np.maximum(deg, 1e-9))  # Jacobi preconditioner
    x, info = cg(L, bvec, rtol=tol, maxiter=max_iter, M=M)
    if info > 0:
        return 0.0  # did not converge; treat as unresolved
    r_eff = x[a] - x[b]
    if r_eff <= 1e-9:
        return 0.0
    return 1.0 / r_eff


def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Exact ROC AUC via Mann-Whitney U."""
    y_true = np.asarray(y_true, dtype=bool)
    y_score = np.asarray(y_score, dtype=float)
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(y_score, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    # tie correction: average ranks within equal scores
    srt = y_score[order]
    i = 0
    while i < len(srt):
        j = i
        while j + 1 < len(srt) and srt[j + 1] == srt[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    sum_pos = ranks[y_true].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def lift_at_k(score: np.ndarray, outcome: np.ndarray, k: int,
              strata: np.ndarray | None = None,
              n_draws: int = 100, seed: int = 42) -> dict:
    """Lift of top-K by score vs random K matched on strata (freq bands).

    Returns {top_k_mean, baseline_mean, lift, gain, ci_lo, ci_hi}.
    gain = top_mean - baseline_mean (robust to negative means; use this
    when the outcome can be negative).
    """
    rng = np.random.default_rng(seed)
    n = len(score)
    k = min(k, n)
    top_idx = np.argsort(score)[-k:]
    top_mean = float(outcome[top_idx].mean())
    if strata is None:
        strata = np.zeros(n, dtype=int)
    draws = []
    for _ in range(n_draws):
        picked = []
        for s in np.unique(strata):
            pool = np.where(strata == s)[0]
            n_pick = int(np.sum(strata[top_idx] == s))
            if n_pick > 0 and len(pool) >= n_pick:
                picked.append(rng.choice(pool, size=n_pick, replace=False))
        if picked:
            idx = np.concatenate(picked)
            draws.append(float(outcome[idx].mean()))
    if not draws:
        return {"top_k_mean": top_mean, "baseline_mean": float(outcome.mean()),
                "lift": float("nan"), "gain": float("nan"),
                "ci_lo": float("nan"), "ci_hi": float("nan")}
    baseline = float(np.mean(draws))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"top_k_mean": top_mean, "baseline_mean": baseline,
            "lift": top_mean / baseline if baseline > 0 else float("nan"),
            "gain": top_mean - baseline,
            "ci_lo": float(lo), "ci_hi": float(hi)}


def bootstrap_ci(x: np.ndarray, y: np.ndarray, stat_fn,
                 iters: int = 1000, seed: int = 42) -> tuple[float, float]:
    """Percentile CI for a bivariate statistic (e.g. Spearman rho)."""
    rng = np.random.default_rng(seed)
    n = len(x)
    vals = []
    for _ in range(iters):
        idx = rng.integers(0, n, size=n)
        try:
            vals.append(stat_fn(x[idx], y[idx]))
        except Exception:  # noqa: BLE001
            continue
    vals = np.array(vals)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def permutation_p(x: np.ndarray, y: np.ndarray, stat_fn,
                  iters: int = 1000, seed: int = 42) -> float:
    """Two-sided permutation p-value for a bivariate statistic."""
    rng = np.random.default_rng(seed)
    obs = stat_fn(x, y)
    cnt = 0
    for _ in range(iters):
        yp = rng.permutation(y)
        try:
            s = stat_fn(x, yp)
        except Exception:  # noqa: BLE001
            continue
        if abs(s) >= abs(obs):
            cnt += 1
    return (cnt + 1) / (iters + 1)


def spearman(x, y):
    return spearmanr(x, y).statistic
