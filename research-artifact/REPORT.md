# Research Artifact — Does concept coupling predict economically relevant scientific emergence?

## Research question

> Does historical coupling between research concepts predict later scientific attention, implementation/adoption, or patent activity beyond publication volume, popularity, standard link-prediction heuristics, and simple growth signals?

## Main causal/data-flow hypothesis

```text
arXiv metadata
    ↓
concept lexicon / topic representation
    ↓
concept co-occurrence graph
    ↓
G(A,B,t) + standard graph baselines
    ↓
future independent outcomes
    ├── citations
    ├── patents
    └── software/package/model adoption
```

This deliberately separates **lexical emergence** from **economic/scientific downstream emergence**.

## Artifact stages

```text
01_data/                  provenance + schemas + snapshots
02_reproduction/          independent reproduction of reference claims
03_ablation/              representation / preprocessing sensitivity
04_temporal_cv/           rolling-origin forecasting
05_null_models/           falsification and matched controls
06_baselines/             standard strong competitors
07_orthogonal_validation/ independent downstream outcomes
08_industry_outcomes/    citations + patents + implementation/adoption
REPORT.md                 final evidence and interpretation
```

## Relationship to the sibling `commercial-trend` project

`commercial-trend` is retained as the **multi-source commercialization prototype**: it combines OpenAlex research volume, GitHub repository creation and Stack Exchange questions, and evaluates a Commercial Signal Index with walk-forward logistic regression. Its own documentation correctly identifies the sample-size and domain-bias limitations. The present repository is the experimental harness: it tests concept-level coupling first and then asks whether that coupling predicts independent downstream outcomes.

Do not merge the two into one opaque score. Preserve separate research signals and evaluate incremental value.

## Relationship to `loomsci_lexicon`

The reference method is useful as a hypothesis generator and reproduction target. It is not treated as ground truth. The audit explicitly tests whether its phrase extraction, candidate-generation and effective-conductance choices are robust and whether G adds information beyond cheaper structural baselines.

## Evidence hierarchy

1. exact reproduction;
2. independent reimplementation;
3. sensitivity/ablation stability;
4. rolling-origin out-of-sample performance;
5. matched nulls and strong baselines;
6. independent downstream validation;
7. multi-source triangulation.

A visually compelling dashboard is not evidence by itself.

## Interpretation rules

- Future arXiv co-occurrence → evidence for lexical/network emergence only.
- Citation growth → evidence for scientific attention.
- GitHub/package/model adoption → evidence for implementation/usage.
- Patent activity → evidence for IP/technology-transfer activity.
- Multiple independent downstream signals → stronger evidence of economically relevant emergence.
- None of these alone proves commercialization or revenue.

## Current status

The repository currently contains the methodological scaffold and the existing backtest implementation. Final claims must be generated from frozen datasets and committed result files; no result should be hand-entered into the report.