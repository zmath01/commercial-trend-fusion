# Backtest report

> Generated from `data/results/backtest.json` — run
> `python scripts/backtest.py` to regenerate. No headline metric exists
> outside this file. These are the exact numbers the committed snapshot
> produced on the sampled corpus (31,805 fetched papers, de-duplicated).

## Setup

- Corpus: arXiv, 23 categories / 10 fields, sampled per-category-year
  (≤150–200 papers per category-year, most recent first). See
  `docs/data_sources.md`.
- History window: **2019–2022**. Test window: **2023–2025**.
- Hit definition (Task B): first co-occurrence in the test window with
  **≥ 3 joint papers**. One definition, used everywhere.
- Random seeds fixed (`config.yaml → random_seed`).
- Graph nodes exclude generic unigrams and "paper furniture" phrases
  (`data/generic_unigrams.txt`, `data/boilerplate_phrases.txt`) so that
  conductance values are not inflated by universal bridges.

## Task A — concept growth prediction

Signal from the history window → outcome = future growth slope (log1p).

| signal | ρ | permutation p | 95% CI | ROC AUC | top-K mean | baseline | gain |
|---|---|---|---|---|---|---|---|
| slope | 0.032 | 0.102 | [−0.005, 0.066] | 0.522 | −0.0018 | −0.0568 | +0.055 |
| hockey | −0.003 | 0.894 | [−0.038, 0.036] | 0.500 | −0.0291 | −0.0556 | +0.027 |

**Honest interpretation:** on this corpus, past growth does **not** strongly
predict future growth (ρ ≈ 0, p > 0.05 for both signals). Research-term
frequency is strongly mean-reverting. The radar is therefore a *nowcast and
monitoring* tool (what is accelerating right now), not a crystal ball. This
negative result is reported because it is the true result — and because most
projects in this space would quietly omit it.

## Task B — pair fusion prediction

Hit = first co-occurrence in test window with ≥ 3 joint papers.

| set | hit rate |
|---|---|
| pool base rate (all 3,000 candidates) | 0.73% |
| top-100 by G (effective conductance) | 1.00% |
| top-100 by I (2-hop strength) | 6.00% |
| naive control (random, freq-matched) | 0.17% |
| structural control (same A, same bridge, random B′) | 0.77% |

Ranking quality on the candidate pool:
- AUC(G) = **0.565**, AUC(I) = 0.543
- permutation p (AUC of G vs chance) = not computed in this snapshot (added
  in `scripts/backtest.py` after this run; will appear on next run)
- permutation p (top-100 by G vs structural control) = 0.537

**Honest interpretation:** with a strict hit definition (≥ 3 joint papers),
fusion is a rare event (base rate < 1%). G ranks slightly above chance
(AUC 0.565) and the cheap 2-hop strength I captures the extreme tail better
(6% vs 1% at top-100), but **neither effect is statistically significant
against the matched structural control in this snapshot**. The two earlier
(smaller-corpus) snapshots showed larger effects; the cleaner full-corpus
numbers are weaker. We report this. Practical takeaways:

1. The watchlist is useful as a **structured, explainable shortlist** of
   never-co-occurring pairs with strong indirect coupling — a monitoring
   surface, not a guaranteed-hit generator.
2. Base rates are tiny; even a 2-3× lift needs large candidate pools and
   human/LLM filtering downstream to be operationally useful.
3. The structural control is the right benchmark; naive random controls
   flatter results by construction and are only shown for transparency.

## Limitations

- Sampled corpus; within-category cross-year comparisons only.
- arXiv preprints ≠ commercialization; funding/patent/adoption data are
  documented extensions (`docs/data_sources.md`).
- Per-test p-values; no family-wise correction.
- Strict hit definition keeps precision high but power low; larger corpora
  (full fetch, `--no-cap`) will tighten the confidence intervals.
