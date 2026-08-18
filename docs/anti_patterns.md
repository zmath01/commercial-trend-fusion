# Anti-patterns this project rejects

A short field guide to the failure modes common in "research direction
prediction" / "science trend" projects — and how this repository avoids each
one. The list exists because these failure modes are widespread, and most
published dashboards in this genre exhibit at least two of them.

## 1. Unreproducible headline metrics

A headline number (e.g. "AUC 0.87", "2× baseline") appears in the README but
no script in the repository can produce it. The number lives only in prose.

**This project:** every metric on the site is written by
`scripts/backtest.py` / `scripts/predict.py` into `data/results/*.json`, which
`scripts/build_site.py` renders. If you want to verify a number, you run a
script. If the number is wrong, that is a bug — not a debate.

## 2. Misnamed methods

Fancy vocabulary without the corresponding mechanism:

- "random walk sampling" that is deterministic enumeration (no stochastic
  process anywhere in the code);
- "semantic search" implemented as exact lexical overlap;
- "neural/embedding" claims backed by plain counting.

**This project:** names mean what they say. `scripts/sci_*`-style naming is
not used; the only physics-flavored term is *effective conductance*, and it is
implemented as an actual sparse Laplacian solve (`signals.py::conductance`),
with the formula in `docs/methodology.md`.

## 3. Unmatched controls

The treatment arm is "pairs with a two-hop path, ranked by signal"; the
control arm is "random pairs with no structural condition". Nearby pairs link
more often than far pairs *by construction*, so the control under-hits and the
headline gain is an artifact of the comparison, not of the signal.

**This project:** the primary control is *structural* — same A, same bridge w,
random alternative B′ with the same two-hop condition
(`scripts/backtest.py`). The naive frequency-matched control is reported
separately and labeled as such.

## 4. Inconsistent baselines

Different experiments cite different baselines (0 %, 3 %, 4.3 %…) for the
same underlying quantity, and hit definitions change between claims (any
co-occurrence vs. N≥5 with growth). Each change moves the headline number.

**This project:** one hit definition per task, stated once, used everywhere;
one baseline definition per task, reported every time.

## 5. Fancy names for standard heuristics

Rebranding common-neighbor counting as "conductance", "quantum-inspired", or
"physics of science" without any of the actual mathematics.

**This project:** standard pieces are called by their standard names (BM25,
PageRank, RBO, OLS slope). The one non-trivial object (G) is defined by a
published formula and computed exactly on the full graph.

## 6. Private funnels

The "open" project funnels readers into a private WeChat/paid channel where
the real "interpretation" lives, and the public artifact is just a lead magnet.

**This project:** no private channel. Questions → GitHub issues. Corrections →
pull requests. The public artifact *is* the product.

## 7. Version inflation

Version numbers racing (v17 → v20 in three days) with changelogs full of
"user confirmed" entries that are actually AI-agent session logs.

**This project:** semantic versions only when there is a release; CI builds
the site from committed results; `data/results/meta.json` records the exact
config + git SHA that produced every page.
