# cf_item_cosine: Item-Item Cosine Similarity

**Model ID:** `cf_item_cosine` · **Category:** Collaborative Filtering · **Status:** Implemented, served

## Data

- Source: the `ratings` table (Postgres), read directly via `pd.read_sql("SELECT user_id AS user, game_id AS item, rating FROM ratings", ...)` in `scripts/precompute_cf_recommendations.py`, filtered to games present in `games`. `ratings` was itself loaded once from `data/processed/master_ratings.csv` by `ingest_master.py`.
- Fields used: `user`, `item` (BGG ID), `rating`.
- Real scale: 26.2M ratings, 555,432 distinct users, 27,825 distinct rated games.
- No fixed train/test split for the serving path; fit on the full ratings table. A held-out split exists only for evaluation (see below).

## Model / Architecture

Co-occurrence-masked adjusted, mean-centered cosine similarity (`backend/app/recommenders/collaborative/item_cosine.py`, `ItemCosineRecommender`, one of the two real `BaseRecommender` subclasses), the Sarwar/Karypis/Konstan/Riedl (2001) "Item-Based Collaborative Filtering Recommendation Algorithms" correction over raw cosine. Before building the similarity matrix, each user's ratings are mean-centered (`user_means = df.groupby('user')['rating'].transform('mean')`, `centered_ratings = df['rating'] - user_means`), so a user who rates everything 8-10 doesn't look "similar" to every other item that user happened to rate just because raw cosine can't tell generosity apart from genuine taste. Only actually-rated entries are centered, so the matrix stays sparse; an unrated item is never turned into an implicit zero. `sklearn.metrics.pairwise.cosine_similarity` then runs on the item-item transpose of this centered matrix, and any pair sharing fewer than `min_shared_users` raters is zeroed out, which keeps the similarity from being dominated by pairs of items rated by only one or two overlapping users.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig`.

| Param | Value |
|---|---|
| `CF_ITEM_COSINE_MIN_SHARED_USERS` | 50 |

No random seed needed; the fit is fully deterministic (no sampling, no iterative optimization).

## Training

Not gradient training; a single deterministic `fit()` pass computing the masked similarity matrix in memory.

- Script: `scripts/precompute_cf_recommendations.py` (fits fresh each run alongside `cf_als`, writes top-10 rows per game to `game_recommendations`).
- Command: `uv run --project backend python scripts/precompute_cf_recommendations.py`
- MLflow experiment: `recommender/collaborative` (run name `cf_item_cosine_precompute`), logging `min_shared_users`, `n_ratings`, `n_valid_games`, and `games_processed`/`recommendations_written` metrics. Grouped with `cf_als` in the same experiment, not two separate ones, which is what makes them directly comparable in the MLflow UI's run-comparison table.

## Artifact

None persisted to disk. The fitted similarity matrix lives only in memory for the duration of the script; only its output, the top-10 recommendation rows, is written to Postgres. MLflow records the run's parameters and metrics for history, but there's no model file to version, since the whole fit is cheap enough to redo.

## Evaluation

- Script: `backend/evaluation/cf_split.py`, per-user 80/20 split (1,000 sampled active users, seed 42), Precision@10/Recall@10/NDCG@10 against held-out "liked" items (rating ≥ 8.0).
- MLflow experiment: `recommender/collaborative` (run name `cf_item_cosine_eval_cf_split`).
- Can write `backend/evaluation/results/cf_split_cf_item_cosine_latest.json` and a coverage/ILD diagnostic via `backend/evaluation/evaluate_recommenders.py`, but hasn't been run since that capability was added; no committed file exists yet. See [docs/ml/evaluation.md](../evaluation.md).

## Known limitations

- Full catalog coverage confirmed live: 27,825 of 27,825 rated games have precomputed rows.
- No re-fit trigger tied to new ratings arriving; it's a manual, whole-catalog rerun.
