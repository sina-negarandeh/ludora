# Model cards

One file per model or pipeline component, each following the same structure: Data (source, version, preprocessing), Model / Architecture, Hyperparameters (pointing at the single source of truth, `backend/app/core/ml_config.py`), Training (script, exact command, seed, MLflow experiment), Artifact (where the trained or versioned output lives, or "none" for pretrained/prompted models), Evaluation (metric, script, latest result), Known limitations.

This is the reproducibility layer: given a model card, you should be able to answer what data, what processing, what model, what hyperparameters, how it was trained, how it's evaluated, and where the artifact is, without reading source code. The narrative docs ([search.md](../search.md), [recommenders.md](../recommenders.md), [absa.md](../absa.md), [assistant.md](../assistant.md)) explain why a system is built the way it is; these cards are the exact spec for one model within it.

## Recommenders (9 model IDs)

| Card | Model ID(s) |
|---|---|
| [cf-item-cosine.md](cf-item-cosine.md) | `cf_item_cosine` |
| [cf-als.md](cf-als.md) | `cf_als` |
| [content-based.md](content-based.md) | `metadata`, `tfidf`, `embedding` |
| [graph-jaccard.md](graph-jaccard.md) | `graph_jaccard` |
| [deepwalk.md](deepwalk.md) | `deepwalk` |

`popularity` has no model card; it's a live `ORDER BY rank` query, nothing is computed or trained. `hybrid` also has no card; it's a live, request-time blend of `cf_item_cosine` and `metadata` computed in `RecommendationService.get_recommendations()`, never precomputed or stored. See [docs/ml/recommenders.md](../recommenders.md). There's no `cf_svd` model; it was redundant with `cf_als`, both dense 50-dimensional latent-factor decompositions of the same ratings matrix.

## Search

| Card | Covers |
|---|---|
| [search-lexical.md](search-lexical.md) | Postgres full-text (`tsvector`) retrieval |
| [search-semantic.md](search-semantic.md) | pgvector nearest-neighbor retrieval (also the shared embedding build) |

Hybrid search is RRF fusion of the two at request time, no separate model, documented in `search-semantic.md`.

## Reviews NLP

| Card | Covers |
|---|---|
| [absa-deberta.md](absa-deberta.md) | Aspect-based sentiment extraction |
| [summarization-llm.md](summarization-llm.md) | "Customers say" LLM summarization |

## Assistant

| Card | Covers |
|---|---|
| [assistant-intent-parse.md](assistant-intent-parse.md) | Natural-language → structured intent parsing |
