# Search

**Status: Implemented.** All three modes are live, request-time code paths; nothing here is precomputed or cached.

## Problem

Let a user find a specific game by name, or describe what they want in natural language ("a tense sci-fi trading game") and get relevant results even when no keyword matches.

## Inputs and outputs

Input: a query string `q`, a `mode` (`lexical` | `semantic` | `hybrid`), and the same filter set used by browsing (categories, themes, mechanics, player count, weight, playtime, year). Output: a paginated, ranked list of games.

## Approach

### Query normalization

Every user-typed query is folded through `normalize_query()` (`backend/app/core/query_text.py`) before anything is done with it: collapse whitespace runs, `casefold`. It is applied where a query *enters*, not by each retrieval leg, so no caller has to remember:

- `/api/search/` folds on the contract. `SearchQuery.q` carries an `AfterValidator`, so the route, the assistant orchestrator, the entity resolver and the evaluation harness are all covered by construction.
- `/api/games/?query=` folds inside `GameService.get_games`, which is that path's only entry point since it has no request model to hang a validator on.

The retrieval legs (`search_lexical`, `search_semantic`) therefore do no folding and hold no policy: they take a query and retrieve. `EntityResolver.resolve_game` uses the same fold to decide whether a hit is an exact title match, so the lookup has one notion of equality rather than two.

For the lexical leg the fold changes nothing, since `websearch_to_tsquery` already lowercases while building its lexemes and tokenizes away whitespace. For semantic it matters, because the embedding model does neither: before this existed, "catan" and "Catan" retrieved different neighbourhoods, and hybrid inherited the difference through the RRF union. Measured against the live catalog, hybrid returned 149 matches topped by "Catan: Big Box" for the first and 120 topped by "Catan Card Game" for the second.

For the browse path the whitespace fold is what matters. That query string goes straight into a `LIKE` pattern, so an untrimmed `"catan "` required a literal space after the name: measured against the live catalog, 46 matches became 14.

Both were reachable from an ordinary keyboard rather than a contrived one. iOS capitalizes the first letter of a search field by default and inserts a trailing space when a keyboard suggestion is accepted, so the phone and the web returned different games for the same keystrokes.

`casefold` rather than `lower`, because this is a case-insensitive comparison and not a display transform: `lower` leaves the German sharp s alone, so "Straße" and "STRASSE" stay distinct strings and encode to distinct vectors. BGG's catalog carries many German titles. Whitespace runs are collapsed rather than only trimmed, because an internal double space splits a query for the encoder exactly the way a leading one does.

**A blank query retrieves nothing, in every mode.** Normalization reduces `"   "` to `""`, and an empty string is a perfectly good input to an embedding model whose nearest neighbours are arbitrary games: a blank search field used to answer with 100 confident-looking results in semantic and hybrid while lexical answered with none. `SearchService.search()` now returns an empty page for an empty query, so the three modes agree and nothing reaches the encoder or the database.

That check sits in `search()` rather than in the legs because it is the only layer that can see whether filters were supplied. A request with filters and no text is a *browse*, not a search, and `AssistantOrchestrator._handle_search` routes exactly that case to `_handle_browse` — the LLM classifies "strategy games for four players" as a search often enough that guarding any lower would have answered it with nothing at all.

This fold is the identity on every query in `backend/evaluation/search_queries.json` (all five are already lowercase, single-spaced ASCII), so the committed baseline in `backend/evaluation/results/` was measured under exactly the condition it now guarantees. That also means those five queries cannot detect a case regression, which is why `evaluate_search.py` reports case invariance separately: it re-runs each query uppercased, title-cased and padded, and checks the top-10 comes back identical. It writes to its own results file so the three quality baselines stay comparable.

Documents keep their natural case: `scripts/update_embeddings.py` does not fold. So the query is slightly out of step with the corpus, which is worth knowing but is not new. That asymmetry already applied to every lowercase query anyone typed, the five evaluation queries included. Folding makes it uniform instead of dependent on whether the caller happened to hold shift. Pinned by `backend/tests/test_search_query_normalization.py`.

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
