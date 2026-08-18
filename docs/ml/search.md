# Search

**Status: Implemented.** All three modes are live, request-time code paths — nothing here is precomputed or cached.

## Problem

Let a user find a specific game by name, or describe what they want in natural language ("a tense sci-fi trading game") and get relevant results even when no keyword matches.

## Inputs and outputs

Input: a query string `q`, a `mode` (`lexical` | `semantic` | `hybrid`), and the same filter set used by browsing (categories, themes, mechanics, player count, weight, year). Output: a paginated, ranked list of games.

## Approach

### Lexical search

`SearchService.search_lexical()` (`backend/app/services/search_service.py`) uses Postgres full-text search: `func.websearch_to_tsquery('english_unaccent', q)` matched against `Game.search_vector` via the `@@` operator, ranked with `ts_rank_cd`. `english_unaccent` (migration `c4d8f21a9e56`) is a custom text search config, not Postgres's plain `english` — plain `english` doesn't fold diacritics, so "Chvatil" against a tsvector built from "Chvátil" matched nothing at all; ~9-10% of designers/artists have non-ASCII names, making this a substantial real-world failure mode, not an edge case. `search_vector` is a **weighted** tsvector (name = A, themes+mechanics+categories+subdomains+families = B, description = C, designers+artists+publishers = D — subdomains/families were added in this pass, previously missing entirely despite being used everywhere else), built by a standalone script, `scripts/update_search_vectors.py` — not a DB trigger, not an ORM event listener, and there is no GIN index on the column, so this is an out-of-band, must-remember-to-rerun batch job rather than something that stays in sync automatically.

### Semantic search

`search_semantic()` embeds the query at request time via `backend/app/core/embeddings.py` (`Qwen3-Embedding-0.6B`, 4-bit DWQ, served locally through `mlx-embeddings` on Apple MLX — replaced `all-MiniLM-L6-v2` in this pass), applying `SearchConfig.QUERY_INSTRUCTION`'s asymmetric instruction prefix since the query side, unlike the document side, is instruction-aware. It then orders by pgvector's `cosine_distance` against `GameEmbedding.embedding`, filtered to `GameEmbedding.model == SearchConfig.EMBEDDING_MODEL`. Vectors live in a separate `game_embeddings` table (one row per `(game_id, model)`, unique-constrained) rather than a column on `games` — this is what lets more than one embedding model's vectors coexist for comparison instead of the newer model silently overwriting the only copy. Like the lexical path, there is no ANN index (no ivfflat/hnsw) — this is an exact brute-force nearest-neighbor scan over every row for the active model. Embeddings are populated offline by `scripts/update_embeddings.py`, encoding a structured document of name + description (truncated to 1,500 characters — a longer truncation was tried and measured to add mostly tail-outlier length with no median-document benefit) + themes + mechanics + categories + subdomains + families + bucketed weight/playtime phrases (e.g. "heavy strategy game", "30 to 60 minute game" — see `SearchConfig.WEIGHT_BUCKETS`/`PLAYTIME_BUCKETS`) — designers/artists/publishers are deliberately excluded, since lexical search already covers proper-noun matches at `search_vector`'s D-tier.

### Hybrid search (Reciprocal Rank Fusion)

`search()` retrieves up to 100 candidates from each of the lexical and semantic paths, then fuses ranks with RRF, `k = 60`:

```python
l_score = 1.0 / (self.rrf_k + l_rank) if l_rank else 0.0
s_score = 1.0 / (self.rrf_k + s_rank) if s_rank else 0.0
rrf_score = l_score + s_score
```

Filters (`apply_game_filters()`) are applied **after** the fused candidate set is scored, then the result is sorted by `rrf_score` and paginated. Filtering is not pushed into the retrieval SQL for either underlying path.

### Filters

`apply_game_filters()` supports: `exact_players`, `min_players`/`max_players`, `min_weight`/`max_weight`, `min_year`/`max_year`, `categories`, `themes`, `mechanics`. **There is no playtime filter anywhere in the code** — not in `SearchService`, not in the `GameFilter` Pydantic schema, not on the `/api/games` route. This directly contradicts the pre-Phase-2 README's claim of filtering "by exact Player Count, Play Time, Complexity Weight, Year, Categories, and Mechanics" — the rewritten README removes the Play Time claim. Also worth noting: `min_year`/`max_year` exist on the search `GameFilter` schema but are **not** exposed as query parameters on the plain browse route (`GET /api/games`) — they only work through search.

## Serving architecture

Both embedding and lexical scoring happen inside the FastAPI request — there is no separate search index (Elasticsearch/OpenSearch/etc.), no cache layer, and no async/background scoring. Latency is whatever Postgres + one GPU-accelerated MLX `embeddings.encode()` call costs per request.

## Evaluation

`backend/evaluation/evaluate_search.py` implements MRR@10, NDCG@10 (binary relevance), and Recall@100 against a 5-query hand-written test set (`backend/evaluation/search_queries.json`). It only prints results — no results file exists anywhere in the repository, so no numeric scores can be reported here. See [docs/ml/evaluation.md](evaluation.md) for what is and isn't measured.

## Failure modes and limitations

- No ANN index on either the tsvector or `game_embeddings.embedding` — both paths do a full sequential scan, which will not scale past the current catalog size without an index.
- `search_vector` requires a manual script re-run to reflect new/changed games; there's no trigger keeping it current.
- 5-query evaluation set is far too small to be statistically meaningful; results were never captured to a file even at that scale.
- Semantic search excludes designer/artist/publisher text from the embedding by design, so a query like "a game by [designer name]" will not match semantically (lexical search still catches exact-name matches via the weighted D-tier).

## Related code

- `backend/app/services/search_service.py`
- `backend/app/schemas/game_query.py` (`GameFilter`)
- `scripts/update_embeddings.py`, `scripts/update_search_vectors.py`
- `backend/evaluation/evaluate_search.py`, `backend/evaluation/search_queries.json`
- `frontend/src/pages/GamesList.tsx` (search bar + mode toggle)
