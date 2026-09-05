# 02_reproduction — independent reproduction contract

The first scientific task is to reproduce the published `loomsci_lexicon`-style result before extending it.

## Reproduction target

Freeze:

- exact arXiv snapshot and date range;
- phrase normalization and stoplists;
- minimum frequencies and edge thresholds;
- candidate-generation rule;
- G/effective-conductance definition;
- hit definition;
- seed/candidate set;
- prediction cutoff and horizon.

Record every discrepancy in `reproduction_log.csv` rather than silently adapting the method.

## Two implementations

1. **Reference path:** execute the upstream implementation where possible.
2. **Independent path:** reimplement the estimator from the mathematical specification without copying implementation details.

Agreement should be assessed on intermediate artifacts as well as headline metrics:

```text
lexicon -> annotations -> graph edges -> candidate pairs -> G -> outcomes -> metrics
```

The independent path is the important scientific control: identical numbers produced by copied code are weaker evidence than agreement between independently implemented estimators.

## Acceptance criteria

For each claimed result report:

- absolute difference;
- relative difference;
- whether the difference changes ranking or significance;
- explanation (data snapshot, preprocessing, numerical solver, or implementation bug).

Do not label a result "reproduced" merely because the dashboard looks similar.