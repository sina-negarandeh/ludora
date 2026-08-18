# cf_als — Alternating Least Squares

**Model ID:** `cf_als` · **Category:** Collaborative Filtering · **Status:** Implemented, served

## Data

- Source: `data/raw/user_ratings.csv`, filtered to games present in `games`.
- Fields used: `user`, `item` (BGG ID), `rating`. Treated as implicit-feedback strength (the `implicit` library's ALS was built for confidence-weighted implicit signals, not explicit 1–10 ratings — see Known limitations).

## Model / Architecture

`implicit.als.AlternatingLeastSquares` (`backend/app/recommenders/collaborative/als.py`, `ALSRecommender`) fit on a sparse user-item matrix. Recommendations are cosine-similarity nearest neighbors over the resulting item factors.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig` / `RANDOM_SEED`.

| Param | Value |
|---|---|
| `CF_ALS_FACTORS` | 50 |
| `CF_ALS_ITERATIONS` | 15 |
| `CF_ALS_REGULARIZATION` | 0.1 |
| `RANDOM_SEED` (→ `AlternatingLeastSquares(random_state=...)`) | 42 |

## Training

Real `fit()` step: `implicit`'s ALS solver, 15 iterations.

- Script: `scripts/precompute_cf_recommendations.py` (fits fresh each run alongside `cf_item_cosine` and a duplicate `cf_svd` — see that model's card), writes top-10 rows per game to `game_recommendations`.
- Command: `uv run --project backend python scripts/precompute_cf_recommendations.py`
- MLflow experiment: `recommender/collaborative` (run name `cf_als_precompute`) — logs `factors`, `iterations`, `regularization`, `n_ratings`, `n_valid_games`, and result metrics. Same experiment as `cf_item_cosine`/`cf_svd` so all three are directly comparable as runs.

## Artifact

None persisted to disk. Same reasoning as `cf_item_cosine` — the fit is cheap enough to redo each run; only the output rows in `game_recommendations` matter downstream. MLflow retains the run's parameters/metrics for history.

## Evaluation

- Script: `backend/evaluation/cf_split.py` — Precision@10 / Recall@10 / NDCG@10, seed 42, 1,000 sampled users.
- MLflow experiment: `recommender/collaborative` (run name `cf_als_eval_cf_split`).
- Results file: `backend/evaluation/results/cf_split_cf_als_latest.json`.
- Coverage/ILD diagnostic: `backend/evaluation/results/recommenders_coverage_ild_latest.json`.

## Known limitations

- ALS is designed for implicit feedback (confidence weights derived from interaction counts), but this pipeline feeds it explicit 1–10 star ratings directly as the confidence signal — a reasonable practical shortcut, not a textbook-correct use of the algorithm.
- No re-fit trigger tied to new ratings arriving — manual, whole-catalog rerun.
