# Recommendation engine

**Status: all 9 model IDs are correctly wired and served.** Implementations range from a live database query, to genuinely distinct offline-precomputed algorithms served from `game_recommendations`, to a live cross-paradigm blend computed at request time. This document exists to make that distinction legible, since it isn't visible from the UI alone.

## Problem

Given a game a user is looking at, suggest other games they might like, and let a technical visitor compare recommendation algorithms side by side. That comparison is the explicit purpose of the model-selector UI; see [docs/product/features.md](../product/features.md).

## The 9 model IDs

Source of truth: `RECOMMENDATION_MODELS`, `backend/app/core/ml_config.py:374-393`, served via `GET /api/recommendation-models` (`RecommendationService.get_recommendation_models()`) and consumed live by the frontend (`fetchRecommendationModels()` in `frontend/src/api/games.ts`, called from `frontend/src/pages/GameDetail.tsx`). There's no separate hardcoded frontend model list.

| id | Name | Paradigm | Computed | Served from |
|---|---|---|---|---|
| `popularity` | Popularity Ranking | Popularity | Live | `games` table, `ORDER BY rank ASC` |
| `metadata` | Metadata Similarity | Content | Offline | `game_recommendations` |
| `tfidf` | TF-IDF Similarity | Content | Offline | `game_recommendations` |
| `embedding` | Semantic Embedding Similarity | Content | Live | pgvector cosine-distance query on `game_embeddings` |
| `graph_jaccard` | Graph Jaccard | Content | Offline | `game_recommendations` |
| `deepwalk` | Graph Embedding (DeepWalk) | Content | Offline | `game_recommendations` |
| `cf_item_cosine` | Item-Item Similarity | Collaborative | Offline | `game_recommendations` |
| `cf_als` | Matrix Factorization (ALS) | Collaborative | Offline | `game_recommendations` |
| `hybrid` | Weighted Hybrid | Hybrid | Live | blends `cf_item_cosine` + `metadata` rows from `game_recommendations` at request time |

Four paradigms: popularity, content, collaborative, hybrid. Graph-based models (`graph_jaccard`, `deepwalk`) are classified under **content**, not collaborative. Despite the word "graph," both build their graph purely from item metadata (mechanics, categories, subdomains, families, designers, publishers, artists) and never read the `ratings` table.

The "Hybrid" tab in the UI is enabled and functional; it maps to the `hybrid` model id.

## Routing: `RecommendationService.get_recommendations()`

`backend/app/services/recommendation_service.py` routes each model id to one of three paths:

