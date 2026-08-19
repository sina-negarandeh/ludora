# Case study

## Contents
- [Problem](#problem)
- [Product](#product)
- [Architecture](#architecture)
- [Data](#data)
- [Machine learning](#machine-learning)
- [Results](#results)
- [Tradeoffs and honest caveats](#tradeoffs-and-honest-caveats)

## Problem

[BoardGameGeek](https://boardgamegeek.com/) hosts the largest public dataset of board games and reviews on the internet, but its own UI is a 2000s-era forum layout. No semantic search, no aspect-level review analysis, a single "geek rating" as the only recommendation signal. Ludora asks what a modern discovery product looks like on top of that same data: hybrid search, a multi-algorithm recommendation engine you can actually compare, aspect-level sentiment extraction instead of one star rating, and a natural-language assistant on top of all of it.

## Product

Ludora is a board game discovery web app. A filterable, sortable catalog. A game detail page with rich metadata, ranking badges, and custom SVG statistical visualizations. A review browser with per-aspect sentiment ("Community Consensus"). A nine-algorithm recommendation engine with a model comparison UI. A conversational assistant that browses, searches, compares, and recommends by natural language. Every one of these is a real, running feature. See [docs/product/features.md](product/features.md) for a screenshot-backed walkthrough of each.

There are no user accounts, no login, no saved preferences, and no personalization loop. Every visitor sees the same catalog. It's a discovery and exploration tool, not a personalized recommendation app.

## Architecture

The backend is a layered FastAPI service: routes call services, services call the ORM or a recommender class, and nothing skips a layer. 18 REST endpoints across 6 route files, all but the health check carrying explicit OpenAPI summaries. The schema is normalized down to the taxonomy level: Category, Subdomain, Theme, and Family each get their own entity and join tables rather than one denormalized string column, tracked across 21 sequential, reversible Alembic migrations.

The more interesting architectural fact is what the FastAPI layer *doesn't* do. With the exception of live search and 3 of the 9 recommendation model IDs (`popularity`, `embedding`, `hybrid`), almost everything the API serves was computed by an offline Python script and written to Postgres ahead of time. Full breakdown: [docs/architecture/README.md](architecture/README.md) and [docs/architecture/data-pipeline.md](architecture/data-pipeline.md).

## Data

Ludora merges two Kaggle datasets on BGG ID, [threnjen/board-games-database-from-boardgamegeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) for game metadata and [jvanelteren/boardgamegeek-reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/) for 26M+ reviews, with an explicit field-preference policy for the outer join (`scripts/build_master_dataset.py`). Most of both datasets feeds the pipeline directly, or as a fallback source for games missing from the other one. A handful of files, an older ratings snapshot and superseded review snapshots, go unread. Full breakdown: [docs/data/README.md](data/README.md#what-each-file-is-used-for).

BGG's own taxonomy splits into four distinct concepts, each modeled as its own set of tables. Subdomain is BGG's rank and leaderboard type (Strategy, Party, Thematic, and five more). Category is its actual content tag (Economic, Fantasy, Card Game, and so on). Theme is specifically the `Theme:` group inside BGG's much larger `boardgamefamily` field. Family is that full field: 72 namespaces, about 4,200 values, modeled as its own two-level hierarchy (`families` holds the namespace, `subfamilies` holds the value, foreign-keyed to its parent) rather than forced into the flat pattern everything else in the schema uses, since it's the one taxonomy field that's genuinely hierarchical in the source data.

## Machine learning

Four ML/AI systems, each documented separately by problem rather than by library: [search](ml/search.md), [recommendations](ml/recommenders.md), [ABSA and summarization](ml/absa.md), and the [AI assistant](ml/assistant.md). The recommendation engine is the most structurally interesting of the four. It exposes 9 model IDs across four paradigms: popularity (1), content-based (5: TF-IDF, a metadata blend, semantic embedding, and two models sharing the same item-metadata graph, weighted Jaccard and a DeepWalk-via-`gensim` implementation with model id `deepwalk`), collaborative filtering (2: item-item cosine and ALS, both genuine `BaseRecommender` subclasses), and hybrid (1: a live cross-paradigm blend).

Nine models is a lot of surface area, so nothing is left redundant. An old `ensemble` model that duplicated the current cross-paradigm `hybrid` blend, and a second dense 50-dimensional latent-factor decomposition (`cf_svd`, `TruncatedSVD`) that duplicated what ALS already computes, are both gone. `hybrid` itself is real, not a stub: it blends `cf_item_cosine` (collaborative) and `metadata` (content) scores 0.5/0.5, computed live per request rather than precomputed. `RecommendationService.get_recommendations()` routes each of the 9 model IDs to its own live query or its own precomputed `game_recommendations` rows, with no shared fallback branch collapsing distinct models into identical results. Full per-model routing table: [docs/ml/recommenders.md](ml/recommenders.md).

ABSA runs 17-aspect zero-shot classification through `yangheng/deberta-v3-base-absa-v1.1`, a discriminative classifier rather than the generative-LLM-prompted-for-JSON approach the pipeline used before it. That earlier approach has been removed from the repo entirely. See [docs/ml/absa.md](ml/absa.md#one-approach-today-an-earlier-one-was-tried-and-removed).

## Results

Every evaluation script computes real metrics: `evaluate_search.py` for MRR/NDCG/Recall, `evaluate_recommenders.py` for Coverage/ILD, `cf_split.py` for Precision/Recall/NDCG on the two collaborative filtering models. All three log to MLflow and can write a results file. Search evaluation is the one that's actually been run end to end: MRR@10, NDCG@10, and Recall@100 for all three search modes are committed at `backend/evaluation/results/`, so those numbers are labeled **Measured**. Coverage and ILD for the recommendation models, and Precision/Recall/NDCG for the two CF models, haven't been run to produce a committed file yet, so those stay **Observed** until they are. Full accounting, system by system: [docs/ml/evaluation.md](ml/evaluation.md).

## Tradeoffs and honest caveats

**Speed over test coverage.** The commit history spans five calendar days. That pace produced a working, feature-dense app with a real layered architecture and a real migration history, and zero automated test assertions. Every `test_*.py` file in the repo is a print-only smoke script; several require a live database and/or a live local LLM server to run at all. Detail: [docs/engineering/testing.md](engineering/testing.md).

**Breadth over depth in the recommendation engine.** Nine model IDs across four paradigms is a lot of surface area for a short build, and keeping each one correctly routed and evaluated took real work: deleting a redundant SVD pipeline and an in-paradigm blend that predated the current `hybrid` model. A narrower engine with fewer algorithms would have been easier to keep correct from the start, but wouldn't have covered the same range of technique: popularity, content-based, graph, and collaborative filtering side by side.

**Classification coverage lags eligibility for ABSA, closing incrementally in bounded chunks.** The quality/eligibility filter (`app.core.review_quality`) runs over the entire ~4.2M-review corpus, not a pre-restricted sample: 267,950 reviews are eligible, measured directly, not estimated. The DeBERTa classifier runs in resumable, time-boxed sessions (`--minutes N`) rather than one multi-hour sitting, with 39,484 of 267,950 attempted so far (about 14.7%) at a measured 20 to 24 reviews per second. Getting the filter cheap enough to run at full-corpus scale also surfaced a real resumability bug: reviews yielding zero storable aspects weren't being marked done, so every chunked session was silently re-classifying an ever-growing backlog before making new progress. That's a timing gap that's closing, not a coverage number the docs are quiet about.

**Local-only LLM dependency.** Both the assistant and the summarization feature need an Apple Silicon Mac running MLX locally by default, though the endpoint is OpenAI-compatible and swappable. That's a real constraint on who can run every feature of this app.

**No production security posture.** No auth, wide-open CORS, a hardcoded local DB credential default. Fine for a local portfolio project, and it would need to change before any public deployment. Full list: [docs/limitations.md](limitations.md).
