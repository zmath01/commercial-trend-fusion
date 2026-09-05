# 03_ablation — stress-test the concept representation

The main threats to the arXiv phrase/network result are preprocessing and representation choices.

## Mandatory ablations

| Factor | Values |
|---|---|
| top words/phrases per paper | 20, 40, 50, 100, 200 |
| phrase length | 1–2, 1–4, 1–6 |
| minimum frequency | 3, 5, 10, 20 |
| edge threshold | 1, 2, 5, 10 |
| stoplist | baseline / no LLM-assisted list / alternate public list |
| concept representation | lexical phrase / noun phrase / TF-IDF / embedding cluster |
| graph | local neighborhood / full graph / degree-preserving sparsification |
| signal | common neighbors / Jaccard / Adamic-Adar / preferential attachment / G |

## Stability measures

For each variant calculate:

- lexicon overlap (Jaccard);
- top-K overlap;
- Spearman rank correlation of pair scores;
- network degree and component distributions;
- forecast AUC/PR-AUC/Brier and confidence intervals.

A conclusion is robust only when it survives reasonable preprocessing changes, not merely the default configuration.

## Specific hypothesis

Test whether effective conductance G adds information beyond the 2-hop structural signal I. The primary comparison is:

```text
G(A,B)  vs  I(A,B) = min(w_AW, w_WB)
```

under the same candidate population and the same temporal split.