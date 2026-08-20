# Search

**Status: Implemented.** All three modes are live, request-time code paths; nothing here is precomputed or cached.

## Problem

Let a user find a specific game by name, or describe what they want in natural language ("a tense sci-fi trading game") and get relevant results even when no keyword matches.

## Inputs and outputs

Input: a query string `q`, a `mode` (`lexical` | `semantic` | `hybrid`), and the same filter set used by browsing (categories, themes, mechanics, player count, weight, playtime, year). Output: a paginated, ranked list of games.

## Approach

### Lexical search

`SearchService.search_lexical()` (`backend/app/services/search_service.py`) uses Postgres full-text search: `func.websearch_to_tsquery('english_unaccent', q)` matched against `Game.search_vector` via the `@@` operator, ranked with `ts_rank_cd`. `english_unaccent` (migration `c4d8f21a9e56`) is a custom text search config, not Postgres's plain `english`. Plain `english` doesn't fold diacritics, so "Chvatil" against a tsvector built from "Chvátil" matched nothing at all; about 9-10% of designers and artists have non-ASCII names, making this a substantial real-world failure mode, not an edge case. `search_vector` is a weighted tsvector (name = A, themes+mechanics+categories+subdomains+families = B, description = C, designers+artists+publishers = D), built by a standalone script, `scripts/update_search_vectors.py`, not a DB trigger and not an ORM event listener. There's no GIN index on the column, so this is an out-of-band, must-remember-to-rerun batch job rather than something that stays in sync automatically.

### Semantic search

`search_semantic()` embeds the query at request time via `backend/app/core/embeddings.py` (`Qwen3-Embedding-0.6B`, 4-bit DWQ, served locally through `mlx-embeddings` on Apple MLX), applying `SearchConfig.QUERY_INSTRUCTION`'s asymmetric instruction prefix, since the query side, unlike the document side, is instruction-aware. It then orders by pgvector's `cosine_distance` against `GameEmbedding.embedding`, filtered to `GameEmbedding.model == SearchConfig.EMBEDDING_MODEL`. Vectors live in a separate `game_embeddings` table (one row per `(game_id, model)`, unique-constrained) rather than a column on `games`, which is what lets more than one embedding model's vectors coexist for comparison instead of a newer model silently overwriting the only copy. Like the lexical path, there's no ANN index (no ivfflat or hnsw); this is an exact brute-force nearest-neighbor scan over every row for the active model. Embeddings are populated offline by `scripts/update_embeddings.py`, encoding a structured document of name, description (truncated to 1,500 characters), themes, mechanics, categories, subdomains, families, and bucketed weight/playtime phrases (for example "heavy strategy game", "30 to 60 minute game", see `SearchConfig.WEIGHT_BUCKETS`/`PLAYTIME_BUCKETS`). Designers, artists, and publishers are deliberately excluded, since lexical search already covers proper-noun matches at `search_vector`'s D-tier.

### Hybrid search (Reciprocal Rank Fusion)

`search()` retrieves up to 100 candidates from each of the lexical and semantic paths, then fuses ranks with RRF, `k = 60`:

```python
l_score = 1.0 / (self.rrf_k + l_rank) if l_rank else 0.0
s_score = 1.0 / (self.rrf_k + s_rank) if s_rank else 0.0
rrf_score = l_score + s_score
```

Filters (`apply_game_filters()`) are applied after the fused candidate set is scored, then the result is sorted by `rrf_score` and paginated by default. Filtering isn't pushed into the retrieval SQL for either underlying path.

### Optional field sort, with a relevance floor

`SearchQuery.sort` (a `SortSpec`: `field`, rank/rating/year/complexity/name/playtime, plus `direction`) overrides the default relevance ordering, for a request like "find games with Spiderman in it, sorted by rating," a free-text match that also wants a specific ordering criterion, not just relevance rank. When set, sorting is **not** applied across the whole ~100-candidate pool: it's restricted to the top `SearchConfig.SORT_RELEVANCE_POOL_SIZE` (25) candidates by RRF score first, and only that slice is re-sorted by the requested field.

This floor exists because of a measured failure mode, not a hypothetical one: sorting the full 100-candidate pool for the query above by rating surfaced "Slay the Spire: The Board Game" (RRF relevance rank #44 out of ~100, barely related to the query at all) ahead of games with a real, strong textual/semantic connection to "Spiderman," purely because it happened to have a high rating. A marginal match shouldn't be able to outrank a strong one just by scoring well on the sort field. Restricting the floor to the top 25 keeps enough headroom to answer "top 3 by rating" meaningfully while still requiring every candidate to have cleared a real relevance bar first.

This is the primary way the AI assistant expresses "find X, sorted/limited by Y" (`_handle_search` in `AssistantOrchestrator`); see [docs/ml/assistant.md](assistant.md).

### Filters

`apply_game_filters()` supports `exact_players`, `min_players`/`max_players`, `min_weight`/`max_weight`, `min_playtime`/`max_playtime`, `min_year`/`max_year`, `categories`, `subdomains`, `themes`, `families`, `mechanics`, `designers`, `artists`, and `publishers`. Both search and the plain browse route (`GET /api/games`) filter identically now; `min_year`/`max_year` used to work only through search, but browse filters on year too.

## Serving architecture

Both embedding and lexical scoring happen inside the FastAPI request. There's no separate search index (Elasticsearch, OpenSearch, or similar), no cache layer, and no async or background scoring. Latency is whatever Postgres plus one GPU-accelerated MLX `embeddings.encode()` call costs per request.

## Evaluation

`backend/evaluation/evaluate_search.py` implements MRR@10, NDCG@10 (binary relevance), and Recall@100 against a 5-query hand-written test set (`backend/evaluation/search_queries.json`). Results are logged to MLflow and written to `backend/evaluation/results/search_{mode}_latest.json`, committed for all three modes. See [docs/ml/evaluation.md](evaluation.md) for the actual numbers and what is and isn't measured elsewhere.

## Failure modes and limitations

- No ANN index on either the tsvector or `game_embeddings.embedding`. Both paths do a full sequential scan, which won't scale past the current catalog size without an index.
- `search_vector` requires a manual script re-run to reflect new or changed games; there's no trigger keeping it current.
- The 5-query evaluation set is far too small to be statistically meaningful, though the results it does produce are at least committed and reproducible now.
- Semantic search excludes designer, artist, and publisher text from the embedding by design, so a query like "a game by [designer name]" won't match semantically. Lexical search still catches exact-name matches via the weighted D-tier.

## Related code

- `backend/app/services/search_service.py`
- `backend/app/schemas/game_query.py` (`GameFilter`)
- `scripts/update_embeddings.py`, `scripts/update_search_vectors.py`
- `backend/evaluation/evaluate_search.py`, `backend/evaluation/search_queries.json`
- `frontend/src/pages/GamesList.tsx` (search bar + mode toggle)
