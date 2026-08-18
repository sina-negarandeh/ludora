# Phase 1 — Evidence-First Repository Audit

**Project:** Ludora  
**Audited:** 2026-08-16  
**Auditor:** Principal Software Architect / ML Engineer / Data Scientist / Product Analyst / Technical Writer

---

## 1. Executive Project Inventory

### Product Summary

Ludora is a board-game discovery web application backed by the BoardGameGeek (BGG) dataset. It presents a game catalog, per-game detail pages, hybrid search, a multi-algorithm recommendation engine, aspect-based sentiment analysis of community reviews, and a conversational AI assistant. Every feature is implemented from scratch as a portfolio-quality, end-to-end ML system.

### Engineering Findings

- **Stack:** FastAPI + SQLAlchemy + PostgreSQL/pgvector (backend); React 19 + TypeScript + TanStack Query + Tailwind CSS (frontend); Docker Compose for local orchestration.
- **Architecture:** A clean layered design — `routes → services → (recommenders / ORM models)` — introduced deliberately in commit `c89a915` ("Refactor backend architecture to Layered Design").
- **API surface:** 5 route files (`games`, `search`, `metadata`, `recommendations`, `assistant`). All routes have OpenAPI summaries and `response_model` annotations (commit `df892ef`).
- **DB migrations:** 13 Alembic migrations covering initial schema, normalized relational entities, vectors/search columns, rating distributions, category ranks, ABSA tables, interactions, and game summaries — providing a complete, auditable schema history.
- **Frontend:** Two page-level components (`GamesList.tsx` ~42 KB, `GameDetail.tsx` ~63 KB) plus 6 smaller components. Rich glassmorphic design with SVG-based custom visualizations.
- **Known engineering debt:** `app/explainers/` directory exists but is completely empty (only `__pycache__`). `src/ludora/` directory is empty. Both `infrastructure/docker/` and `infrastructure/postgres/` are empty. No CI/CD pipeline exists.

### Data Science Findings

- **Source data:** Two heterogeneous BGG Kaggle datasets merged. (1) [`threnjen/board-games-database-from-boardgamegeek`](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) — the flat CSVs under `data/raw/` (`games.csv`, `mechanics.csv`, `themes.csv`, `subcategories.csv`, `artists_reduced.csv`, `designers_reduced.csv`, `publishers_reduced.csv`, `user_ratings.csv`, `ratings_distribution.csv`, documented by `data/raw/bgg_data_documentation.txt`). (2) [`jvanelteren/boardgamegeek-reviews`](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/) — everything under `data/raw/reviews/` (`games_detailed_info.csv`, `games_detailed_info2025.csv`, and the dated review snapshots `2020-08-19.csv`, `2022-01-08.csv`, `bgg-15m-reviews.csv`, `bgg-19m-reviews.csv`, `bgg-26m-reviews.csv`). `backend/scripts/build_master_dataset.py` merges dataset 1's `games.csv` with dataset 2's `games_detailed_info2025.csv` (outer join on `BGGId`) to build `master_games.csv`; the review snapshots from dataset 2 feed the separate reviews pipeline.
- **Processed data:** 27 files in `data/processed/` including master games, ratings (~470 MB CSV), reviews (~994 MB CSV), relational tables, a Node2Vec graph pickle (`node2vec_graph.gpickle`, 13 MB), and a stratified review sample cache (`data/stratified_samples.json`).
- **Model artifacts:** `data/models/cf_svd.pkl` (5.9 MB trained SVD model) and `data/models/lid.176.ftz` (fastText LID model). No ALS or Item-Cosine pkl files found in the repo.
- **Statistical preprocessing:** `scripts/generate_distributions.py` reads the raw games CSV, computes histogram density + CDF per metric (Complexity, Playtime, Min Age, Max Players) per category, and writes `frontend/public/distributions.json` (25 KB). This file is present and committed.

### ML/AI Findings