- **`popularity`**: a live query, `games` table ordered by `rank ASC`, the same global top-N regardless of the source game. That's by design; it's the non-personalized baseline every other model is implicitly compared against. Score is a real value, min-max normalized inverse rank among the returned candidates, via `minmax_normalize_scores()` in `backend/app/recommenders/utils.py`.
- **`hybrid`**: a live blend, computed at request time (see [Hybrid](#hybrid-hybrid) below). Never written to `game_recommendations`.
- **`embedding`**: a live pgvector cosine-distance query against `GameEmbedding` rows, the only content model computed at request time rather than precomputed. Score is `round(1.0 - cosine_distance, 4)`.
- **Everything else** (`metadata`, `tfidf`, `graph_jaccard`, `deepwalk`, `cf_item_cosine`, `cf_als`): a generic lookup. Each reads its own precomputed rows from `game_recommendations` filtered by `model`, ordered by `score DESC`.

Each model id reads its own data, live or precomputed as appropriate; none of them share a fallback branch that would collapse distinct models into identical rankings.

## Per-model implementation

### Popularity (`popularity`)

A live query, `games` table ordered by `rank ASC`. No personalization, no offline computation. Score is normalized inverse rank (see routing above), not a flat constant.

### Content paradigm: Metadata, TF-IDF, Embedding, Graph Jaccard, DeepWalk

Five models. `metadata`, `tfidf`, `graph_jaccard`, and `deepwalk` are precomputed offline; `embedding` is live (see routing above).

- **Metadata Similarity** (`metadata`), from `scripts/precompute_content_recommendations.py`: `0.7 * cosine(TF-IDF over categories+mechanics+subdomains+families tokens) + 0.3 * cosine(min-max-scaled [game_weight, mfg_playtime, min_players, max_players])`. Weights are `RecommenderConfig.METADATA_CATEGORICAL_WEIGHT` / `METADATA_NUMERIC_WEIGHT` in `backend/app/core/ml_config.py`.
- **TF-IDF Similarity** (`tfidf`), same script: `TfidfVectorizer(stop_words='english', max_features=10000)` over one blob per game (`name + description + categories + mechanics + subdomains + families + designers + publishers`), cosine similarity.
- **Semantic Embedding Similarity** (`embedding`): a live pgvector cosine-distance search against `GameEmbedding` rows (Qwen3-Embedding-0.6B via MLX, `SearchConfig.EMBEDDING_MODEL`). The only content model computed at request time; always reflects current `game_embeddings` state.
- **Graph Jaccard** (`graph_jaccard`), from `scripts/precompute_graph_recommendations.py::run_jaccard`: weighted multi-relation Jaccard over 7 relations (mechanics, categories, subdomains, families, designers, publishers, artists). Weights (`RecommenderConfig.GRAPH_JACCARD_WEIGHTS`, renormalized to sum to 1 at use time): `mechanics=0.35, categories=0.25, subdomains=0.15, families=0.1, designers=0.05, publishers=0.025, artists=0.025`.
- **Graph Embedding (DeepWalk)** (`deepwalk`), same script, `run_deepwalk`: the same 7-relation item-metadata graph as `graph_jaccard` (game nodes connected to mechanic, category, subdomain, family, designer, publisher, and artist nodes). Uniform random walks (`DEEPWALK_NUM_WALKS=10`, `DEEPWALK_WALK_LENGTH=10`, seeded via `RANDOM_SEED=42`), then `gensim.Word2Vec(sg=1, vector_size=64, window=5, epochs=1, min_count=1)`, cosine similarity on the resulting embeddings. This is DeepWalk, uniform random walks, explicitly not node2vec's biased walks controlled by `p`/`q`, which is why the model id is `deepwalk` and not `node2vec`.

`themes` isn't a separate feature here because BGG's `Theme:` namespace is already one of `families`'s 72 namespaces (`scripts/build_master_dataset.py` lines ~302-304); adding both `themes` and `families` as separate relations or tokens would double-count the same tag values.

There's no `ensemble` model. What used to be an in-paradigm content blend (embedding, metadata, TF-IDF, and a quality score recombined with weights) wasn't an independent signal, and duplicated what the cross-paradigm `hybrid` model below already does. It doesn't exist in `RECOMMENDATION_MODELS`, the precompute script, or anywhere served.

### Collaborative paradigm (`cf_item_cosine`, `cf_als`)

Two model ids, both real `BaseRecommender` subclasses under `backend/app/recommenders/collaborative/` (ABC at `backend/app/recommenders/base.py`), fit against the `ratings` table (26.2M rows, 555K distinct users, 27,825 distinct rated games) via `scripts/precompute_cf_recommendations.py`.

| Class | Model id | Key hyperparameters | Library |
|---|---|---|---|
| `ItemCosineRecommender` (`backend/app/recommenders/collaborative/item_cosine.py`) | `cf_item_cosine` | `min_shared_users=50` (`RecommenderConfig.CF_ITEM_COSINE_MIN_SHARED_USERS`) | `sklearn.metrics.pairwise.cosine_similarity` on a co-occurrence-masked item-item matrix |
| `ALSRecommender` (`backend/app/recommenders/collaborative/als.py`) | `cf_als` | `factors=50, iterations=15, regularization=0.1` | `implicit.als.AlternatingLeastSquares(random_state=42)`; similarity computed manually via sklearn cosine on `item_factors` |

`cf_item_cosine` uses adjusted, mean-centered cosine similarity (Sarwar et al., 2001, "Item-Based Collaborative Filtering Recommendation Algorithms"): each user's ratings are centered by subtracting that user's own mean rating before building the user-by-item matrix, correcting for individual rating-scale bias, someone who rates everything 8-10 versus someone who uses the full 1-10 range. Centering only touches actually-rated entries; an unrated item stays absent, never becomes an implicit zero.

`cf_als` converts ratings to Hu/Koren/Volinsky (2008) confidence weights before fitting: `confidence = 1.0 + CF_ALS_CONFIDENCE_ALPHA * rating`, with `CF_ALS_CONFIDENCE_ALPHA = 40` (the paper's own default, not tuned against this dataset). `implicit`'s ALS is designed for implicit-feedback confidence weights, not raw explicit ratings; feeding raw ratings directly would conflate "confidence this interaction is positive" with the rating's own polarity, so a rating of 2/10 would read as a weak-but-positive signal instead of a dislike.

There's no `cf_svd` model. `TruncatedSVD` was redundant with ALS: both are dense 50-dimensional latent-factor decompositions of the same ratings matrix, likely to correlate more with each other than either does with `cf_item_cosine`. There's one CF pipeline, not two.

### Hybrid (`hybrid`)

The only cross-paradigm model, and the only model in the **hybrid** paradigm. Computed live at request time in `RecommendationService.get_recommendations()`, never precomputed, never written to `game_recommendations`.

Formula: `0.5 * collaborative_norm + 0.5 * content_norm`, where collaborative is `cf_item_cosine`'s precomputed top-N rows for the source game, content is `metadata`'s precomputed top-N rows for the source game, and each is independently min-max normalized via `minmax_normalize_scores()` (dict-based, `backend/app/recommenders/utils.py`) before blending.

Configured via `RecommenderConfig.HYBRID_ENGINE_WEIGHTS = {"collaborative": 0.5, "content": 0.5}`, `HYBRID_COLLABORATIVE_MODEL = "cf_item_cosine"`, `HYBRID_CONTENT_MODEL = "metadata"` (`backend/app/core/ml_config.py`). An even 0.5/0.5 split and those two specific representative models are a disclosed starting point, not tuned against any evaluation.

It's live rather than precomputed because both inputs are already-precomputed top-10 lists, so combining them is a few dozen floats and a sort, not an O(n²) similarity matrix; the same "cheap and freshness-sensitive stays live" reasoning applies to `embedding`. A `computed_at` column exists on `game_recommendations` for freshness tracking on models that are precomputed, but `hybrid` never gets a row there; it has no precomputed state to go stale.

## Data coverage

All 9 model ids that get precomputed have full catalog coverage: 27,825 to 28,208 of the catalog's 28,208 games, not a partial 10,000-game subset. Verified against a live database.

## Evaluation

See [docs/ml/evaluation.md](evaluation.md) for the full picture. In short:

- `backend/evaluation/evaluate_recommenders.py` computes catalog Coverage and ILD@10 for the 6 models that persist rows to `game_recommendations`: `['metadata', 'tfidf', 'graph_jaccard', 'deepwalk', 'cf_item_cosine', 'cf_als']`. It explicitly excludes `embedding` and `hybrid`, since both are live and never stored, so a `game_recommendations` query for either would always read 0 rows.
- `backend/evaluation/cf_split.py` computes Precision@10/Recall@10/NDCG@10 for the two CF recommenders, `ItemCosineRecommender` and `ALSRecommender`.
- `popularity` is not included in either evaluation script.

## Known limitations

- **No online feedback loop.** Nothing in the app records which recommendations a user clicked, so there's no way to close the loop with implicit signal.
- **No model versioning.** A rerun of any precompute script overwrites prior rows for that model id; `computed_at` records when a row was last written, not a history of prior values.
- `HYBRID_ENGINE_WEIGHTS` (0.5/0.5) and `GRAPH_JACCARD_WEIGHTS` are disclosed starting points, not empirically tuned against any evaluation metric.

## Related code

- `backend/app/services/recommendation_service.py`
- `backend/app/recommenders/base.py`, `backend/app/recommenders/collaborative/{item_cosine,als}.py`
- `backend/app/recommenders/utils.py` (`minmax_normalize_scores`)
- `backend/app/core/ml_config.py` (`RecommenderConfig`, `RECOMMENDATION_MODELS`)
- `scripts/precompute_content_recommendations.py`, `scripts/precompute_graph_recommendations.py`, `scripts/precompute_cf_recommendations.py`
- `backend/evaluation/cf_split.py`, `backend/evaluation/evaluate_recommenders.py`
- `frontend/src/pages/GameDetail.tsx`, `frontend/src/api/games.ts` (`fetchRecommendationModels`)
