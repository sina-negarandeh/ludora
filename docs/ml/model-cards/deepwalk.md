# deepwalk: Graph DeepWalk Embedding

**Model ID:** `deepwalk` · **Category:** Content-Based Filtering (graph-based) · **Status:** Implemented, served

## Data

- Source: a heterogeneous graph built in-memory from `games` (via ORM): one node per game, plus one node per mechanic, category, subdomain, family, designer, publisher, and artist (node prefixes `G_`/`M_`/`C_`/`SD_`/`SF_`/`D_`/`P_`/`A_` respectively), with an edge from a game to every tag it has. Not persisted to disk; rebuilt fresh each run from live ORM objects.

## Model / Architecture

DeepWalk (Perozzi et al.) via uniform random walks and `gensim.Word2Vec` (`scripts/precompute_graph_recommendations.py::run_deepwalk`). Generates fixed-length random walks from every node, treats each walk as a "sentence," and trains a skip-gram Word2Vec model over them, so games that co-occur in walks, that is, that share tags transitively, end up with similar embeddings. Recommendations are cosine-similarity nearest neighbors in that embedding space.

The model id is `deepwalk`, not `node2vec`, because DeepWalk's uniform random walks are a genuinely different algorithm from node2vec's biased walks (controlled by return/in-out parameters `p`/`q`), and nothing in this pipeline implements the biased-walk variant. Detail: `docs/ml/recommenders.md`.

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

- Script: `scripts/precompute_graph_recommendations.py` (runs `run_jaccard()` first, then `run_deepwalk()`; see [graph-jaccard.md](graph-jaccard.md)).
- Command: `uv run --project backend python scripts/precompute_graph_recommendations.py`
- MLflow experiment: `recommender/graph` (run name `deepwalk_precompute`), logging all walk and embedding hyperparameters, the random seed, graph node and edge counts, and `recommendations_written`. Same experiment as `graph_jaccard` so the two graph-based approaches are directly comparable as runs.
- Random-walk generation is seeded (`random.Random(RANDOM_SEED)`).

## Artifact

None persisted. The Word2Vec model and graph are rebuilt from scratch each run; only the top-10 rows per game are written to `game_recommendations`.

## Evaluation

- Script: `backend/evaluation/evaluate_recommenders.py`, Catalog Coverage plus Intra-List Diversity @10.
- MLflow experiment: `recommender/graph` (run name `deepwalk_eval_coverage_ild`).
- Can write `backend/evaluation/results/recommenders_coverage_ild_latest.json`, but hasn't been run since that capability was added; no committed file exists yet. See [docs/ml/evaluation.md](../evaluation.md).
- No ranking-quality (Precision/Recall/NDCG) evaluation exists; there are no held-out relevance labels to evaluate against.

## Known limitations

- 1 training epoch is very light for Word2Vec (its own default is 5), chosen for speed over the full catalog, not tuned against a quality metric. A legitimate future improvement, not yet changed in code.
- `data/processed/node2vec_graph.gpickle` (13.2 MB), a leftover artifact from an earlier, abandoned node2vec-package attempt, is still present on disk pending a decision on whether to delete it.
- Full catalog coverage confirmed live: 28,208 of 28,208 games have precomputed rows.