- **Search:** `SearchService` implements lexical (`websearch_to_tsquery` + `ts_rank_cd`), semantic (pgvector cosine distance with `all-MiniLM-L6-v2`), and hybrid (Reciprocal Rank Fusion with k=60) search. All three paths are live in code.
- **Recommendation engine:** 9 model IDs referenced in the UI (`popularity`, `metadata`, `tfidf`, `embedding`, `hybrid`, `graph_jaccard`, `node2vec`, `cf_item_cosine`, `cf_svd`, `cf_als`). `RecommendationService.get_recommendations()` handles `popularity` and the embedding-family directly at runtime; all others are served via precomputed `game_recommendations` table rows. Only `cf_svd` has a precompute script and a saved `.pkl`. Node2Vec is trained by `scripts/train_node2vec.py` and precomputed by `scripts/precompute_graph_recommendations.py` (root-level). CF ALS and Item-Cosine have `.fit()` implementations and a `cf_split.py` evaluation script, but no precompute-to-DB scripts and no saved artifacts.
  > **Phase 2 correction (2026-08-16):** the list above is actually **10** model IDs, not 9 — this was a counting slip in the original audit (the list itself is complete and correct). Deeper Phase 2 code reading also found: `scripts/precompute_cf_recommendations.py` (top-level, distinct from the `backend/scripts/` script of the same purpose) *does* precompute `cf_item_cosine` and `cf_als` to the DB — the "no precompute-to-DB scripts" finding above was based on an incomplete script inventory. And `RecommendationService` routes `metadata`, `tfidf`, and `hybrid` — not just the "embedding-family" — through the identical live embedding query. See `docs/ml/recommenders.md` for the corrected, fully-cited account.
- **ABSA:** `backend/scripts/absa_extract_hf.py` uses `yangheng/deberta-v3-large-absa-v1.1` (HuggingFace zero-shot ABSA) with fastText quality filtering to extract 22-aspect sentiment from reviews. Runs offline; writes to the `review_aspects` table. `data/processed/pilot_absa_filtered.csv` (4 MB) exists as a pilot artifact.
- **LLM summarization:** `SummarizationService` calls a local OpenAI-compatible endpoint (defaults to `http://localhost:8080/v1`) using structured JSON output to produce per-game "Community Consensus" paragraphs, stored in `game_summaries`. The configured model is `Qwen/Qwen3-30B-A3B-MLX-4bit` via Apple MLX.
- **AI assistant:** `AssistantService` calls the same local MLX server to parse natural language into a typed `ParsedIntent` Pydantic model. `AssistantOrchestrator` routes to 5 handler branches.

### Evaluation Findings

- `backend/evaluation/evaluate_search.py` — implements MRR@10, NDCG@10, Recall@100 across 3 search modes using 5 handwritten test queries in `search_queries.json`. **No result file exists in the repo.**
- `backend/evaluation/evaluate_recommenders.py` — computes Catalog Coverage and Intra-List Diversity (ILD@10) for 9 model IDs. **No result file exists.**
- `backend/evaluation/cf_split.py` — runs Precision@10, Recall@10, NDCG@10 on Item-Cosine, SVD, ALS via an 80/20 user-based split from `data/processed/master_ratings.csv`. **No result file exists.**
- **The exception:** Coverage and ILD values for 7 content-based models are hardcoded directly into `frontend/src/pages/GameDetail.tsx` (lines 64–75). These are the only numeric evaluation results in the repository. They appear to be real outputs manually pasted into the UI rather than consumed from an API or artifact file.

---

## 2. Capability and Evidence Matrix

