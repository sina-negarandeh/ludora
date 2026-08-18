# Content-based: Metadata, TF-IDF, Embedding, Hybrid

**Model IDs:** `metadata`, `tfidf`, `embedding`, `hybrid` · **Category:** Content-Based Filtering · **Status:** Computed offline; only `embedding` is actually served — see Known limitations

## Data

- Source: `games` table (via ORM) — categories, mechanics, designers, publishers, `game_weight`, `mfg_playtime`, `min_players`, `max_players`, `description`, `name`, `rank`, `avg_rating` — plus `game_embeddings`, filtered to the currently-configured model (produced separately — see [search-semantic.md](search-semantic.md)).
- No held-out split — all four are unsupervised similarity computations, not fit against a labeled objective.

## Model / Architecture

All four computed by one script, inline `sklearn` (no `BaseRecommender` subclass):

- **`metadata`**: `TfidfVectorizer` over categories+mechanics text, cosine similarity, blended with min-max-scaled numeric features (`game_weight`, `mfg_playtime`, `min_players`, `max_players`) also via cosine similarity.
- **`tfidf`**: `TfidfVectorizer(stop_words='english', max_features=10000)` over name + description + categories + mechanics + designers + publishers text, cosine similarity.
- **`embedding`**: cosine similarity directly on `game_embeddings` (the same vectors used by semantic search, filtered to the currently-configured model).
- **`hybrid`**: a weighted blend of the three similarities above plus a quality score, each row-normalized to 0–1 first.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig`.

| Param | Value |
|---|---|
| `METADATA_CATEGORICAL_WEIGHT` / `METADATA_NUMERIC_WEIGHT` | 0.7 / 0.3 |
| `TFIDF_MAX_FEATURES` | 10,000 |
| `HYBRID_WEIGHTS` | `{embedding: 0.45, metadata: 0.25, tfidf: 0.15, quality: 0.15}` |
| `QUALITY_RANK_WEIGHT` / `QUALITY_RATING_WEIGHT` (quality score blend) | 0.5 / 0.5 |
| `RECS_PER_MODEL_LIMIT` | 10 |

No random seed needed — every step is deterministic (TF-IDF fit + cosine similarity, no sampling or iterative optimization).

## Training

Not gradient training — deterministic vectorization + similarity computation, batched over the catalog (100 games per batch to bound memory).

- Script: `scripts/precompute_content_recommendations.py`
- Command: `uv run --project backend python scripts/precompute_content_recommendations.py`
- MLflow experiment: `recommender/content_based` (run name `precompute`) — logs every weight above plus `n_games` and `recommendations_written`.

## Artifact

None persisted — TF-IDF vectorizers and similarity matrices are rebuilt from scratch each run; only the resulting top-10 rows per model per game are written to `game_recommendations`.

## Evaluation

- Diagnostic only (no ranking-quality eval exists for these four — no held-out relevance labels to evaluate against): `backend/evaluation/evaluate_recommenders.py` computes Catalog Coverage and Intra-List Diversity @10 for `metadata`, `tfidf`, `embedding`, `hybrid`.
- MLflow experiment: `recommender/content_based` (run name `<model_id>_eval_coverage_ild`), one run per model — same experiment as the precompute step above.
- Results file: `backend/evaluation/results/recommenders_coverage_ild_latest.json`.

## Known limitations

- **Only `embedding` is actually served.** `RecommendationService.get_recommendations()` routes `embedding`, `metadata`, `tfidf`, and `hybrid` all to the identical live pgvector query — `metadata`, `tfidf`, and `hybrid`'s genuinely distinct precomputed rows above are written to `game_recommendations` but never read by the API. This is a real, disclosed serving bug, not a documentation gap — see `docs/ml/recommenders.md#known-issue-four-model-ids-silently-serve-embedding-results`. Deliberately **not** fixed in this pass (flagged as a separate follow-up, distinct from this session's reproducibility-foundation work).
- No ranking-quality evaluation exists for any of the four (Coverage/ILD measure diversity and catalog reach, not whether the recommendations are actually *good*).
