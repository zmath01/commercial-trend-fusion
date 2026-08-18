# Methodology

Formal description of the Commercial Trend Radar pipeline. Every formula below
has a direct implementation in `scripts/`. Nothing on the site is a number
without a script behind it.

## 1. Design principles

1. **Reproducibility first.** The corpus is fetched by `scripts/fetch_arxiv.py`;
   every derived number comes from a script; the site (`docs/`) is generated
   from those numbers by `scripts/build_site.py`.
2. **Honest baselines.** Predictions are compared against controls that share
   the same structural conditions (frequency bands, two-hop neighborhood) —
   never against arbitrary "random" sets that flatter the result by construction.
3. **Report failure too.** Modest ρ, low AUC, base rates — all published.
4. **No private funnels.** Code, data pipeline and results are public. The
   product is the analysis, not access to it.

## 2. Corpus

Source: arXiv Atom API (open, key-less). 23 categories grouped into 10
commercial fields:

| Field | arXiv categories |
|---|---|
| AI / ML | cs.AI, cs.LG, cs.CL, cs.CV, stat.ML, cs.NE |
| Software | cs.SE, cs.PL |
| Security & crypto | cs.CR |
| Systems | cs.DC |
| Theory | cs.DS, cs.GT |
| Chips | cs.AR |
| Quantum / chips | cs.ET |
| Applied math | math.OC, math.NA |
| Quantum | quant-ph |
| Quant finance | q-fin.ST, q-fin.TR, q-fin.CP, q-fin.MF, q-fin.RM |
| Fintech | econ.GN |

Fields per paper: `arxiv_id, title, abstract, primary_cat, published, year`.
Papers de-duplicated by `arxiv_id`.

**Sampling (read before interpreting anything).** The default fetch keeps the
most recent N papers per (category, year) (`corpus.per_year_cap`, default 250).
Frequencies are comparable **within a category across years**, not across
categories with different sampling rates. The full fetch (`--no-cap`) or the
official metadata dump (see `docs/data_sources.md`) removes this limitation.

## 3. Phrase mining

Concepts are multi-word academic phrases extracted with the association
measure of Mikolov et al. (2013) *word2phrase*. For adjacent tokens a, b with
counts c(a), c(b), c(ab) and total adjacent-pair count N:

    score(a,b) = (c(ab) − δ) / (c(a) · c(b)) · N,    δ = f_min

Merging iterates until no pair passes the threshold or phrases reach
n_max = 4 tokens. Final phrases must appear ≥ f_min times. Strong unigrams
(freq ≥ 10·f_min) are added so single-token commercial terms (llm, gpu,
qubit, bitcoin) enter the network. Stopwords at phrase edges, pure digits and
length-1 tokens are excluded.

- Implementation: `scripts/build_lexicon.py`
- Complexity: O(T) per merge pass over total tokens T; the number of passes
  is bounded by n_max.

## 4. Concept network

For each year and for cumulative windows: nodes = phrases with document
frequency ≥ f_hot; edge (u,v) = number of papers containing both phrases,
kept if weight ≥ e_min.

**Data structure.** Sparse CSR matrix (scipy) — O(V + E) memory — instead of
nested dicts. Node↔term maps are CSVs. This is the concrete choice that lets
the whole pipeline run on a 16 GB laptop.

- Implementation: `scripts/build_graph.py`

## 5. Signals

### 5.1 Growth slope

OLS slope of log(1 + f_t) regressed on year: log-linear growth rate with R²
and p. (`scripts/signals.py::log_slope`)

### 5.2 Hockey-stick (takeoff detector)

    h = slope(last w years) / slope(previous w years)

h > 1: accelerating; h < 0: declining after prior growth. The
commercial-takeoff pattern (LLMs, superconductors, Bitcoin, …).
(`signals.py::hockey_stick`)

### 5.3 PageRank

Power iteration on the row-stochastic adjacency matrix, α = 0.85.
(`signals.py::pagerank`)

### 5.4 Effective conductance G(A,B)

Resistance distance (Klein & Randić 1993):

    R_eff(i,j) = L⁺[i,i] + L⁺[j,j] − 2·L⁺[i,j],    L = D − A
    G(i,j)     = 1 / R_eff(i,j)

Instead of forming the dense pseudoinverse L⁺ (O(V³)), we solve the sparse
system L·x = e_i − e_j with conjugate gradients (Jacobi preconditioner) and
read R_eff = x_i − x_j. Complexity ≈ O(E·√κ) per pair. Disconnected pairs
get G = 0. For never-co-occurring pairs, G remains well-defined through all
indirect paths — the principled "how close are these concepts in the whole
network" quantity. (`signals.py::conductance`)

## 6. Prediction tasks

- **Task A (concept growth):** will a term's frequency grow in the next
  window? Signals: history-window slope, hockey-stick ratio.
- **Task B (pair fusion):** will two never-co-occurring concepts first
  co-occur? Candidates: 2-hop non-edges (A–w–B, strength
  I = min(w_Aw, w_wB)), ranked by full-network G.

## 7. Evaluation

### 7.1 Task A

Outcome = future-window log-slope. Metrics:

- Spearman ρ with permutation p (1000 shuffles) and bootstrap 95% CI (1000
  resamples) (`signals.py::permutation_p`, `bootstrap_ci`)
- ROC AUC of above-median future growth (`signals.py::roc_auc`)
- lift@K: mean outcome of top-K vs random baseline matched on 5 frequency
  bands (`signals.py::lift_at_k`)

### 7.2 Task B

Hit = first co-occurrence in the test window with ≥ 3 joint papers. Reported:

| Set | Meaning |
|---|---|
| pool base rate | all candidates, no ranking |
| top-100 by G | ranked by effective conductance |
| top-100 by I | ranked by cheap 2-hop strength |
| naive control | random pairs, frequency-band matched only |
| structural control | same A, same bridge w, random alternative B′ (matched 2-hop structure) |

Plus AUC of G and of I on the candidate pool, and a permutation p for the
top-100-by-G lift vs the structural control.

The structural control is the fair test: it isolates whether G adds signal
beyond the neighborhood structure itself. A control without the 2-hop
condition is guaranteed to under-hit (nearby pairs link more often than far
pairs by construction) and flatters every result — we do not use one as the
headline comparison.

## 8. Known limitations

- Capped sampling limits cross-category comparisons (see §2).
- arXiv ≠ market: funding, patents, hiring, price data are documented
  extensions, not yet integrated.
- Multiple testing: p-values are per-test.
- Lexicon-based phrases lag brand-new phrasings by design.
