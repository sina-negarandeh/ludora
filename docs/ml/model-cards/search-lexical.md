# Lexical search — Postgres full-text

**Category:** Search (one leg of hybrid search) · **Status:** Implemented, served live

## Data

- Source: `games.search_vector` (a Postgres `TSVECTOR` column), built from `name` (weight A), `themes`/`mechanics`/`categories`/`subdomains`/`families` (weight B — every structured taxonomy tag, one tier), `description` (weight C), `designers`/`artists`/`publishers` (weight D).
- Build script: `scripts/update_search_vectors.py` — a manual batch `UPDATE`, not a trigger; must be rerun whenever tagged entities change.
- **`subdomains`/`families` were missing from this tsvector entirely until this pass** — both exist and are used everywhere else (filters, the embedding document), but a query for a subdomain name (e.g. "party game") or a family name previously matched nothing on that basis, only incidentally via other fields.
- **Text search config is `english_unaccent`, not Postgres's plain `english`** (migration `c4d8f21a9e56` — `CREATE EXTENSION unaccent` + a custom config copying `english` but running `unaccent` before stemming). Plain `english` does not fold diacritics: querying "Chvatil" against a tsvector built from "Chvátil" returned **zero** rows, since the two accent forms tokenize to different lexemes. Measured against the live catalog: ~9% of designers, ~10% of artists, 5% of publishers have non-ASCII names — a substantial, silent failure mode for the exact query class (designer/artist/publisher name search) this leg is most relied on for. Both the tsvector build (`to_tsvector`) and the live query (`websearch_to_tsquery` in `SearchService.search_lexical()`) must use the same config, or accent-insensitive matching silently doesn't take effect.

## Model / Architecture

Not a trained model — Postgres's built-in `websearch_to_tsquery` + `ts_rank_cd` ranking (`SearchService.search_lexical()`, `backend/app/services/search_service.py`). Natural-language-ish query parsing (handles quoted phrases, `-exclusion`, `OR`) is native to Postgres, not custom code.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::SearchConfig`.

| Param | Value |
|---|---|
| `CANDIDATE_POOL_SIZE` (per-leg retrieval limit before RRF fusion) | 100 |

No random seed needed — fully deterministic ranking.

## Training

None — this is a live database query, not a fit/train step. `search_vector` itself is populated by `scripts/update_search_vectors.py`, a deterministic SQL `UPDATE`, not a learned model.

## Artifact

None — nothing is trained; `search_vector` is a derived database column, versioned only by its own `UPDATE` timestamp (not currently tracked).

## Evaluation

- Script: `backend/evaluation/evaluate_search.py` — MRR@10, NDCG@10, Recall@100 against 5 hand-written queries (`backend/evaluation/search_queries.json`) with manually curated expected BGG IDs.
- MLflow experiment: `search/retrieval_eval` (run name `lexical`) — shared with the semantic/hybrid legs below, since all three modes are evaluated by the same script and are directly comparable retrieval strategies over the same query set.
- Results file: `backend/evaluation/results/search_lexical_latest.json`.

## Known limitations

- Only 5 evaluation queries — not statistically meaningful, a smoke-level sanity check rather than a real benchmark.
- No relevance-judgment methodology documented for how the 5 queries' expected BGG IDs were chosen (manual curation, not a labeled dataset).
- **Discursive, multi-word natural-language queries are inherently a weak fit for this leg**, not a bug to be tuned away: `websearch_to_tsquery` ANDs every bare word together, so a query like "heavy strategy game about trains" only matches documents containing *all four* stems — measured at 7 games out of 28,208 for that exact query. Worse, English stemming collapses unrelated word senses (e.g. "train" the vehicle and "train" the verb, "to train an employee," share a stem), which can surface confident-looking but irrelevant matches. This is exactly the query class hybrid mode's semantic leg is meant to cover instead (see [search-semantic.md](search-semantic.md)) — not something reachable by retuning weights or ranking here, since weight/rank changes only reorder documents that already satisfy the AND, they don't change which documents do.
- Tried `ts_rank_cd`'s length-normalization option (divide by 1 + log(document length)) to discount long, description-heavy incidental matches — measured it against a real query and reverted it: normalization applies across the *whole* combined tsvector, not per-field, so it penalized a legitimately relevant long document (a game whose own name was the query) exactly as much as an irrelevant long one, dropping an exact-name match out of the top 5 in favor of a much weaker, shorter-description match.
- **Weight D conflates designers, artists, and publishers into one undifferentiated field** — a search for a designer's name can match a game where that person only did the art, or only the publisher. Confirmed with a real query: searching "Gavan Brown" (Brass: Birmingham's designer) also surfaces the "Dice Throne" series, where he's credited as artist, not designer — a real match, just the wrong role, and there's currently no structured way to search by role at all. Weight/rank tuning can't fix this (it only reorders documents that already match, it doesn't add role awareness). Planned fix: a reranking stage — see [docs/roadmap.md](../../roadmap.md#planned-but-unimplemented).