| Capability | Status | Code Evidence | Test / Evaluation Evidence | Visual Evidence | Documentation Need |
|---|---|---|---|---|---|
| Game catalog browse + paginate | **Implemented** | `GET /api/games` in `routes/games.py`, `GameService.get_games()`, `GamesList.tsx` | `test_routes.py` (smoke only) | None | Architecture + API ref |
| Lexical search (FTS) | **Implemented** | `SearchService.search_lexical()` using `websearch_to_tsquery` + `TSVECTOR` column | `evaluate_search.py` (no stored results) | None | Data + ML doc |
| Semantic search (embedding) | **Implemented** | `SearchService.search_semantic()` with `all-MiniLM-L6-v2` + pgvector cosine | `evaluate_search.py` (no stored results) | None | ML doc |
| Hybrid search (RRF) | **Implemented** | `SearchService.search()` fusing lexical + semantic via RRF k=60 | `evaluate_search.py` (no stored results) | None | ML doc |
| Multi-filter browse (players, weight, year, mechanics, themes, categories) | **Implemented** | `apply_game_filters()` in `search_service.py`; `GameService.get_games()` | None | None | Feature doc |
| Sorting (rank, rating, year, complexity, name) | **Implemented** | `GameService.get_games()` sort logic; `GamesList.tsx` sort UI | None | None | — |
| Game detail page | **Implemented** | `GET /api/games/{bgg_id}` in `routes/games.py`; `GameDetail.tsx` (1340 lines) | `test_routes.py` smoke | None | — |
| Ranking badges (overall + category) | **Implemented** | `category_ranks` JSON field + `GameRankings` component in `GameDetail.tsx` | None | None | — |
| SVG smoothed-histogram density distributions | **Implemented** | `DistributionChart` component; `scripts/generate_distributions.py`; `public/distributions.json` committed | None | None | Data pipeline doc |
| Interactive rating histogram (0.5-step bars) | **Implemented** | `UserRatings` component in `GameDetail.tsx` using `rating_distribution` JSON field | None | None | — |
| "Recommended" percentage arc gauge | **Implemented** | Arc gauge in `UserRatings` (`gaugeCircumference`, `gaugeArcLength` math) | None | None | — |
| Review browsing with pagination | **Implemented** | `GET /api/games/{bgg_id}/reviews`; `ReviewService`; reviews section in `GameDetail.tsx` | `test_routes.py` smoke | None | — |
| Review language filter | **Implemented** | `language` param on reviews endpoint; `language_breakdown` in response; `languageOptions` in UI | None | None | — |
| Review rating filter (positive/mixed/negative) | **Implemented** | `min_rating`/`max_rating` params on reviews endpoint; `rating_breakdown` in response | None | None | — |
| FastText language + quality filtering | **Implemented** (offline pipeline) | `compute_quality_score()` in `absa_extract_hf.py`; `lid.176.ftz` in `data/models/` | None | None | ML pipeline doc |
| ABSA extraction (DeBERTa zero-shot, 22 aspects) | **Implemented** (offline pipeline) | `absa_extract_hf.py` with `yangheng/deberta-v3-large-absa-v1.1`; `review_aspects` table + Alembic migration | `pilot_absa_filtered.csv` (pilot artifact) | None | ML doc |
| ABSA aggregation | **Implemented** | `absa_aggregate.py`; `GameAspectAggregate` model; `GET /api/games/{game_id}/aspects`; `AspectService` | None | None | ML doc |
| Aspect cards UI (Community Consensus) | **Implemented** | `CommunityConsensus` component in `GameDetail.tsx`; per-aspect arc gauges | None | None | — |
| LLM summarization (ABSA to paragraph) | **Implemented** | `SummarizationService`; `game_summaries` table + migration; `generate_summaries.py` | None | None | ML + Architecture doc |
| Popularity-based recommendations | **Implemented** | `RecommendationService` popularity branch (rank-ordered) | Coverage/ILD hardcoded as `null` | None | ML doc |
| Content-based (semantic embedding) | **Implemented** | pgvector cosine in `RecommendationService`; precomputed via root-level precompute script | ILD: 0.34, Coverage: 93.54% (hardcoded in UI) | None | ML doc |
| Content-based (TF-IDF) | **Implemented** (precomputed) | Model ID `tfidf` served from `game_recommendations` table | ILD: 0.44, Coverage: 95.41% (hardcoded in UI) | None | ML doc |
| Content-based (Metadata similarity) | **Implemented** (precomputed) | Model ID `metadata` served from `game_recommendations` table | ILD: 0.52, Coverage: 96.13% (hardcoded in UI) | None | ML doc |
| Content-based (Hybrid content) | **Implemented** (precomputed) | Model ID `hybrid` served from `game_recommendations` table | ILD: 0.39, Coverage: 90.49% (hardcoded in UI) | None | ML doc |
| Graph-based (Graph Jaccard) | **Implemented** (precomputed) | `node2vec_graph.gpickle` (13 MB) committed; `precompute_graph_recommendations.py` | ILD: 0.52, Coverage: 94.03% (hardcoded in UI) | None | ML doc |
| Graph-based (Node2Vec / DeepWalk) | **Implemented** (precomputed) | `train_node2vec.py`, `build_node2vec_graph.py`; graph pickle committed | ILD: 0.54, Coverage: 96.55% (hardcoded in UI) | None | ML doc |
| CF Item-Item Cosine | **Implemented** (offline class) | `ItemCosineRecommender` with `min_shared_users=50`; no precompute script | `cf_split.py` (no stored results); Coverage/ILD: `null` | None | ML doc |
| CF SVD (Matrix Factorization) | **Implemented** | `SVDRecommender`; `cf_svd.pkl` (5.9 MB); `train_svd.py`; `precompute_recommendations.py` | `cf_split.py` (no stored results); Coverage/ILD: `null` | None | ML doc |
| CF ALS | **Implemented** (offline class only) | `ALSRecommender` class; no precompute script; no saved artifact | `cf_split.py` (no stored results); Coverage/ILD: `null` | None | ML doc |
| AI assistant intent parsing (local LLM) | **Implemented** | `AssistantService.parse_query()` via OpenAI-compatible local endpoint; `ParsedIntent` Pydantic schema | `test_assistant.py`, `test_assistant_retry.py`, `test_orchestrator.py` (integration only, LLM-dependent) | None | Architecture + ML doc |
| Assistant orchestration (browse/search/compare/recommend/get_game) | **Implemented** | `AssistantOrchestrator.execute()` with 5 handler branches; entity resolution | `test_orchestrator.py` (3 test queries, integration only) | None | Architecture doc |
| Assistant entity resolver | **Implemented** | `EntityResolver` with class-level caches for categories/themes/mechanics; fuzzy game title resolution via `resolve_game()` | None | None | Architecture doc |
| Assistant UI (chat drawer + inline cards) | **Implemented** | `AssistantDrawer.tsx`, `AssistantMessageBubble.tsx`, `CompactGameRow.tsx` | None | None | — |
| Multi-turn conversation memory | **Planned / Partial** | Comment `// In the future, pass conversation_id here` in `AssistantDrawer.tsx:44`; `conversation_id` param accepted but unused in `AssistantOrchestrator` | None | None | Roadmap / Limitations |
| Conversational `get_reviews` / `get_aspects` intents | **Stub** | Listed in `IntentEnum`; both fall back to `_handle_get_game()` per inline comment "Not fully implemented" | None | None | Limitations doc |
| Containerized local development | **Implemented** | `docker-compose.yml` (3 services: `pgvector/pgvector:pg15`, FastAPI backend, Vite frontend); DB health check | None | None | Setup doc |
| Node2Vec full training pipeline | **Implemented** | `build_node2vec_graph.py`, `train_node2vec.py`; graph pickle committed | None | None | ML pipeline doc |
| Stratified ABSA sampling | **Implemented** | `generate_stratified_sample.py`, `count_stratified.py`; `data/stratified_samples.json` committed | None | None | ML pipeline doc |

