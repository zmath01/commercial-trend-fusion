# 04_temporal_cv — rolling-origin evaluation

Random K-fold cross-validation is invalid for trend forecasting because it mixes future observations into training.

## Protocol

For forecast origin y:

```text
train = all observations <= y
features = information available at y only
test = outcome in (y, y+H]
```

Advance the origin one period at a time and pool out-of-fold predictions only after every origin has been evaluated.

Report:

- ROC-AUC;
- PR-AUC;
- Brier score / calibration;
- lift@K;
- bootstrap confidence intervals at the **origin level**;
- per-origin performance, not only the pooled number.

## Required model comparison

1. persistence / recent-growth baseline;
2. frequency or degree popularity baseline;
3. common-neighbor / Jaccard / Adamic-Adar / preferential-attachment baselines;
4. 2-hop strength I;
5. effective conductance G;
6. G + multi-source commercial signals;
7. ablated multi-source models.

The key quantity is incremental predictive value:

```text
Delta metric = metric(full model) - metric(strongest leakage-free baseline)
```

AUC around 0.5 should be reported as failure/no useful discrimination, not hidden by a dashboard ranking.