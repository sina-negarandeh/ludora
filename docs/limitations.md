# Known limitations

Grouped by area. Each item links to the doc with full evidence and detail; this page is a scannable index, not a duplicate explanation.

## Product

- **No user accounts, no authentication, no personalization.** Every visitor sees the same catalog and the same non-personalized recommendation baselines. Frame Ludora as a discovery and exploration tool, not a personalized app.
- **The AI Assistant has no memory across turns.** Every message is parsed independently, even though a `conversation_id` field exists in the request schema. A multi-step plan's steps can reference each other, but only within one message. Detail: [docs/ml/assistant.md](ml/assistant.md#known-limitation-no-multi-turn-memory).
- **The assistant has no grammar-constrained structured output.** `ParsedIntent`/`ParsedPlan` validity relies on prompting plus post-hoc JSON repair and retry, not a token-level guarantee. The local serving stack (`mlx_lm.server`) has no schema-aware decode hook. Detail: [docs/ml/assistant.md](ml/assistant.md#parsing-is-repair-first-not-trust-first), [docs/roadmap.md](roadmap.md).

## Machine learning

- **Recommender diversity and CF ranking-quality evaluation results aren't committed yet.** Both scripts can log to MLflow and write a results file, the same capability `evaluate_search.py` already uses, but neither has been run since that capability was added. Search evaluation results (MRR/NDCG/Recall across all three modes) are committed and real. Detail: [docs/ml/evaluation.md](ml/evaluation.md).
- **ABSA classification is running in resumable chunks, not full eligible-corpus coverage yet.** 39,484 of 267,950 eligible reviews attempted (about 14.7%). Detail: [docs/ml/absa.md](ml/absa.md#coverage-full-corpus-filtered-not-sampled).
- **No accuracy evaluation exists for ABSA, summarization, or assistant intent parsing.** No ground-truth annotation set, no human rating, no benchmark.
- **LLM summarization has only been run for one example game.** No batch invocation over the catalog exists. Detail: [docs/ml/absa.md](ml/absa.md#downstream-llm-summarization-community-consensus-paragraph).
- **No online feedback loop.** Nothing records which recommendations, search results, or assistant responses a user actually engaged with, so nothing here can be evaluated or improved against real usage.

## Engineering

- **No automated test suite.** Every `test_*.py` file in `backend/` is a print-only script with zero `assert` statements, and several require a live database and/or a live local LLM server to run meaningfully. No frontend test framework is installed. No CI is configured. Detail: [docs/engineering/testing.md](engineering/testing.md).
- **No authentication on any route.**
- **CORS is fully open** (`allow_origins=["*"]`, `allow_credentials=True`), marked `# For development` in source but not conditionally disabled for any other environment.
- **`DATABASE_URL` has a hardcoded local-development default credential** in `backend/app/core/config.py`, mirrored in `docker-compose.yml`. Low severity for a local portfolio project; would need to move to environment-only configuration (with a committed `.env.example` and no default) before any public deployment. No credential values are reproduced anywhere in this documentation set.
- **No CI/CD pipeline** of any kind.
- **The commit history spans five calendar days** (2026-08-15 to 2026-08-19). This is a concentrated build, not a project that has weathered long-lived production usage. Framing should reflect that honestly; see [docs/case-study.md](case-study.md).

## Data

- **Part of the raw data footprint is unused.** Dataset 1's `ratings_distribution.csv` and 5 of Dataset 2's 7 files are never read by any script, including two of the three multi-million-row review snapshots, `bgg-15m-reviews.csv` and `bgg-19m-reviews.csv`. Detail: [docs/data/README.md](data/README.md#what-each-file-is-used-for).
- **No DB-level `CHECK` constraints.** There's no rating-range enforcement, for instance; value validity is enforced only in application code, where it's enforced at all.
- **No exact dataset version or license metadata is recorded** beyond the Kaggle URLs themselves.

## What's genuinely solid despite the above

This page is deliberately exhaustive about gaps because the rest of the documentation set already covers what works. For the positive case, see [docs/case-study.md](case-study.md) and the strongest-honest-story framing in each ML doc under [docs/ml/](ml/README.md).