> **Phase 2 correction (2026-08-16):** every "committed" reference above to a `data/` path (`node2vec_graph.gpickle` in the two Graph-based rows and the Node2Vec pipeline row; `data/stratified_samples.json` in the Stratified ABSA sampling row) is incorrect. The entire `data/` directory is gitignored (`.gitignore:8`) — nothing under `data/raw/`, `data/processed/`, or `data/models/` is tracked in git. These files exist on the local filesystem where this audit was run, not in version control. `public/distributions.json`, referenced two rows above this note, is outside `data/` and genuinely is committed — that one line was correct as written.

---

## 3. Claim-Risk Audit

Claims in the current `README.md` that require correction, requalification, or evidence before publication:

| README Claim | Risk Level | Finding |
|---|---|---|
| "Aspect-Based Sentiment Analysis (ABSA): A zero-shot classification pipeline running on `deberta-v3-large-absa`." | **Low** | The full model ID is `yangheng/deberta-v3-large-absa-v1.1`. The pipeline is an offline batch process, not a real-time endpoint. Should state "offline batch pipeline." |
| "Identifies…22 specific game aspects" | **Low** | The `TAXONOMY` list in `absa_extract_hf.py` has exactly 22 entries. Accurate. |
| "Collaborative Filtering: Item-Item Cosine Similarity, Matrix Factorization (SVD), and Alternating Least Squares (ALS)." | **Medium** | All three classes exist with proper `fit()` / `recommend()` methods. SVD has a trained artifact and is precomputed to the DB. Item-Cosine and ALS have no precompute scripts and no DB artifacts; they serve no live recommendations. The README implies all three are equally operational. |
| "Hybrid System: Weighted ensemble algorithms providing a balanced, highly diverse output" | **Medium** | The `hybrid` model ID serves precomputed rows from `game_recommendations`. The `RecommendationService` routes live `hybrid` requests to the embedding (pgvector cosine) branch, not a genuine weighted ensemble. The precomputed rows and the live runtime path are disjoint. |
| "Contextual Memory: Maintains a rolling multi-turn memory buffer" | **High** | `AssistantDrawer.tsx` contains `// In the future, pass conversation_id here`. The `conversation_id` parameter is accepted by the API but never used in `AssistantOrchestrator`. Each `/api/assistant/chat` call is stateless. No rolling memory buffer exists anywhere in the codebase. |
| "Dynamic Semantic Routing: The assistant uses an intent-classifier to route user queries…" | **Medium** | The routing is not a semantic classifier. The LLM is given the full `ParsedIntent` Pydantic schema and instructed to output a valid JSON enum for `intent`. Routing is a JSON `if/elif` chain in `AssistantOrchestrator`. This is a valid engineering choice, but "semantic routing" and "intent-classifier" are inaccurate labels. |
| "Comprehensive Filters: Robust filtering…by exact Player Count, Play Time, Complexity Weight, Year, Categories, and Mechanics." | **Medium** | `GameService.get_games()` does not implement `min_playtime`/`max_playtime` filter parameters. Playtime filtering is not implemented despite the README claiming it is. |
| "Semantic Search: Vector-embedding based search allowing users to search by 'vibe'" | **Low** | `search_semantic()` uses `all-MiniLM-L6-v2` to encode queries and performs cosine distance against `Game.embedding`. Accurate. |
| "Pre-computes and beautifully renders Gaussian density curves via SVG mathematical paths" | **Low** | The curves are computed via `np.histogram` + `np.convolve` (box smoothing), not true Gaussian KDE. "Smoothed histogram density curves" is technically more accurate, but the visual effect is substantively equivalent. Minor. |
| "Employs Meta's `fastText` model to assign quality scores to incoming reviews" | **Low** | `compute_quality_score()` in `absa_extract_hf.py` uses `lid.176.ftz` for language detection + length + spam heuristics. Accurate. `fasttext-wheel` confirmed in `pyproject.toml`. |
| "30-Billion parameter LLM (`Qwen3-30B-A3B-MLX-4bit`) directly on local hardware" | **Low** | The model name is hardcoded as default in `AssistantService` and `SummarizationService`. The architecture is model-agnostic (any OpenAI-compatible local server works). Accurate as configured. |

