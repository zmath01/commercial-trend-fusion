# Commercial Trend Radar — Fusion

> A reproducible arXiv-based research radar for **concept growth and possible cross-field fusion**.
> It is a research-monitoring experiment, **not a validated commercialization predictor**.

**Live site:** https://zmath01.github.io/commercial-trend-fusion
**Repo:** https://github.com/zmath01/commercial-trend-fusion

## Current status — 2026-09-18

The currently published/generated site is a **sampled arXiv snapshot**, not a live continuously refreshed commercialization dataset.

The committed corpus metadata says:
- **27,259 papers**
- **2019–2025**
- per-category annual cap: **150 papers**
- 23 arXiv categories in the committed run
- prediction/backtest snapshot built at **2026-09-04 08:55 UTC**
- random seed: 42

The canonical taxonomy is broader than the committed corpus. FinTech is treated separately because arXiv has no dedicated FinTech category.

## What it actually does

The pipeline fetches a capped arXiv corpus, mines phrases, annotates papers, builds sparse phrase co-occurrence graphs, computes growth / hockey-stick signals, PageRank and effective conductance, evaluates two out-of-sample tasks, and generates a static GitHub Pages site.

### Task A — concept growth

Question: does a term's historical growth signal predict its future growth?

The committed backtest uses 2019–2022 as history and 2023–2025 as test data.

### Task B — pair fusion

Question: can graph structure identify pairs that subsequently begin to co-occur?

The project uses effective conductance G as one ranking signal and compares it with a cheap two-hop strength baseline I, a naive control, and a structural control that preserves the same starting node and bridge.

This is a **link-prediction problem over arXiv language**, not a direct measurement of commercial adoption.

## Latest displayed dashboard snapshot

The current generated homepage ranks concept-growth signals such as:

- **agentic ai** — latest frequency 25; recent slope 1.629; hockey 99
- **regime shifts** — 16; slope 1.070; hockey 3.087
- **llm agents** — 31; slope 1.040; hockey 0.456
- **hybrid framework** — 15; slope 1.040; hockey -4.129
- **stress testing** — 13; slope 0.973; hockey 99
- **dynamic environments** — 13; slope 0.973; hockey -0.107
- **learning dynamics** — 13; slope 0.973; hockey -0.509
- **efficiency gains** — 12; slope 0.936; hockey 99
- **flow matching** — 12; slope 0.936; hockey 1.70
- **market regimes** — 12; slope 0.936; hockey -2.357

These are **ranking outputs**, not validated commercialization forecasts. Several phrases are generic academic language, so the radar should not be read as a list of commercially promising technologies.

## Latest committed backtest result

The committed `data/results/backtest.json` reports:

### Task A

- slope signal: Spearman ρ = **0.0322**, permutation p = **0.0859**, AUC = **0.5216**
- hockey signal: Spearman ρ = **-0.0026**, permutation p = **0.8931**, AUC = **0.5000**

The confidence intervals for the reported correlations include zero. The committed result therefore does **not demonstrate a strong predictive relationship** between the tested historical signals and future concept growth.

### Task B

- candidate-pool base rate: **0.733%**
- top-100 by effective conductance G: **1.0%**
- top-100 by two-hop strength I: **6.0%**
- naive control: **0.333%**
- structural control: **0.667%**
- AUC(G): **0.5648**
- AUC(I): **0.5444**
- permutation p for AUC(G): **0.1277**
- permutation p for top-100 G vs structural control: **0.4826**

The 6% I result is descriptive and is not evidence that I is a validated commercial signal. The structural-control comparison is the more relevant test of whether G adds information beyond the graph structure used to construct candidate pairs.

## Important snapshot mismatch

The generated homepage and `backtest.json` are **not the same statistical object**:
- the homepage radar is generated from the committed concept/fusion result files;
- `backtest.json` is the committed 2019–2022 → 2023–2025 evaluation snapshot;
- the site can therefore display a current-looking radar while the formal backtest remains a fixed historical snapshot.

Do not describe homepage rankings as the outcome of the formal backtest unless the result files are rebuilt together.

## GitHub Actions / Pages status

The Pages workflow currently performs a **full live arXiv fetch + full pipeline + static-site build** on push, monthly schedule, or manual dispatch.

The workflow also has `concurrency: cancel-in-progress: true`, so overlapping runs can be **cancelled** when a newer run supersedes an older run. A cancelled run is an operational workflow event, not a failed scientific result and not new data.

The raw live corpus is intentionally not committed. A successful Pages deployment therefore represents the generated artifact from that run; it does not by itself create a permanently versioned full raw-corpus snapshot.

## Limitations

- arXiv is a research-publication corpus, not a commercialization database.
- The per-category cap (150/year) means the committed corpus is a sample, not the full arXiv population.
- Phrase mining can produce generic phrases such as “different groups”, “significant progress”, or “framework provides”.
- Frequency growth is not commercialization.
- First co-occurrence is not market adoption.
- Effective conductance is a graph heuristic; it has no demonstrated causal connection to commercialization.
- Task B has a low event rate and only 3 test years.
- Multiple signals and candidate pairs are evaluated; displayed p-values are not family-wise corrected.
- The project currently lacks independent patent, funding, hiring, company-formation, revenue, or market-outcome labels.
- Current evidence supports **monitoring / hypothesis generation**, not commercial prediction.

## Roadmap

1. Keep the sampled arXiv radar reproducible and versioned.
2. Remove generic/non-technical phrase artifacts from the lexicon with a pre-registered rule set.
3. Rebuild the formal backtest and homepage from one immutable result snapshot.
4. Add an independent commercialization outcome layer.
5. Test whether concept/fusion signals predict that independent outcome out-of-sample.
6. Only then treat the radar as evidence about commercialization rather than research-language dynamics.

## Quickstart

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python scripts/run_all.py --sample
    python scripts/build_site.py

## License

Code: MIT. Derived data and site content: CC BY 4.0. See `CITATION.cff`.