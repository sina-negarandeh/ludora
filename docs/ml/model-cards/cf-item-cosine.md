# cf_item_cosine — Item-Item Cosine Similarity

**Model ID:** `cf_item_cosine` · **Category:** Collaborative Filtering · **Status:** Implemented, served

## Data

- Source: `data/raw/user_ratings.csv` (jvanelteren dataset), filtered to games present in `games`.
- Fields used: `user`, `item` (BGG ID), `rating`.
- No fixed train/test split for the *serving* path — fit on the full ratings table. A held-out split exists only for evaluation (see below).

## Model / Architecture

Co-occurrence-masked item-item cosine similarity (`backend/app/recommenders/collaborative/item_cosine.py`, `ItemCosineRecommender`, one of the three real `BaseRecommender` subclasses). Builds a sparse user-item ratings matrix, computes `sklearn.metrics.pairwise.cosine_similarity` on the item-item transpose, then zeroes out any pair sharing fewer than `min_shared_users` raters — this is what keeps the similarity from being dominated by pairs of items rated by only one or two overlapping users.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig`.

| Param | Value |
|---|---|
| `CF_ITEM_COSINE_MIN_SHARED_USERS` | 50 |

No random seed needed — the fit is fully deterministic (no sampling, no iterative optimization).

## Training

Not gradient training — a single deterministic `fit()` pass computing the masked similarity matrix in memory.

- Script: `scripts/precompute_cf_recommendations.py` (fits fresh each run alongside `cf_svd` and `cf_als`, writes top-10 rows per game to `game_recommendations`).
- Command: `uv run --project backend python scripts/precompute_cf_recommendations.py`
- MLflow experiment: `recommender/collaborative` (run name `cf_item_cosine_precompute`) — logs `min_shared_users`, `n_ratings`, `n_valid_games`, and `games_processed`/`recommendations_written` metrics. Grouped with `cf_svd`/`cf_als` as runs in the *same* experiment, not three separate experiments — that's what makes them directly comparable in the MLflow UI's run-comparison table.

## Artifact

None persisted to disk — the fitted similarity matrix lives only in memory for the duration of the script; only its *output* (top-10 recommendation rows) is written to Postgres. MLflow records the run's parameters and metrics for history, but there's no model file to version (nothing here needs to be reloaded later — the whole fit is cheap enough to redo).

## Evaluation

- Script: `backend/evaluation/cf_split.py` — per-user 80/20 split (1,000 sampled active users, seed 42), Precision@10 / Recall@10 / NDCG@10 against held-out "liked" items (rating ≥ 8.0).
- MLflow experiment: `recommender/collaborative` (run name `cf_item_cosine_eval_cf_split`).
- Results file: `backend/evaluation/results/cf_split_cf_item_cosine_latest.json`.
- A second, coarser diagnostic (Catalog Coverage, Intra-List Diversity @10) runs via `backend/evaluation/evaluate_recommenders.py` → `backend/evaluation/results/recommenders_coverage_ild_latest.json`.

## Known limitations

- `scripts/precompute_cf_recommendations.py` and `scripts/train_svd.py`/`precompute_svd_recommendations.py` both write `cf_svd` rows independently — a duplicate pipeline noted but not consolidated in this pass (see `docs/ml/recommenders.md`). Doesn't affect `cf_item_cosine` directly, but the same script that fits this model also re-derives `cf_svd`.
- No re-fit trigger tied to new ratings arriving — this is a manual, whole-catalog rerun.
