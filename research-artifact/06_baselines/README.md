# 06_baselines — strong competitors

Do not compare a sophisticated method only against random pairs.

## Pair-fusion baselines

For the same candidate population and cutoff, compute:

- Common Neighbors;
- Jaccard coefficient;
- Adamic-Adar;
- Resource Allocation;
- Preferential Attachment;
- 2-hop strength I;
- effective conductance G.

## Commercialization baselines

For every downstream outcome compare against:

- current level / persistence;
- recent slope and CAGR;
- degree/popularity;
- publication volume alone;
- implementation signal alone;
- citation momentum alone;
- patent momentum alone where available;
- simple logistic regression with locked features.

The scientific question is not whether G correlates with the future. It is whether G provides **incremental information after controlling for the strongest cheap predictors**.