# cf_als: Alternating Least Squares

**Model ID:** `cf_als` · **Category:** Collaborative Filtering · **Status:** Implemented, served

## Data

- Source: the `ratings` table (Postgres), read directly via `pd.read_sql("SELECT user_id AS user, game_id AS item, rating FROM ratings", ...)` in `scripts/precompute_cf_recommendations.py`, filtered to games present in `games`. `ratings` was itself loaded once from `data/processed/master_ratings.csv` by `ingest_master.py`.
- Fields used: `user`, `item` (BGG ID), `rating`.
- Real scale: 26.2M ratings, 555,432 distinct users, 27,825 distinct rated games.
- Ratings are converted to Hu/Koren/Volinsky (2008) confidence weights before fitting. `implicit`'s ALS is built for confidence-weighted implicit signals, not explicit 1-10 preference values fed straight through (see Model / Architecture).

## Model / Architecture

`implicit.als.AlternatingLeastSquares` (`backend/app/recommenders/collaborative/als.py`, `ALSRecommender`) fit on a sparse user-item confidence matrix, not a raw-rating matrix. Each rating is converted via `confidence = 1.0 + CF_ALS_CONFIDENCE_ALPHA * rating` (Hu, Koren & Volinsky, 2008, "Collaborative Filtering for Implicit Feedback Datasets") before being placed in the matrix `implicit.als.AlternatingLeastSquares.fit()` consumes. `implicit`'s ALS has no concept of a negative observation on its own, so feeding it a raw 1-10 rating directly would read a 2/10 as "low-confidence positive" rather than "confident dislike"; the confidence transform fixes that by making every observed rating a strictly positive confidence weight, scaled by how strong the underlying preference actually was. Recommendations are cosine-similarity nearest neighbors over the resulting item factors.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig` / `RANDOM_SEED`.

| Param | Value |
|---|---|
| `CF_ALS_FACTORS` | 50 |
| `CF_ALS_ITERATIONS` | 15 |
| `CF_ALS_REGULARIZATION` | 0.1 |
| `CF_ALS_CONFIDENCE_ALPHA` (confidence = `1.0 + alpha * rating`) | 40, the Hu/Koren/Volinsky paper's own default, not tuned against this dataset specifically |
| `RANDOM_SEED` (→ `AlternatingLeastSquares(random_state=...)`) | 42 |

## Training

Real `fit()` step: `implicit`'s ALS solver, 15 iterations. Measured on the real 26.2M-rating/555K-user dataset: the fit itself took about 77 seconds (15 iterations at roughly 5.19s/it).

- Script: `scripts/precompute_cf_recommendations.py` (fits fresh each run alongside `cf_item_cosine`), writes top-10 rows per game to `game_recommendations`.
- Command: `uv run --project backend python scripts/precompute_cf_recommendations.py`
- MLflow experiment: `recommender/collaborative` (run name `cf_als_precompute`), logging `factors`, `iterations`, `regularization`, `confidence_alpha`, `n_ratings`, `n_valid_games`, and result metrics. Same experiment as `cf_item_cosine` so both are directly comparable as runs.

## Artifact

None persisted to disk. Same reasoning as `cf_item_cosine`: the fit is cheap enough to redo each run, so only the output rows in `game_recommendations` matter downstream. MLflow retains the run's parameters and metrics for history.

## Evaluation

- Script: `backend/evaluation/cf_split.py`, Precision@10/Recall@10/NDCG@10, seed 42, 1,000 sampled users.
- MLflow experiment: `recommender/collaborative` (run name `cf_als_eval_cf_split`).
- Can write `backend/evaluation/results/cf_split_cf_als_latest.json` and a coverage/ILD diagnostic to `backend/evaluation/results/recommenders_coverage_ild_latest.json`, but hasn't been run since that capability was added; no committed file exists yet. See [docs/ml/evaluation.md](../evaluation.md).

## Known limitations

- `CF_ALS_CONFIDENCE_ALPHA = 40` is the Hu/Koren/Volinsky paper's own default, not empirically tuned against this dataset.
- Full catalog coverage confirmed live: 27,825 of 27,825 rated games have precomputed rows (278,250 total rows, the full 10 recs per game, no sparsity threshold on this model, unlike `cf_item_cosine`'s `min_shared_users`).
- No re-fit trigger tied to new ratings arriving; it's a manual, whole-catalog rerun.
