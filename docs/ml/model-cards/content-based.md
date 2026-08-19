# Content-based: Metadata, TF-IDF, Embedding

**Model IDs:** `metadata`, `tfidf`, `embedding` · **Category:** Content-Based Filtering · **Status:** Computed offline, all three served; see Known limitations

`hybrid` is a different, cross-paradigm model (a live blend of `cf_item_cosine` + `metadata`, computed at request time, never stored) and is out of scope for this content-paradigm card; see [docs/ml/recommenders.md](../recommenders.md) and [cf-item-cosine.md](cf-item-cosine.md). There's no `ensemble` model; a weighted blend of `embedding`, `metadata`, `tfidf`, and a quality score has been removed entirely, along with its supporting code (`compute_quality_scores()` in `app/recommenders/utils.py`, `RecommenderConfig.ENSEMBLE_WEIGHTS`, `QUALITY_RANK_WEIGHT`, `QUALITY_RATING_WEIGHT`).

## Data

- Source: `games` table (via ORM): categories, mechanics, subdomains, families, designers, publishers, `game_weight`, `mfg_playtime`, `min_players`, `max_players`, `description`, `name`, plus `game_embeddings`, filtered to the currently-configured model (produced separately; see [search-semantic.md](search-semantic.md)).
- `subdomains` and `families` feed both `metadata`'s categorical TF-IDF features and `tfidf`'s text blob. Deliberately not `themes`: [BGG](https://boardgamegeek.com/)'s `Theme:` namespace is already one of `families`'s 72 namespaces (`scripts/build_master_dataset.py:302-304`), so adding both would double-count the same tags.
- No held-out split; all three are unsupervised similarity computations, not fit against a labeled objective.

## Model / Architecture

Both computed by one script (`scripts/precompute_content_recommendations.py`), inline `sklearn`, no `BaseRecommender` subclass:

- **`metadata`**: `0.7 * cosine(TF-IDF over categories+mechanics+subdomains+families) + 0.3 * cosine(min-max-scaled game_weight/mfg_playtime/min_players/max_players)`.
- **`tfidf`**: `TfidfVectorizer(stop_words='english', max_features=10000)` over `name + description + categories + mechanics + subdomains + families + designers + publishers` text, cosine similarity.
- **`embedding`**: cosine similarity directly on `game_embeddings` (the same vectors used by semantic search, filtered to the currently-configured model), computed live at request time, not by this script (see Known limitations).

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig`.

| Param | Value |
|---|---|
| `METADATA_CATEGORICAL_WEIGHT` / `METADATA_NUMERIC_WEIGHT` | 0.7 / 0.3 |
| `TFIDF_MAX_FEATURES` | 10,000 |
| `RECS_PER_MODEL_LIMIT` | 10 |

No random seed needed; every step is deterministic (TF-IDF fit plus cosine similarity, no sampling or iterative optimization).

## Training

Not gradient training; deterministic vectorization and similarity computation, batched over the catalog (100 games per batch to bound memory). This script owns and writes only `metadata` and `tfidf` (`OWNED_MODELS = ['metadata', 'tfidf']` scopes both the pre-run delete and MLflow logging so it never touches other models' rows); `embedding` is never written here, since it's computed live (see Model / Architecture).

- Script: `scripts/precompute_content_recommendations.py`
- Command: `uv run --project backend python scripts/precompute_content_recommendations.py`
- MLflow experiment: `recommender/content_based` (run name `precompute`), logging every weight above plus `n_games` and `recommendations_written`.

## Artifact

None persisted. TF-IDF vectorizers and similarity matrices are rebuilt from scratch each run; only the resulting top-10 rows per model per game are written to `game_recommendations`.

## Evaluation

- Diagnostic only; no ranking-quality eval exists for these, since there are no held-out relevance labels to evaluate against. `backend/evaluation/evaluate_recommenders.py` computes Catalog Coverage and Intra-List Diversity @10 for `metadata` and `tfidf` (`embedding` is excluded from this script, since it has no precomputed rows in `game_recommendations` to iterate over, being served live from `game_embeddings` instead).
- MLflow experiment: `recommender/content_based` (run name `<model_id>_eval_coverage_ild`), one run per model, same experiment as the precompute step above.
- Can write `backend/evaluation/results/recommenders_coverage_ild_latest.json`, but hasn't been run since that capability was added; no committed file exists yet. See [docs/ml/evaluation.md](../evaluation.md).
- Full catalog coverage confirmed live: `metadata` and `tfidf` both have precomputed rows for 28,207 to 28,208 of 28,208 games.

## Known limitations

- No ranking-quality evaluation exists for any of the three (Coverage/ILD measure diversity and catalog reach, not whether the recommendations are actually *good*).
- No evaluation coverage exists for `embedding` specifically, since it's served live rather than from stored rows (see Evaluation above).
