# deepwalk — Graph DeepWalk Embedding

**Model ID:** `deepwalk` · **Category:** Content-Based Filtering (graph-based) · **Status:** Implemented, served

## Data

- Source: a heterogeneous graph built in-memory from `games` (via ORM) — one node per game, plus one node per mechanic/category/designer/publisher/artist, with an edge from a game to every tag it has. Not persisted to disk; rebuilt fresh each run from live ORM objects.

## Model / Architecture

DeepWalk (Perozzi et al.) via uniform random walks + `gensim.Word2Vec` (`scripts/precompute_graph_recommendations.py::run_deepwalk`). Generates fixed-length random walks from every node, treats each walk as a "sentence," and trains a skip-gram Word2Vec model over them — games that co-occur in walks (i.e. that share tags, transitively) end up with similar embeddings. Recommendations are cosine-similarity nearest neighbors in that embedding space.

**Naming history**: this model id used to be `node2vec`, which was inaccurate — DeepWalk's *uniform* random walks are a different algorithm from node2vec's *biased* walks (controlled by return/in-out parameters `p`/`q`). A separate, genuine node2vec-package attempt (`scripts/build_node2vec_graph.py` + `train_node2vec.py`) was scaffolded but never completed and has been removed from the repo; the served model's id was renamed to `deepwalk` to match what it actually is. Detail: `docs/ml/recommenders.md`.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::RecommenderConfig` / `RANDOM_SEED`.

| Param | Value |
|---|---|
| `DEEPWALK_NUM_WALKS` | 10 |
| `DEEPWALK_WALK_LENGTH` | 10 |
| `DEEPWALK_VECTOR_SIZE` | 64 |
| `DEEPWALK_WINDOW` | 5 |
| `DEEPWALK_EPOCHS` | 1 |
| `DEEPWALK_MIN_COUNT` | 1 |
| `RANDOM_SEED` (walk generation + `Word2Vec(seed=...)`) | 42 |

## Training

Real training step: Word2Vec skip-gram over the generated walks (1 epoch).

- Script: `scripts/precompute_graph_recommendations.py` (runs `run_jaccard()` first, then `run_deepwalk()` — see [graph-jaccard.md](graph-jaccard.md)).
- Command: `uv run --project backend python scripts/precompute_graph_recommendations.py`
- MLflow experiment: `recommender/graph` (run name `deepwalk_precompute`) — logs all walk/embedding hyperparameters, the random seed, graph node/edge counts, and `recommendations_written`. Same experiment as `graph_jaccard` so the two graph-based approaches are directly comparable as runs.
- Random-walk generation is seeded (`random.Random(RANDOM_SEED)`) — previously unseeded, fixed as part of this session's reproducibility pass.

## Artifact

None persisted — the Word2Vec model and graph are rebuilt from scratch each run; only the top-10 rows per game are written to `game_recommendations`.

## Evaluation

- Script: `backend/evaluation/evaluate_recommenders.py` — Catalog Coverage + Intra-List Diversity @10.
- MLflow experiment: `recommender/graph` (run name `deepwalk_eval_coverage_ild`).
- Results file: `backend/evaluation/results/recommenders_coverage_ild_latest.json`.
- No ranking-quality (Precision/Recall/NDCG) evaluation exists — no held-out relevance labels to evaluate against.

## Known limitations

- 1 training epoch is very light for Word2Vec — chosen for speed over the full catalog, not tuned against a quality metric.
- `data/processed/node2vec_graph.gpickle` (13.2 MB), a leftover artifact from the removed node2vec-package attempt, is still present on disk pending a decision on whether to delete it.
