# Known limitations

Grouped by area. Each item links to the doc with full evidence and detail — this page is a scannable index, not a duplicate explanation.

## Product

- **No user accounts, no authentication, no personalization.** Every visitor sees the same catalog and the same non-personalized recommendation baselines. Frame Ludora as a discovery/exploration tool, not a personalized app.
- **The AI Assistant has no memory across turns** — every message is parsed independently, even though a `conversation_id` field exists in the request schema. Detail: [docs/ml/assistant.md](ml/assistant.md#known-limitation-no-multi-turn-memory).
- **Two assistant intents (`get_reviews`, `get_aspects`) silently degrade** to a generic game-detail response instead of doing what their name implies. Detail: [docs/roadmap.md](roadmap.md).
- **The "Hybrid" recommendation UI tab is permanently disabled** ("Soon" badge, no models filed under it) — separate from the `hybrid` model id issue below. Detail: [docs/ml/recommenders.md](ml/recommenders.md).

## Machine learning

- **4 of 10 recommendation model IDs (`embedding`, `metadata`, `tfidf`, `hybrid`) all serve identical results** — a single live pgvector query, regardless of which is selected — even though `metadata`, `tfidf`, and `hybrid` have genuinely distinct offline-computed scores sitting unused in the database. Detail: [docs/ml/recommenders.md](ml/recommenders.md#known-issue-four-model-ids-silently-serve-embedding-results).
- **No evaluation results are persisted anywhere.** All three evaluation scripts (search, recommender diversity, CF ranking quality) compute real metrics and only print them — no results file exists in the repo. The Coverage/ILD numbers shown in the product UI are plausible but not traceable to a committed artifact. Detail: [docs/ml/evaluation.md](ml/evaluation.md).
- **ABSA classification is running in resumable chunks, not catalog-wide yet** — 39,484 of 267,950 eligible reviews attempted (~14.7%). Detail: [docs/ml/absa.md](ml/absa.md#coverage-full-corpus-filtered-not-sampled).
- **No accuracy evaluation exists for ABSA, summarization, or assistant intent parsing** — no ground-truth annotation set, no human rating, no benchmark.
- **LLM summarization has only been run for one example game** — no batch invocation over the catalog exists. Detail: [docs/ml/absa.md](ml/absa.md#downstream-llm-summarization-community-consensus-paragraph).
- **No online feedback loop** — nothing records which recommendations, search results, or assistant responses a user actually engaged with, so nothing here can be evaluated or improved against real usage.

## Engineering

- **No automated test suite.** Every `test_*.py` file in `backend/` is a print-only script with zero `assert` statements, and several require a live database and/or a live local LLM server to run meaningfully. No frontend test framework is installed. No CI is configured. Detail: [docs/engineering/testing.md](engineering/testing.md).
- **No authentication on any route.**
- **CORS is fully open** (`allow_origins=["*"]`, `allow_credentials=True`), marked `# For development` in source but not conditionally disabled for any other environment.
- **`DATABASE_URL` has a hardcoded local-development default credential** in `backend/app/core/config.py`, mirrored in `docker-compose.yml`. Low severity for a local portfolio project; would need to move to environment-only configuration (with a committed `.env.example` and no default) before any public deployment. No credential values are reproduced anywhere in this documentation set.
- **No CI/CD pipeline** of any kind.
- **The entire commit history spans two calendar days** (2026-08-15 to 2026-08-16) — this is a concentrated build, not a project that has weathered long-lived production usage. Framing should reflect that honestly; see [docs/case-study.md](case-study.md).

## Data

- **Part of the raw data footprint is unused.** Dataset 1's `ratings_distribution.csv` and 5 of Dataset 2's 7 files are never read by any script (including two of the three multi-million-row review snapshots, `bgg-15m-reviews.csv` and `bgg-19m-reviews.csv`). Detail: [docs/data/README.md](data/README.md#what-each-file-is-used-for).
- **No DB-level `CHECK` constraints** (e.g. no rating-range enforcement) — value validity is enforced only in application code where it's enforced at all.
- **No exact dataset version/license metadata is recorded** beyond the Kaggle URLs themselves.

## What's genuinely solid despite the above

This page is deliberately exhaustive about gaps because the rest of the documentation set already covers what works. For the positive case, see [docs/case-study.md](case-study.md) and the "strongest honest story" framing in each ML doc under [docs/ml/](ml/README.md).
