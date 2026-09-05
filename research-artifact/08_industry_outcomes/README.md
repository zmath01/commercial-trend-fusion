# 08_industry_outcomes — independent commercialization panel

This stage converts the scientific-network experiment into a genuine commercialization test.

## Outcome families

### 1. Citations
OpenAlex and/or Semantic Scholar. Prefer a frozen snapshot and stable identifiers. Measure cumulative citations or citation velocity after the cutoff, with age normalization.

### 2. Patents
Use a documented patent dataset such as PatentsView or another reproducible public source. Prefer filing/application dates for temporal prediction; distinguish patent appearance from grant.

### 3. Software implementation
Use GitHub repository creation dates and stable repository identifiers. Require topic/concept matching rules to be declared before looking at outcomes.

### 4. Package/model adoption
Where coverage permits, use PyPI, Hugging Face or equivalent registries. Store downloads/releases/model usage separately; do not conflate availability with adoption.

## Outcome table

```text
pair_id, cutoff_year, horizon,
citation_growth, patent_event, github_event,
package_adoption, model_adoption
```

Each outcome gets its own model and its own null/baseline comparison. Do not collapse heterogeneous outcomes into one CSI without a pre-registered rationale.

## Preferred interpretation

- citation-only success = scientific attention;
- GitHub/package success = implementation/adoption evidence;
- patent success = technology-transfer/IP evidence;
- multiple independent signals = stronger commercialization evidence.

None is equivalent to revenue. Revenue should be treated as a separate, much harder validation target.