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

Board Game Geek (BGG) hosts the largest public dataset of board games and reviews on the internet, but its own UI is a 2000s-era forum layout: no semantic search, no aspect-level review analysis, and a single "geek rating" as the only recommendation signal. Ludora asks: what does a modern discovery product look like on top of that same data — hybrid search, a multi-algorithm recommendation engine a user (or reviewer) can actually compare, aspect-level sentiment extraction instead of a single star rating, and a natural-language assistant layered on top?

## Product

Ludora is a board-game discovery web app: a filterable, sortable catalog; a game detail page with rich metadata, ranking badges, and custom SVG statistical visualizations; a review browser with per-aspect sentiment ("Community Consensus"); a 10-algorithm recommendation engine with a model comparison UI; and a conversational AI assistant that can browse, search, compare, and recommend by natural language. All ten of these are real, running features — see [docs/product/features.md](product/features.md) for a screenshot-backed walkthrough of each.

**What Ludora is not**: there are no user accounts, no login, no saved preferences, and therefore no personalization loop. The honest framing is "discovery and exploration tool," not "personalized recommendation app" — every visitor sees the same non-personalized baselines.

## Architecture

The backend is a layered FastAPI service: routes call services, services call the ORM or a recommender class, nothing skips a layer. This wasn't the starting design — an explicit refactor commit (`c89a915`, "Refactor backend architecture to Layered Design") shows it was introduced partway through the build, on top of an already-working app. 19 REST endpoints across 6 route files, all but the health check carrying explicit OpenAPI summaries (`df892ef`). The database schema, 21 sequential and reversible Alembic migrations, shows the same iterate-in-the-open discipline: tags started as a single denormalized string column, moved to proper entity + join tables once the normalized design was clearly needed, and BGG's own taxonomy (Category, Subdomain, Theme, Family) was later split apart correctly after an audit found Category and Subdomain had been conflated under one label since the first migration.

The more interesting architectural fact is what the FastAPI layer *doesn't* do: with the exception of live search and 5 of 10 recommendation model IDs, almost everything the API serves was computed by an offline Python script and written to Postgres ahead of time. Full breakdown: [docs/architecture/README.md](architecture/README.md) and [docs/architecture/data-pipeline.md](architecture/data-pipeline.md).

## Data

