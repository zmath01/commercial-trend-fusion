# 07_orthogonal_validation — test a different scientific outcome

The central orthogonal hypothesis is:

> Does historical concept coupling predict economically relevant scientific emergence, rather than merely future lexical co-occurrence?

For concept pair (A,B) at cutoff t, construct features using only data available by t:

```text
G(A,B,t)
I(A,B,t)
frequency(A), frequency(B)
degree(A), degree(B)
common-neighbor / Jaccard / Adamic-Adar
cross-field distance
novelty / first-seen indicators
```

Then predict independent outcomes over a later horizon H:

```text
citation growth
patent appearance / patent growth
software implementation or repository creation
package/model adoption where measurable
```

## Crucial distinction

Do **not** call future arXiv co-occurrence an economic outcome. It remains the lexical link-prediction task. Economic/implementation outcomes must come from an independent source.

## Triangulation

Use at least two independent downstream sources where feasible. A positive result on citations but not patents/software is evidence about scientific attention, not commercialization.

## Leakage rule

A downstream record is eligible only if its event date is strictly after the prediction cutoff. Publication dates, repository creation dates, patent filing dates and package/model release/download timestamps must be preserved separately.

## Primary model comparison

```text
Outcome ~ popularity + growth + degree + standard link predictors + G
```

The coefficient / performance increment attributable to G is the object of interest, not the raw correlation between G and outcome.