---

## 4. Recommended Documentation Architecture

Based on evidence of what is actually implemented, the following documents are justified. Documents with no real content are omitted.

```
README.md                          (rewrite — fixes claim-risk items above)
AGENTS.md                          (brief: how to develop, run scripts, run tests)

docs/
  README.md                        (index linking all docs below)
  product/
    features.md                    (user-facing feature guide grounded in implemented code)
  architecture/
    README.md                      (system diagram: frontend + FastAPI + PostgreSQL/pgvector + MLX LLM)
    data-pipeline.md               (ingest -> merge -> embed -> ABSA -> precompute)
  data/
    README.md                      (dataset sources, schema, migrations overview)
  ml/
    README.md                      (overview of all 9 rec models + search + ABSA)
    recommenders.md                (per-model: algorithm, training data, precompute, limitations)
    search.md                      (lexical / semantic / hybrid; RRF details; embedding model)
    absa.md                        (DeBERTa ABSA pipeline; fastText filtering; 22-aspect taxonomy; stratification)
    assistant.md                   (LLM intent parsing; orchestrator routing; entity resolution; limitations)
    evaluation.md                  (evaluation scripts, metrics, and actual result tables)
  engineering/
    testing.md                     (describes existing test scripts, what they cover, what is missing)
    setup.md                       (Docker Compose quick-start; native UV/npm setup; MLX LLM setup)
  roadmap.md                       (honest: multi-turn memory, get_reviews/get_aspects, CI/CD, etc.)
  limitations.md                   (no auth, CORS wildcard, partial ABSA, CF ALS/cosine not precomputed)
  assets/                          (screenshots, GIFs)
```

