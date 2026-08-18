# graph_jaccard — Weighted Multi-Relation Jaccard

**Model ID:** `graph_jaccard` · **Category:** Content-Based Filtering (graph-based) · **Status:** Implemented, served

## Data

- Source: `games` table (via ORM) — mechanics, categories, subdomains, families, designers, publishers, artists, one-hot encoded per game via `MultiLabelBinarizer`. `subdomains` and `families` were just added to the relation set (previously 5 relations, now 7). Deliberately **not** `themes`: BGG's `Theme:` namespace is already one of `families`'s 72 namespaces (`scripts/build_master_dataset.py:302-304`), so adding both would double-count the same tags.

## Model / Architecture

Weighted, multi-relation Jaccard similarity (`scripts/precompute_graph_recommendations.py::run_jaccard`). Computes Jaccard similarity separately for each relation (mechanics, categories, subdomains, families, designers, publishers, artists), then combines them into one weighted score — two games sharing many mechanics count for more than two sharing one obscure artist.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig`.

| Param | Value |
|---|---|
| `GRAPH_JACCARD_WEIGHTS` | `{mechanics: 0.35, categories: 0.25, subdomains: 0.15, families: 0.1, designers: 0.05, publishers: 0.025, artists: 0.025}` (renormalized to sum to 1.0 at use time — doesn't need to sum to 1 in the config itself) |
| `RECS_PER_MODEL_LIMIT` | 10 |

No random seed needed — fully deterministic.

## Training

Not gradient training — deterministic set-similarity computation, batched (200 games per batch).

- Script: `scripts/precompute_graph_recommendations.py` (runs `run_jaccard()` before `run_deepwalk()` — see [deepwalk.md](deepwalk.md)).
- Command: `uv run --project backend python scripts/precompute_graph_recommendations.py`
- MLflow experiment: `recommender/graph` (run name `graph_jaccard_precompute`) — logs the seven relation weights, `n_games`, `recs_per_model_limit`, and `recommendations_written`. Same experiment as `deepwalk` so the two graph-based approaches are directly comparable as runs.

## Artifact

None persisted — the binarized relation matrices are rebuilt from scratch each run; only the top-10 rows per game are written to `game_recommendations`.

## Evaluation

- Script: `backend/evaluation/evaluate_recommenders.py` — Catalog Coverage + Intra-List Diversity @10.
- MLflow experiment: `recommender/graph` (run name `graph_jaccard_eval_coverage_ild`).
- Results file: `backend/evaluation/results/recommenders_coverage_ild_latest.json`.
- No ranking-quality (Precision/Recall/NDCG) evaluation exists — no held-out relevance labels to evaluate against.

## Known limitations

- Weights (0.35/0.25/0.15/0.1/0.05/0.025/0.025) were hand-chosen, not tuned against any evaluation signal.
- Full catalog coverage confirmed live: 28,205/28,208 games have precomputed rows.
