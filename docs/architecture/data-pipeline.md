# Offline data pipeline

Ludora's ML features (search, recommendations, ABSA, summaries) are populated by 27 standalone Python scripts run by hand, in order, against a local Postgres instance — there is no orchestrator (no Airflow/Prefect/Makefile/CI job). This doc reconstructs the actual run order from each script's read/write dependencies, not from filesystem timestamps (which are not reliable — see the note at the bottom).

For dataset sources and schema, see [docs/data/README.md](../data/README.md). This doc is about *execution order*, not data shape.

> **Status: this order is derived from each script's actual read/write dependencies, not a repository-committed runbook.** No `Makefile`, `justfile`, or numbered-script convention exists in the repo — treat this as an operational guide, not an authored spec.

## Stage 1 — Build the master datasets (from raw CSVs, independent of the DB)

| Script | Reads | Writes |
|---|---|---|
| `scripts/build_master_dataset.py` | Both datasets' game-metadata files, outer-merged on BGG ID, plus Dataset 1's `mechanics.csv`/`themes.csv`/`subcategories.csv`/`designers_reduced.csv`/`artists_reduced.csv`/`publishers_reduced.csv` as fallback sources | `data/processed/master_games.csv`, one entity/mapping CSV pair each for subdomains, categories, themes, mechanics, designers, artists, publishers, a `families`/`subfamilies`/`game_subfamilies` trio for the full BGG Family field (72 namespaces, ~4,200 values), and `master_game_relations.csv` |
| `scripts/build_interactions_dataset.py` | Dataset 2's `bgg-26m-reviews.csv` (streamed, 1M-row chunks; dedup on `(user, game_id)`) | `data/processed/master_ratings.csv`, `master_reviews.csv`, `master_users.csv` |

Exact dataset provenance and the category/subdomain/theme sourcing logic: [docs/data/README.md](../data/README.md). These two scripts are independent of each other and of the database — both can run any time after the raw CSVs exist.

## Stage 2 — Load Postgres

| Script | What it does |
|---|---|
| `scripts/ingest_master.py` | `TRUNCATE`s all core tables, then `COPY`s from the Stage-1 CSVs. Projects `master_games.csv` down to a DB-column subset (`master_games_clean.csv`), dedups every mapping CSV (`copy_mapping_dedup()`), and filters `master_ratings.csv`/`master_reviews.csv`/`master_game_relations.csv` to only `game_id`s present in the games table before loading. |

## Stage 3 — Enrichment (requires `games`/`ratings`/`reviews` already loaded)

| Script | What it does |
|---|---|
| `scripts/populate_subdomain_ranks.py` | Reads `games_detailed_info2025.csv` directly; writes `games.subdomain_ranks` JSON. Treats BGG's `21926` sentinel as "unranked" and drops it. |
| `scripts/populate_rating_distribution.py` | DB-native: `GROUP BY game_id, ROUND(rating*2)/2.0` against the `ratings` table; writes `games.rating_distribution` JSON + `games.num_ratings`. Recomputes from the 26M interaction rows rather than using the unused `data/raw/ratings_distribution.csv`. |
| `scripts/detect_languages.py` | Backfills `reviews.language` and `reviews.language_confidence` (added by the `49d9f97dc6f8`/`f46da67cfb4f` Alembic migrations — run `uv run alembic upgrade head` first) in batches of 10,000 using the fastText `lid.176.ftz` language-ID model. Stores the detected code regardless of confidence — low-confidence guesses are kept, not discarded, so downstream consumers can threshold on `language_confidence` themselves; only empty/unparseable comments get `language='unknown'`. |
| `scripts/update_embeddings.py` + `scripts/update_search_vectors.py` | Populate `game_embeddings` (one upserted row per `(game_id, model)` — `Qwen3-Embedding-0.6B` via `mlx-embeddings` by default, name+description+themes+mechanics+categories+subdomains+families+bucketed weight/playtime, designers/artists/publishers explicitly excluded) and `games.search_vector` (weighted `tsvector`: name=A, themes/mechanics/categories/subdomains/families=B, description=C, designers/artists/publishers=D) respectively. |

`scripts/generate_distributions.py` is independent of the database (reads `data/raw/games.csv` directly) and writes the static frontend asset `frontend/public/distributions.json` — it can run at any point once the raw data exists.

## Stage 4 — ABSA chain (sequential; each step depends on the previous one's output)