Ludora merges two Kaggle datasets — [threnjen/board-games-database-from-boardgamegeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) (game metadata) and [jvanelteren/boardgamegeek-reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/) (26M+ reviews) — via an outer join on BGG ID with an explicit field-preference policy (`scripts/build_master_dataset.py`). Most of both datasets feeds the pipeline directly or as a fallback source for games missing from the other dataset; a handful of files (an older ratings snapshot, superseded review snapshots) go unread. Full breakdown: [docs/data/README.md](data/README.md#what-each-file-is-used-for).

BGG's own taxonomy — Category, Subdomain, Theme, and Family — turned out to be four distinct concepts that an earlier pass through this data had partly conflated under one label. Sorting that out against BGG's own wiki produced a normalized `subdomains` / `categories` / `themes` / `families` → `subfamilies` schema: Subdomain is BGG's rank/leaderboard type (Strategy, Party, Thematic...), Category is its real content tag (Economic, Fantasy...), Theme is specifically the `Theme:` group inside BGG's much larger `boardgamefamily` field, and Family is that full field — 72 namespaces, ~4,200 values — modeled as its own two-level hierarchy (`families` holds the namespace, `subfamilies` the value, FK'd to its parent) rather than force-fit into the flat pattern everything else in the schema uses, since it's the one taxonomy field that's genuinely hierarchical in the source data.

## Machine learning

Four ML/AI systems, each documented separately by problem rather than by library: [search](ml/search.md), [recommendations](ml/recommenders.md), [ABSA + summarization](ml/absa.md), and the [AI assistant](ml/assistant.md). The recommendation engine is the most structurally interesting of the four: it exposes **10** model IDs (not 9 — a miscount in this project's own earlier internal audit, corrected here) spanning popularity, content-based (TF-IDF, metadata blend, semantic embedding, weighted hybrid), graph-based (weighted Jaccard, a DeepWalk-via-gensim implementation, model id `deepwalk`), and three genuine collaborative-filtering classes (Item-Item Cosine, SVD, ALS) sharing a common `BaseRecommender` interface.

Digging into `RecommendationService`'s routing code surfaced something the model-selector UI doesn't reveal: four of those ten model IDs (`embedding`, `metadata`, `tfidf`, `hybrid`) currently return **identical** results, because a single `if` branch routes all four to the same live embedding-similarity query — even though the offline scripts that compute genuinely distinct TF-IDF and metadata-blend and weighted-hybrid scores run correctly and write their output to the database. The computation is real; the serving path for three of those four algorithms just never reads it. That's documented in detail, not hidden, in [docs/ml/recommenders.md](ml/recommenders.md#known-issue-four-model-ids-silently-serve-embedding-results) — it's the kind of integration bug that's genuinely common in systems with this many moving parts, and disclosing exactly where it lives is more useful to a reader than a routing table that implies otherwise.

The ABSA pipeline (17-aspect zero-shot classification via `yangheng/deberta-v3-base-absa-v1.1`) has real signal of iteration behind it: git history shows an earlier attempt using a local generative LLM (Ollama + `qwen2.5:7b`) prompted for JSON output, later replaced by the current discriminative zero-shot classifier. The commit history doesn't record *why* — commit messages in this repo are single-line subjects with no body — so the switch is presented as an observed fact (two implementations exist, only one is wired into the current pipeline), not as a reconstructed rationale. See [docs/ml/absa.md](ml/absa.md#two-implementations-exist--only-one-is-current).

## Results

Every evaluation script that exists (`evaluate_search.py` for MRR/NDCG/Recall, `evaluate_recommenders.py` for Coverage/ILD, `cf_split.py` for Precision/Recall/NDCG on the three CF models) computes the right metrics and then only prints them — none persist a results file. The Coverage/ILD numbers visible in the product UI for 6 of the 10 recommendation models are real-looking and internally consistent with the evaluation script's exact metric definitions and model grouping, but cannot be traced to a committed artifact, so they're labeled **Observed**, not **Measured**, throughout this documentation set. Full accounting, system by system: [docs/ml/evaluation.md](ml/evaluation.md).

## Tradeoffs and honest caveats

- **Speed over test coverage.** The commit history spans two calendar days. That pace produced a working, feature-dense app with a real layered architecture and a real migration history — and zero automated test assertions. Every `test_*.py` file in the repo is a print-only smoke script; several require a live database and/or a live local LLM server to run at all. Detail: [docs/engineering/testing.md](engineering/testing.md).
- **Breadth over depth in the recommendation engine.** Ten model IDs is a lot of surface area for a short build — enough that one routing bug (above) went unnoticed. A narrower engine with fewer, fully-wired algorithms would have been more defensible, but would not have demonstrated the same range of technique (popularity, content-based, graph, collaborative filtering side by side).
- **Classification coverage lags eligibility for ABSA, closing incrementally in bounded chunks.** The quality/eligibility filter (`app.core.review_quality`) runs over the *entire* ~4.2M-review corpus, not a pre-restricted sample — 267,950 reviews are eligible, measured directly, not estimated. The DeBERTa classifier is run in resumable, time-boxed sessions (`--minutes N`) rather than one multi-hour sitting, with 39,484 of 267,950 attempted so far (~14.7%) at a measured ~20-24 rev/sec. An earlier design (a stratified 10,000-review sample capped at the top 100 ranked games) was replaced once the filter itself became cheap enough to run at full-corpus scale; getting there also surfaced and fixed a real resumability bug — reviews yielding zero storable aspects weren't being marked done, so every chunked session was silently re-classifying an ever-growing backlog before making new progress. A disclosed, closing timing gap, not a silent one.
- **Local-only LLM dependency.** Both the assistant and the summarization feature require an Apple Silicon Mac running MLX locally by default (though the endpoint is OpenAI-compatible and swappable). That's a real constraint on who can run every feature of this app, disclosed rather than hidden behind "cloud-ready" language.
- **No production security posture.** No auth, wide-open CORS, a hardcoded local DB credential default. Entirely appropriate for a local portfolio project; explicitly flagged as needing to change before any public deployment. Full list: [docs/limitations.md](limitations.md).