**Omitted** (no real content to anchor them): `docs/case-study.md`, standalone ADR files.

**Added** (new, not previously drafted):
- `docs/architecture/data-pipeline.md` — the multi-script offline pipeline is architecturally complex and entirely undocumented.
- `docs/ml/assistant.md` — the LLM-parsing + structured routing architecture is a distinctive design decision worth explicit documentation.
- `docs/engineering/setup.md` — promotes the basic Getting Started section into a proper guide with MLX LLM context.

---

## 5. Visual-Asset Plan

> **Update (2026-08-16, post author-review):** The author captured 8 real application screenshots after Phase 1 was drafted. They now exist at `docs/assets/images/`. The table below supersedes the original "no screenshots exist" finding.

### Existing Visual Assets

| Asset | Location | Notes |
|---|---|---|
| `game_catalog_page.default.png` | `docs/assets/images/` | Game catalog grid, default state |
| `game_catalog_page.default.ai_assistant.drawer.png` | `docs/assets/images/` | Game catalog grid with AI Assistant drawer open |
| `game_detail_page.hero_section.brass_birmingham.png` | `docs/assets/images/` | Game Detail hero section — Brass: Birmingham |
| `game_detail_page.stats.brass_birmingham.png` | `docs/assets/images/` | Game Detail stats/distributions section — Brass: Birmingham |
| `game_detail_page.ratings.brass_birmingham.png` | `docs/assets/images/` | Game Detail ratings histogram + recommend gauge — Brass: Birmingham |
| `game_detail_page.reviews.user_reviews.brass_birmingham.png` | `docs/assets/images/` | Game Detail user reviews list — Brass: Birmingham |
| `game_detail_page.reviews.community_consensus.brass_birmingham.png` | `docs/assets/images/` | Game Detail ABSA "Community Consensus" + aspect cards — Brass: Birmingham |
| `game_detail_page.recommendation_engine.model_selector.brass_birmingham.png` | `docs/assets/images/` | Recommendation engine model selector dropdown — Brass: Birmingham |
| `favicon.svg` | `frontend/public/favicon.svg` | Custom SVG favicon |
| `icons.svg` | `frontend/public/icons.svg` | Icon sprite sheet |
| `distributions.json` | `frontend/public/distributions.json` | Data asset, not a visual |

These 8 screenshots cover catalog browse, AI assistant drawer, game detail hero, stats/distributions, ratings, reviews, ABSA community consensus, and the recommendation model selector — i.e., items 1–6 of the original missing-visuals list below are now satisfied as static screenshots (no GIFs/motion captured yet).

### Remaining Missing Visuals (in priority order)

1. **System architecture diagram** — a Mermaid diagram showing: raw data CSVs → Python pipeline scripts → PostgreSQL/pgvector → FastAPI backend → React frontend → local MLX LLM server, with offline ABSA and precompute pipelines annotated. (Diagram, not a screenshot — to be authored in `docs/architecture/README.md`.)

2. **Motion/GIF captures** (nice-to-have, not blocking) — the original plan called for short GIFs of (a) hero → stats scroll and (b) an assistant query round-trip. Static screenshots now exist for both; GIFs would add interaction context but are not required for the documentation set to be evidence-complete.