1. `scripts/build_review_quality_vocab.py` → `data/review_quality_vocab_candidates.txt` (human-curation input, feeds `ABSAConfig.DOMAIN_VOCABULARY`) + `data/boilerplate_ngrams.json` (auto-applied, no curation) — one-time corpus-statistics pass, only needs rerunning if the review corpus changes substantially.
2. `scripts/filter_eligible_reviews.py` → `reviews.is_absa_eligible`/`quality_score` columns (DB-persisted, not a JSON cache) — streams the **entire** ~4.2M-review corpus once, applies `app.core.review_quality`'s language/hard-filter/dedup/score pipeline, no per-game cap or pre-restriction to top-ranked games. Measured: 267,950 eligible.
3. `scripts/absa_extract_hf.py` → `review_aspects` table (production 17-aspect DeBERTa zero-shot classifier, `deberta-v3-base-absa-v1.1`; reads `is_absa_eligible` directly, resumable via `reviews.absa_processed_at`; run in bounded chunks via `--minutes N` rather than one sitting — 39,484/267,950 eligible reviews attempted as of this writing)
4. `scripts/absa_aggregate.py` → `game_aspect_aggregates` table (`INSERT ... ON CONFLICT DO UPDATE`, grouped by `game_id, aspect`; rerun after each extraction chunk so newly-processed games show up in the UI)
5. `scripts/generate_summaries.py` → `game_summaries` table (calls the local LLM through `SummarizationService`; **hardcodes a single game, "Brass: Birmingham" — there is no batch/loop-over-all-games invocation in the repo**)

`scripts/absa_extract.py` is an **earlier, abandoned** approach (Ollama + `qwen2.5:7b`, prompted JSON extraction rather than a discriminative classifier) — see [docs/ml/absa.md](../ml/absa.md) for the two-implementation history. It is not part of the current chain. `scripts/absa_filter.py` is a separate, earlier/pilot CSV-based quality filter (over `master_reviews.csv`, not DB-based) — frozen, not wired into the current chain, kept for historical reference. `scripts/count_eligible.py` and `count_clusters.py` are one-off exploration/estimation scripts that write nothing to disk or DB (`count_stratified.py`, a similar script for the old sampling scheme, was deleted along with `generate_stratified_sample.py`).

## Stage 5 — Recommendation precompute (each model ID independent, all require Stage 2 complete)

| Model ID(s) | Script(s) |
|---|---|
| `cf_svd` | `scripts/train_svd.py` (trains `SVDRecommender`, pickles to `data/models/cf_svd.pkl`) → `scripts/precompute_svd_recommendations.py` (loads the pickle, writes top-20 rows per game to `game_recommendations`) |
| `cf_item_cosine`, `cf_als`, (also re-derives `cf_svd`) | `scripts/precompute_cf_recommendations.py` — a second, independent path that fits all three collaborative recommenders directly from `data/raw/user_ratings.csv` and writes top-10 rows for each |
| `metadata`, `tfidf`, `embedding`, `hybrid` | `scripts/precompute_content_recommendations.py` — computes all four with inline sklearn code and writes top-10 rows each. **Note:** per [docs/architecture/README.md](README.md#known-limitation-four-recommendation-ids-collapse-to-one-query), `RecommendationService` never actually reads these four rows at request time. |
| `graph_jaccard`, `deepwalk` | `scripts/precompute_graph_recommendations.py` — both computed from live ORM objects; `deepwalk` is a `gensim.Word2Vec` DeepWalk embedding (uniform random walks), not the `node2vec` PyPI package's biased-walk algorithm. See [docs/ml/recommenders.md](../ml/recommenders.md) for why. |

A separate, disconnected attempt at a genuine node2vec-package pipeline (`scripts/build_node2vec_graph.py`, `scripts/train_node2vec.py`) was scaffolded but never completed — no trained model artifact ever existed — and has been removed from the repo. `data/processed/node2vec_graph.gpickle` (13.2 MB), that path's leftover graph pickle, is still present on disk pending a decision on whether to delete it (`data/` is gitignored in full — nothing under it, including this pickle, is tracked in git).

## Reproducibility caveats

- **No orchestration**: every step above is a manual `python script.py` invocation with no dependency-checking, retries, or idempotency guarantees beyond what each script does internally (most `TRUNCATE` or `ON CONFLICT` their own target).
- **`precompute_svd_recommendations.py` (SVD only) and `precompute_content_recommendations.py` (metadata/TF-IDF/embedding/hybrid) are separate scripts** — named distinctly precisely because they used to share the name `precompute_recommendations.py` in two different directories and were easy to confuse.
- **Some raw files go unread**: Dataset 1's `ratings_distribution.csv` and five of Dataset 2's seven files (`games_detailed_info.csv`, `2020-08-19.csv`, `2022-01-08.csv`, `bgg-15m-reviews.csv`, `bgg-19m-reviews.csv`) are present on disk but never read by any script. Everything else in both datasets feeds the pipeline — see [docs/data/README.md](../data/README.md#what-each-file-is-used-for) for the full breakdown.
- **File mtimes are not reliable evidence of run order** — e.g. `master_game_categories_clean.csv` on disk is timestamped *before* `master_game_categories.csv`, indicating the `_clean` copy was not regenerated after the most recent `build_master_dataset.py` run. This runbook is derived from code (what each script reads/writes), not from `stat` output.
- **Whether the DB currently holds precomputed rows for every model ID has not been verified by this audit** — the scripts exist and are readable, but confirming `game_recommendations` row counts per model would require a running database, which this documentation pass did not have access to. Treat table-population claims for CF/graph models as "the code to produce them exists and is traceable," not as "verified present in a live database."
