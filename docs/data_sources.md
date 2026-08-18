# Data sources

This project is built on open, key-less data first, with optional extensions
for adoption/commercial signals.

## Integrated

### arXiv Atom API (corpus)

- Endpoint: `https://export.arxiv.org/api/query`
- Usage: `python scripts/fetch_arxiv.py`
- Query: `cat:<category> AND submittedDate:[<year>01010000 TO <year>12312359]`,
  sorted by submission date descending, paginated (100/request), 3 s between
  requests (arXiv etiquette), automatic retries.
- Fields kept: `arxiv_id, title, abstract, primary_cat, cats, published, year`.
- **Caveat:** `cat:` queries match any category field, so results include
  papers whose primary category differs from the searched one; each paper's
  true `primary_cat` is retained for field attribution.
- Terms of use: https://info.arxiv.org/help/api/index.html

### Full-corpus alternative (production grade)

- Kaggle official arXiv dataset (Cornell University):
  https://www.kaggle.com/datasets/Cornell-University/arxiv
  ~2.4 M papers, Hive-partitioned parquet. Download once, point
  `config.yaml → corpus.raw_dir` at it (or write a small adapter that
  produces the same `cat=XX/year=YYYY/papers.csv` layout), then run
  `run_all.py` with `--no-cap`.
- OAI-PMH incremental sync is possible for daily freshness:
  http://export.arxiv.org/oai2 — more moving parts, documented for later.

## Documented extensions (not yet integrated)

| Signal | Source | Why it matters | Access |
|---|---|---|---|
| Citations / TLDRs | Semantic Scholar API (`api.semanticscholar.org`) | impact beyond arXiv | free tier, key optional |
| Adoption (repos) | GitHub Search API (`api.github.com/search/repositories`) | open-source momentum | token, 10 req/min |
| Adoption (packages) | PyPI JSON API (`pypi.org/pypi/<pkg>/json`) | library usage growth | open |
| Adoption (models) | HuggingFace Hub API (`huggingface.co/api/models`) | model ecosystem | open |
| Journal lag / quality | Crossref API, OpenAlex | peer-reviewed confirmation | open |
| Funding | NSF Award API, EU CORDIS | grants precede products | open |
| Hiring | LinkedIn/company sites (manual) | industry pull | manual |

Design note: arXiv frequency growth is a *leading* indicator; adoption signals
(GitHub/PyPI) are *confirming* indicators. A v2 roadmap is to fuse them with
clearly separated roles and a combined score whose components stay inspectable.

## Data license notes

- arXiv metadata: subject to arXiv API terms of use.
- Derived lexicon/results/site content in this repo: CC BY 4.0.
- Code: MIT.