---

## 6. Portfolio Narrative Recommendation

### Product and UX

**Strongest story:** A premium board-game discovery UI — rich metadata, beautiful custom SVG visualizations (smoothed density distributions, rating histograms with 0.5-step bars, arc gauges), and a conversational assistant sidebar. The 63 KB `GameDetail.tsx` is evidence of sustained UX craftsmanship. The glassmorphic design, `DOMPurify` sanitization, `keepPreviousData` anti-flicker, and scroll-driven blur indicators show deliberate attention to perceived quality.

**Honest caveat:** No user authentication, no user accounts, no personalization loop. Framing should be "discovery and exploration tool," not "personalized recommendation app."

### Software Engineering

**Strongest story:** A layered FastAPI architecture with clean service separation, a normalized relational schema with 13 tracked Alembic migrations, explicit N+1 fix with `selectin` loading (commit `6a853cc`), type-safe Pydantic v2 schemas with field-level OpenAPI documentation, full Docker Compose reproducibility, and thoughtful TypeScript types throughout the frontend.

**Honest caveat:** No automated test runner (pytest/vitest) and no CI pipeline. All tests are manually-executed scripts without an assertion framework. The `CORS allow_origins=["*"]` wildcard is a development-only setting that should be disclosed.

### Machine Learning Engineering

**Strongest story:** A full ML engineering lifecycle — offline data pipelines (data merge → quality filter → embedding → stratified sampling → ABSA extraction → precomputation), a `BaseRecommender` ABC with three concrete CF implementations following scikit-learn `fit()/recommend()` conventions, a two-stage LLM summarization pipeline with structured JSON output, and live hybrid search with RRF fusion. The fastText quality filter and stratified review sampling scripts show ML engineering maturity.

**Honest caveat:** CF ALS and Item-Cosine are not precomputed to the DB (no live recommendations served). No model versioning or experiment tracking. ABSA was run on a pilot subset; `pilot_absa_filtered.csv` and `stratified_samples.json` suggest partial coverage.

### Data Science

**Strongest story:** Merging two heterogeneous BGG Kaggle datasets ([threnjen/board-games-database-from-boardgamegeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) and [jvanelteren/boardgamegeek-reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/)) with a documented field-level policy (`build_master_dataset.py`), a 22-aspect taxonomy designed for board-game review analysis, pre-computed per-category smoothed histogram distributions with CDF for percentile positioning ("You Are Here"), and stratified review sampling ensuring balanced sentiment representation for ABSA at scale.

**Honest caveat:** No Jupyter notebooks, no exploratory analysis artifacts. The `explore_dists.py` root-level script is the only EDA artifact — a 9-line one-off. Exact dataset source URLs are recorded above (author-supplied); no in-repo file previously documented them (correction applied 2026-08-16 — see below).

### AI / NLP / Recommender Systems

**Strongest story:** Three search modalities unified under one RRF fusion framework; 9 recommendation models spanning popularity, content-based (embedding, TF-IDF, metadata), graph-based (Jaccard co-occurrence, Node2Vec), and collaborative filtering (Item-Cosine, SVD, ALS), all serving from a single precomputed `game_recommendations` table; a zero-shot ABSA pipeline extracting 22-dimensional sentiment from open-ended text; a structured LLM parsing pipeline with entity disambiguation and typed intent routing.

**Honest caveat:** No user-item feedback loop at runtime. No A/B testing or online evaluation. The "hybrid" recommendation model served at runtime is actually a single embedding model (a naming inconsistency). Multi-turn assistant memory is not implemented.

---

## 7. Gaps and Highest-Value Next Steps

### Missing Documentation

