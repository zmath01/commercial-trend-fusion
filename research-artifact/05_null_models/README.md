# 05_null_models — falsification tests

The research claim must beat null models that preserve the easy structure of the problem.

## Nulls

### N1: label permutation
Shuffle future outcomes while keeping historical features fixed. Expected AUC is approximately 0.5.

### N2: degree-preserving graph randomization
Rewire the historical concept graph while approximately preserving the degree sequence. Recompute G/I and the forecast.

### N3: frequency-matched pair null
Sample non-edge pairs matched on endpoint frequency/degree bands.

### N4: bridge-matched null
For every treatment pair A-W-B, replace B by B' satisfying the same A/W two-hop condition. This is the primary structural control.

### N5: temporal placebo
Train on the historical window but test against a pseudo-future window that precedes the prediction origin. A genuine forward signal should disappear.

## Interpretation

If G beats N3 but not N4, the apparent effect is explained by two-hop structure. If G beats N4 but fails N1/N2 or does not replicate across forecast origins, the result is unstable. Only a consistent advantage over all relevant nulls supports incremental information in G.