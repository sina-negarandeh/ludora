# graph_jaccard — Weighted Multi-Relation Jaccard

**Model ID:** `graph_jaccard` · **Category:** Content-Based Filtering (graph-based) · **Status:** Implemented, served

## Data

- Source: `games` table (via ORM) — mechanics, categories, designers, publishers, artists, one-hot encoded per game via `MultiLabelBinarizer`.

## Model / Architecture

Weighted, multi-relation Jaccard similarity (`scripts/precompute_graph_recommendations.py::run_jaccard`). Computes Jaccard similarity separately for each relation (mechanics, categories, designers, publishers, artists), then combines them into one weighted score — two games sharing many mechanics count for more than two sharing one obscure artist.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig`.

| Param | Value |
|---|---|
| `GRAPH_JACCARD_WEIGHTS` | `{mechanics: 0.4, categories: 0.3, designers: 0.05, publishers: 0.025, artists: 0.025}` (renormalized to sum to 1.0) |
| `RECS_PER_MODEL_LIMIT` | 10 |

No random seed needed — fully deterministic.

## Training

Not gradient training — deterministic set-similarity computation, batched (200 games per batch).

- Script: `scripts/precompute_graph_recommendations.py` (runs `run_jaccard()` before `run_deepwalk()` — see [deepwalk.md](deepwalk.md)).
- Command: `uv run --project backend python scripts/precompute_graph_recommendations.py`
- MLflow experiment: `recommender/graph` (run name `graph_jaccard_precompute`) — logs the five relation weights, `n_games`, `recs_per_model_limit`, and `recommendations_written`. Same experiment as `deepwalk` so the two graph-based approaches are directly comparable as runs.

## Artifact

None persisted — the binarized relation matrices are rebuilt from scratch each run; only the top-10 rows per game are written to `game_recommendations`.

## Evaluation

- Script: `backend/evaluation/evaluate_recommenders.py` — Catalog Coverage + Intra-List Diversity @10.
- MLflow experiment: `recommender/graph` (run name `graph_jaccard_eval_coverage_ild`).
- Results file: `backend/evaluation/results/recommenders_coverage_ild_latest.json`.
- No ranking-quality (Precision/Recall/NDCG) evaluation exists — no held-out relevance labels to evaluate against.

## Known limitations

- Weights (0.4/0.3/0.05/0.025/0.025) were hand-chosen, not tuned against any evaluation signal.