- No `AGENTS.md` or contributor guide.
- No per-model documentation (training data, hyperparameters, algorithm rationale).
- ~~No data provenance documentation (exact Kaggle dataset names, versions, licenses).~~ **Resolved by author correction (2026-08-16):** two source datasets confirmed — [threnjen/board-games-database-from-boardgamegeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) (`data/raw/*.csv`) and [jvanelteren/boardgamegeek-reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/) (`data/raw/reviews/*`). Licenses/versions still unconfirmed — link out to the Kaggle pages rather than asserting a license in docs.
- No offline pipeline runbook (ordered sequence of scripts to go from raw data to a fully populated DB).
- No architecture diagram.
- No `docs/limitations.md` disclosing partial ABSA coverage, no user auth, CORS wildcard, CF model gaps.
- `distributions.json` is committed but has no documentation explaining its contents or how to regenerate it.

### Missing Tests

- No pytest test suite. No `conftest.py`. No test fixtures or mocks. All `backend/` test files are ad-hoc scripts that print output, require a live DB and LLM, and have no assertions.
- No unit tests for: `SearchService` RRF logic, `EntityResolver` disambiguation, `AssistantOrchestrator` routing branches, `SVDRecommender`, `ALSRecommender`, `ItemCosineRecommender`.
- No frontend tests (no vitest, no React Testing Library, no Playwright/Cypress E2E).
- No schema/migration tests.

### Missing Evaluation

- Search (`evaluate_search.py`): no stored results file. MRR@10, NDCG@10, Recall@100 for lexical/semantic/hybrid are unknown from the repository.
- CF evaluation (`cf_split.py`): no stored results. Precision@10, Recall@10, NDCG@10 for Item-Cosine, SVD, ALS are unknown.
- Recommender diversity (`evaluate_recommenders.py`): results only as hardcoded UI values for 7 models; no external results file. Coverage/ILD for `cf_item_cosine`, `cf_svd`, `cf_als` are `null` in the UI — these models were never evaluated.
- ABSA: no quality benchmark (no ground-truth aspect annotations to measure classification accuracy against).
- LLM summarization: no evaluation (no human-rated quality score, no faithfulness check).
- Assistant parsing: no evaluation (no test set of natural-language queries with expected parsed intents).

### Missing Reproducibility

- CF ALS and Item-Cosine: no precompute-to-DB scripts. A new developer cannot reproduce live recommendations for these models.
- TF-IDF and Metadata content-based models: no training scripts found in the repository. Their `game_recommendations` rows exist in the DB but how they were generated is undocumented.
- ABSA: `pilot_absa_filtered.csv` suggests a pilot was run, but the full production ABSA run (which games, how many reviews, total aspects extracted) is not documented.
- `data/processed/master_ratings.csv` (~470 MB) is committed but no script documents how to regenerate it from the raw review CSVs.
  > **Phase 2 correction:** not committed — see the note in Section 2. It's present on disk only; the regeneration-script gap itself still stands.
- No `Makefile` or task runner to chain offline pipeline steps in order.

### Planned but Unimplemented Functionality

- **Multi-turn memory in the assistant** — `conversation_id` accepted but ignored; noted as future in `AssistantDrawer.tsx:44`.
- **`get_reviews` / `get_aspects` assistant intents** — in `IntentEnum`, but both fall back to `_handle_get_game()` per inline code comment "Not fully implemented."
- **Hybrid recommendation tab in UI** — `RECSYS_TYPES` includes `{ id: 'Hybrid', available: false }` with a "Soon" badge in the model picker.
- **`app/explainers/` module** — directory exists with only `__pycache__`, no Python source files.
- **`infrastructure/docker/` and `infrastructure/postgres/`** — both empty; suggest planned but not completed infrastructure-as-code work.
- **`src/ludora/`** — empty Python package directory at the root.

### Security Note

No hardcoded secrets, API keys, or external service tokens were found in any source file, configuration file, or committed data file during this audit.

> **Warning — Credentials in version-controlled configuration:** `backend/app/core/config.py` defaults `DATABASE_URL` to a plaintext credential string for the local database. This same credential pair appears as plaintext environment variables in `docker-compose.yml`. For a local-development-only portfolio project this is low severity, but if this repository is ever made public, both the default in `config.py` and the `docker-compose.yml` credentials should be replaced with environment variable references with no defaults, and a `.env.example` file should be committed instead. Do not reproduce these credential values anywhere in documentation.
