# Offline data pipeline

Ludora's ML features (search, recommendations, ABSA, summaries) are populated by 27 standalone Python scripts run by hand, in order, against a local Postgres instance. There's no orchestrator: no Airflow, no Prefect, no Makefile, no CI job. This doc reconstructs the actual run order from each script's read/write dependencies, not from filesystem timestamps, which aren't reliable (see the note at the bottom).

For dataset sources and schema, see [docs/data/README.md](../data/README.md). This doc is about *execution order*, not data shape.

> This order is derived from each script's actual read/write dependencies, not a repository-committed runbook. No `Makefile`, `justfile`, or numbered-script convention exists in the repo; treat this as an operational guide, not an authored spec.

## Stage 1: build the master datasets (from raw CSVs, independent of the DB)

| Script | Reads | Writes |
|---|---|---|
| `scripts/build_master_dataset.py` | Both datasets' game-metadata files, outer-merged on BGG ID, plus Dataset 1's `mechanics.csv`/`themes.csv`/`subcategories.csv`/`designers_reduced.csv`/`artists_reduced.csv`/`publishers_reduced.csv` as fallback sources | `data/processed/master_games.csv`, one entity/mapping CSV pair each for subdomains, categories, themes, mechanics, designers, artists, publishers, a `families`/`subfamilies`/`game_subfamilies` trio for the full BGG Family field (72 namespaces, about 4,200 values), and `master_game_relations.csv` |
| `scripts/build_interactions_dataset.py` | Dataset 2's `bgg-26m-reviews.csv`, streamed in 1M-row chunks, deduped on `(user, game_id)` | `data/processed/master_ratings.csv`, `master_reviews.csv`, `master_users.csv` |

Exact dataset provenance and the category/subdomain/theme sourcing logic: [docs/data/README.md](../data/README.md). These two scripts are independent of each other and of the database; both can run any time after the raw CSVs exist.

## Stage 2: load Postgres

| Script | What it does |
|---|---|
| `scripts/ingest_master.py` | `TRUNCATE`s all core tables, then `COPY`s from the Stage-1 CSVs. Projects `master_games.csv` down to a DB-column subset (`master_games_clean.csv`), dedups every mapping CSV (`copy_mapping_dedup()`), and filters `master_ratings.csv`/`master_reviews.csv`/`master_game_relations.csv` to only `game_id`s present in the games table before loading. |

## Stage 3: enrichment (requires `games`/`ratings`/`reviews` already loaded)

| Script | What it does |
|---|---|
| `scripts/populate_subdomain_ranks.py` | Reads `games_detailed_info2025.csv` directly; writes `games.subdomain_ranks` JSON. Treats BGG's `21926` sentinel as "unranked" and drops it. |
| `scripts/populate_rating_distribution.py` | DB-native: `GROUP BY game_id, ROUND(rating*2)/2.0` against the `ratings` table; writes `games.rating_distribution` JSON and `games.num_ratings`. Recomputes from the 26M interaction rows rather than using the unused `data/raw/ratings_distribution.csv`. |
| `scripts/detect_languages.py` | Backfills `reviews.language` and `reviews.language_confidence` (added by two Alembic migrations, so run `uv run alembic upgrade head` first) in batches of 10,000 using the fastText `lid.176.ftz` language-ID model. Stores the detected code regardless of confidence; low-confidence guesses are kept, not discarded, so downstream consumers can threshold on `language_confidence` themselves. Only empty or unparseable comments get `language='unknown'`. |
| `scripts/update_embeddings.py` and `scripts/update_search_vectors.py` | Populate `game_embeddings` (one upserted row per `(game_id, model)`, `Qwen3-Embedding-0.6B` via `mlx-embeddings` by default, over name, description, themes, mechanics, categories, subdomains, families, and bucketed weight/playtime; designers, artists, and publishers are explicitly excluded) and `games.search_vector` (a weighted `tsvector`: name=A, themes/mechanics/categories/subdomains/families=B, description=C, designers/artists/publishers=D) respectively. |

`scripts/generate_distributions.py` is independent of the database (it reads `data/raw/games.csv` directly) and writes the static frontend asset `frontend/public/distributions.json`; it can run at any point once the raw data exists.

## Stage 4: the ABSA chain (sequential, each step depends on the previous one's output)

1. `scripts/build_review_quality_vocab.py` writes `data/review_quality_vocab_candidates.txt` (human-curation input, feeds `ABSAConfig.DOMAIN_VOCABULARY`) and `data/boilerplate_ngrams.json` (auto-applied, no curation). A one-time corpus-statistics pass; only needs rerunning if the review corpus changes substantially.
2. `scripts/filter_eligible_reviews.py` writes `reviews.is_absa_eligible`/`quality_score` columns (DB-persisted, not a JSON cache). Streams the entire ~4.2M-review corpus once, applies `app.core.review_quality`'s language, hard-filter, dedup, and scoring pipeline, with no per-game cap or pre-restriction to top-ranked games. Measured: 267,950 eligible.
3. `scripts/absa_extract_hf.py` writes the `review_aspects` table via the production 17-aspect DeBERTa zero-shot classifier (`deberta-v3-base-absa-v1.1`). Reads `is_absa_eligible` directly, resumable via `reviews.absa_processed_at`, run in bounded chunks via `--minutes N` rather than one sitting. 39,484 of 267,950 eligible reviews attempted as of this writing.
4. `scripts/absa_aggregate.py` writes the `game_aspect_aggregates` table (`INSERT ... ON CONFLICT DO UPDATE`, grouped by `game_id, aspect`), rerun after each extraction chunk so newly-processed games show up in the UI.
5. `scripts/generate_summaries.py` writes the `game_summaries` table by calling the local LLM through `SummarizationService`. It hardcodes a single game, "Brass: Birmingham"; there's no batch or loop-over-all-games invocation in the repo.

