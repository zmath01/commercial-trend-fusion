# 01_data — provenance, snapshots, schemas

This stage defines the immutable evidence layer for the research program.

## Required principles

1. Record the exact source, retrieval date, snapshot/version, query/filter, and software version for every external dataset.
2. Separate **source data** from **derived data**. Never silently replace a source snapshot with a newer one during reproduction.
3. Store stable identifiers and source timestamps so records can be joined without using display names as keys.
4. Keep a data dictionary and a leakage audit for every feature.

## Planned sources

| Source | Role | Canonical key | Time field | Status |
|---|---|---|---|---|
| arXiv metadata | research corpus | arxiv_id | first submission date | implemented |
| OpenAlex | citation / topic metadata | openalex_id / DOI / arxiv_id | publication date | planned |
| Semantic Scholar | citation cross-check | paperId / DOI / arxiv_id | publication date | planned |
| GitHub | implementation/adoption | repository id / URL | created_at / pushed_at | prototype signal exists |
| PyPI | package adoption | project name | release/download date | planned |
| Hugging Face | model/dataset adoption | repo id | created_at/download time | planned |
| Patent datasets | technology transfer | patent/application id | filing/grant date | planned |

## Canonical panel

The core analytical unit is:

```text
entity_id, entity_type, year,
research_signal_*, implementation_signal_*, citation_signal_*,
patent_signal_*, adoption_signal_*
```

For fusion experiments the canonical pair key is deterministic:

```text
pair_id = hash(min(concept_a, concept_b) || max(concept_a, concept_b))
```

No outcome observed after the prediction cutoff may be used to construct a historical feature.

## Snapshot manifest

Every real-data run should write a machine-readable manifest containing:

```yaml
run_id: <git-sha>-<timestamp>
data_sources:
  - name: arxiv
    snapshot: <exact snapshot or retrieval interval>
    retrieved_at: <UTC timestamp>
    query: <query/filter>
code_commit: <git sha>
config_hash: <sha256>
```

The current committed sample is suitable for CI and pipeline verification, not for estimating final scientific effect sizes.