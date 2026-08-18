# Recommendation engine

**Status: mixed — see per-model table.** The UI exposes 10 model IDs. Their implementations range from a live database query, to genuinely distinct offline-computed algorithms that get served, to offline-computed algorithms that are computed and stored but **never actually served** by the API. This document exists specifically to make that distinction legible, since it is not visible from the UI alone.

## Problem

Given a game a user is looking at, suggest other games they might like, and let a technical visitor compare recommendation algorithms side by side (this is the explicit purpose of the model-selector UI — see [docs/product/features.md](../product/features.md)).

## The 10 model IDs

Source of truth: `MODELS` array, `frontend/src/pages/GameDetail.tsx:64-75`.

| id | UI name | UI category | Computed | Served from |
|---|---|---|---|---|
| `popularity` | Popularity Baseline | Popularity-Based | Live | `games` table, `ORDER BY rank` |
| `metadata` | Metadata Similarity | Content-Based Filtering | Offline (script exists) | **Not served** — see [Known issue](#known-issue-four-model-ids-silently-serve-embedding-results) |
| `tfidf` | TF-IDF Vectorization | Content-Based Filtering | Offline (script exists) | **Not served** |
| `embedding` | Semantic Embedding | Content-Based Filtering | Live | `game_embeddings` pgvector cosine query |
| `hybrid` | Hybrid System | Content-Based Filtering | Offline (script exists) | **Not served** — silently returns `embedding` results instead |
| `graph_jaccard` | Graph Jaccard | Content-Based Filtering | Offline | `game_recommendations` table |
| `deepwalk` | Graph DeepWalk | Content-Based Filtering | Offline | `game_recommendations` table |
| `cf_item_cosine` | Item-Item Cosine | Collaborative Filtering | Offline | `game_recommendations` table |
| `cf_svd` | Matrix Factorization (SVD) | Collaborative Filtering | Offline | `game_recommendations` table |
| `cf_als` | Alternating Least Squares (ALS) | Collaborative Filtering | Offline | `game_recommendations` table |

There is also a fourth UI tab, **"Hybrid"** (`RECSYS_TYPES`, distinct from the `hybrid` *model id* above), permanently disabled with a "Soon" badge and no models filed under it — a planned fourth category that was never built out, separate from the `hybrid` model id issue below.

The default selected model in the UI is `hybrid`.

## Known issue: four model IDs silently serve embedding results

`RecommendationService.get_recommendations()` (`backend/app/services/recommendation_service.py`) contains:

```python
if model in ["embedding", "metadata", "tfidf", "hybrid"]:
    similar = self.db.query(GameEmbedding).filter(...).order_by(
        GameEmbedding.embedding.cosine_distance(source_embedding.embedding)
    ).limit(limit).all()
    ...
    reasons = ["Semantically similar based on rich metadata"]
```

All four of `embedding`, `metadata`, `tfidf`, and `hybrid` hit this exact branch and return **identical rankings** — pure semantic-embedding nearest neighbors — differing only in the label attached to the response. This is not a partial implementation gap: `scripts/precompute_content_recommendations.py` genuinely computes distinct TF-IDF cosine similarity, a metadata-feature blend, and a weighted hybrid ensemble (`0.45·embedding + 0.25·metadata + 0.15·TF-IDF + 0.15·quality_score`), and writes all of it to `game_recommendations` — but the `if` branch above intercepts those four model IDs before the code path that would read those precomputed rows is ever reached. The offline computation is real; the online serving of it is not wired up.

**Portfolio framing**: if asked "does Ludora have a real hybrid recommender," the honest answer is: the algorithm exists, is implemented correctly, and produces real precomputed output — but a routing bug means the live API never serves it. That is a defensible, common kind of real-world integration bug, and disclosing it here is more credible than letting the UI's Coverage/ILD table imply otherwise.

## Graph models: history of the `deepwalk` id

`scripts/precompute_graph_recommendations.py` produces two outputs. `graph_jaccard` is a genuine weighted multi-relation Jaccard similarity over mechanics/categories/designers/publishers/artists (weights 0.4/0.3/0.05/0.025/0.025, renormalized to sum to 1.0). The other builds a graph from live ORM objects, runs uniform random walks (`num_walks=10, walk_length=10`), and embeds it with `gensim.Word2Vec(..., sg=1)` — that's DeepWalk (uniform random walks), not the `node2vec` PyPI package's algorithm (biased walks controlled by `p`/`q`), so its model id is `deepwalk`.

It wasn't always: this id was previously `node2vec`, a holdover from a separate, disconnected attempt (`scripts/build_node2vec_graph.py` + `scripts/train_node2vec.py`) to use the actual `node2vec` package against a heterogeneous graph pickle. That attempt was scaffolded but never completed — no trained model artifact ever existed — and has been removed; the id was renamed to `deepwalk` to match what the served algorithm actually is. `data/processed/node2vec_graph.gpickle` (13.2 MB), that path's leftover graph pickle, is still present on disk pending a decision on whether to delete it (`data/` is gitignored in full, so this was never tracked in git).

## Per-model implementation

### Popularity (`popularity`)

Live query, `games` table ordered by `rank ascending`. No personalization, no offline computation.

### Content-based: Metadata, TF-IDF, Embedding, Hybrid (`metadata`, `tfidf`, `embedding`, `hybrid`)

All four are computed offline by `scripts/precompute_content_recommendations.py` (inline sklearn, no `BaseRecommender` subclass used for any of these):

- **Metadata**: `TfidfVectorizer` over categories+mechanics text (weight 0.7) blended with min-max-scaled numeric features (`game_weight`, `mfg_playtime`, `min_players`, `max_players`, weight 0.3), both via cosine similarity.
- **TF-IDF**: `TfidfVectorizer(stop_words='english', max_features=10000)` over name + description + categories + mechanics + designers + publishers text, cosine similarity.
- **Embedding**: cosine similarity directly on `game_embeddings` (the same vectors used by semantic search, filtered to the currently-configured model).
- **Hybrid**: `0.45·embedding_norm + 0.25·metadata_norm + 0.15·tfidf_norm + 0.15·quality_score_norm`, each component row-normalized to 0–1 first. `quality_score = 0.5·norm(inverse rank) + 0.5·norm(avg_rating)`.

Only `embedding` is actually served live (via a separate, simpler direct pgvector query in `RecommendationService`, not by reading these precomputed rows). See the known issue above.

### Graph-based (`graph_jaccard`, `deepwalk`)

See [Graph models: history of the `deepwalk` id](#graph-models-history-of-the-deepwalk-id) above.

### Collaborative filtering (`cf_item_cosine`, `cf_svd`, `cf_als`)

The only three model IDs with real `BaseRecommender` subclasses (`backend/app/recommenders/collaborative/`, ABC at `backend/app/recommenders/base.py`):

| Class | Model id | Hyperparameters | Library |
|---|---|---|---|
| `ItemCosineRecommender` | `cf_item_cosine` | `min_shared_users=50` | `sklearn.metrics.pairwise.cosine_similarity` on a co-occurrence-masked item-item matrix |
| `SVDRecommender` | `cf_svd` | `n_factors=50` | `sklearn.decomposition.TruncatedSVD(random_state=42)` on the transposed (item × user) ratings matrix |
| `ALSRecommender` | `cf_als` | `factors=50, iterations=15, regularization=0.1` | `implicit.als.AlternatingLeastSquares(random_state=42)`; similarity computed manually via sklearn cosine on `item_factors` rather than the `implicit` library's own `similar_items` |

Two independent scripts can populate these: `scripts/precompute_cf_recommendations.py` (fits all three directly from `data/raw/user_ratings.csv`, writes top-10 each) and, for `cf_svd` specifically, `scripts/train_svd.py` (trains + pickles to `data/models/cf_svd.pkl`, the only recommender with a saved model artifact) followed by `scripts/precompute_svd_recommendations.py`, which loads that pickle and writes top-20 rows. All three CF model IDs are read correctly by `RecommendationService` at request time (they fall through to the `game_recommendations` SELECT).

## Evaluation

See [docs/ml/evaluation.md](evaluation.md) for the full picture. In short: Coverage and ILD@10 numbers are hardcoded in the frontend for 6 of the 10 models (not sourced from any file the evaluation scripts write, since none of them persist output); `cf_item_cosine`, `cf_svd`, `cf_als`, and `popularity` show `—` in the UI even though `backend/evaluation/evaluate_recommenders.py` computes Coverage/ILD for the first three (it explicitly excludes `popularity`); Precision@10/Recall@10/NDCG@10 for the three CF models exist only as `print()` output from `backend/evaluation/cf_split.py`, never captured to a file.

## Known limitations

- **Whether the DB currently contains rows for every model ID has not been verified by this documentation pass** — the code paths exist and are traceable, but confirming live row counts requires a running, seeded database.
- No online feedback loop — nothing in the app records which recommendations a user clicked, so there is no way to close the loop with implicit signal.
- No model versioning — a rerun of any precompute script overwrites prior rows for that model id with no history.
- `get_recommendation_models()` (a separate endpoint, `GET /api/recommendation-models`) only returns 3 hardcoded entries and is not called by the frontend at all — it does not reflect the 10 model IDs actually usable via `GET /api/games/{id}/recommendations?model=...`.

## Related code

- `backend/app/services/recommendation_service.py`
- `backend/app/recommenders/base.py`, `backend/app/recommenders/collaborative/{item_cosine,svd,als}.py`
- `scripts/precompute_content_recommendations.py`, `scripts/precompute_svd_recommendations.py`, `scripts/precompute_cf_recommendations.py`, `scripts/precompute_graph_recommendations.py`
- `scripts/train_svd.py`
- `backend/evaluation/cf_split.py`, `backend/evaluation/evaluate_recommenders.py`
- `frontend/src/pages/GameDetail.tsx` (`MODELS`, `RECSYS_TYPES`, `GameRecommendations` component)