Two earlier scripts are still on disk but not part of this chain: `scripts/absa_filter.py`, a pilot CSV-based quality filter over `master_reviews.csv` rather than the database, frozen and kept for reference; and `scripts/count_eligible.py`/`count_clusters.py`, one-off exploration scripts that write nothing to disk or DB. `scripts/absa_extract.py`, an earlier Ollama-based extraction approach, has been removed from the repo entirely; see [docs/ml/absa.md](../ml/absa.md) for that history.

## Stage 5: recommendation precompute (each model ID independent, all require Stage 2 complete)

| Model ID(s) | Script(s) |
|---|---|
| `cf_item_cosine`, `cf_als` | `scripts/precompute_cf_recommendations.py` reads directly from the `ratings` DB table (26.2M rows, 555,432 distinct users, 27,825 distinct rated games), not a CSV. `cf_item_cosine` uses adjusted, mean-centered cosine similarity; `cf_als` converts ratings to Hu/Koren/Volinsky confidence weights (`1.0 + 40 * rating`) before fitting. Writes top-10 rows for each. |
| `metadata`, `tfidf` | `scripts/precompute_content_recommendations.py` computes both with inline sklearn code over `subdomains` and `families`, deliberately not `themes`, since BGG's `Theme:` namespace already lives inside `families`'s 72 namespaces, so including both would double-count. Writes top-10 rows each. |
| `graph_jaccard`, `deepwalk` | `scripts/precompute_graph_recommendations.py` computes both from live ORM objects across 7 relations (mechanics, categories, subdomains, families, designers, publishers, artists; weights `mechanics=0.35, categories=0.25, subdomains=0.15, families=0.1, designers=0.05, publishers=0.025, artists=0.025`, renormalized to sum 1 at use time). `deepwalk` is a `gensim.Word2Vec` DeepWalk embedding using uniform random walks, not the `node2vec` PyPI package's biased-walk algorithm. See [docs/ml/recommenders.md](../ml/recommenders.md) for why. |

`popularity`, `embedding`, and `hybrid` have no precompute script at all. `popularity` is a live rank query, `embedding` is a live pgvector query, and `hybrid` is a live cross-paradigm blend of `cf_item_cosine` and `metadata` scores, all computed in `RecommendationService.get_recommendations()` at request time and never written to `game_recommendations`. See [docs/architecture/README.md](README.md#recommendation-routing-live-vs-precomputed) for the full routing.

An earlier attempt at a genuine node2vec-package pipeline (`scripts/build_node2vec_graph.py`, `scripts/train_node2vec.py`) never produced a trained model artifact and has been removed from the repo. `data/processed/node2vec_graph.gpickle` (13.2 MB), that path's leftover graph pickle, is still present on disk pending a decision on whether to delete it; `data/` is gitignored in full, so nothing under it, including this pickle, is tracked in git.

## Reproducibility caveats

- **No orchestration.** Every step above is a manual `python script.py` invocation with no dependency-checking, retries, or idempotency guarantees beyond what each script does internally (most `TRUNCATE` or `ON CONFLICT` their own target).
- **Some raw files go unread.** Dataset 1's `ratings_distribution.csv` and five of Dataset 2's seven files (`games_detailed_info.csv`, `2020-08-19.csv`, `2022-01-08.csv`, `bgg-15m-reviews.csv`, `bgg-19m-reviews.csv`) are present on disk but never read by any script. Everything else in both datasets feeds the pipeline; see [docs/data/README.md](../data/README.md#what-each-file-is-used-for) for the full breakdown.
- **File mtimes are not reliable evidence of run order.** `master_game_categories_clean.csv` on disk is timestamped before `master_game_categories.csv`, which just means the `_clean` copy wasn't regenerated after the most recent `build_master_dataset.py` run. This runbook is derived from code, what each script reads and writes, not from `stat` output.
- **Precomputed row coverage has been verified live.** All precomputed models (`metadata`, `tfidf`, `graph_jaccard`, `deepwalk`, `cf_item_cosine`, `cf_als`) cover 27,825 to 28,208 of the catalog's 28,208 games, essentially full coverage, confirmed against a running database. `popularity`, `embedding`, and `hybrid` are never precomputed; they're read live at request time. See [docs/architecture/README.md](README.md#recommendation-routing-live-vs-precomputed).
