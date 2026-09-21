# Offline data pipeline

21 standalone scripts, run by hand, in order, against a local Postgres. **There is no orchestrator**: no Airflow, no Prefect, no numbered-script convention, no CI job.

This doc is about *execution order*. What each script computes and why lives with that subject: [search.md](../ml/search.md), [recommenders.md](../ml/recommenders.md), [absa.md](../ml/absa.md), [data/README.md](../data/README.md).

> The order below is reconstructed from each script's read and write dependencies, not from a committed runbook and not from file timestamps. Treat it as an operational guide rather than an authored spec.

## Stage 1: build the master CSVs

Independent of the database and of each other. Both can run as soon as the raw CSVs exist.

- `build_master_dataset.py` outer-merges both datasets on BGG ID and emits `master_games.csv`, an entity/mapping CSV pair per taxonomy, the `families`/`subfamilies`/`game_subfamilies` trio, and `master_game_relations.csv`.
- `build_interactions_dataset.py` streams the 26M-row review file in 1M-row chunks, dedupes on `(user, game_id)`, and emits `master_ratings.csv`, `master_reviews.csv`, `master_users.csv`.

## Stage 2: load Postgres

`ingest_master.py`. **It `TRUNCATE`s every core table first**, then `COPY`s from Stage 1. It projects `master_games.csv` down to the DB column subset, dedupes every mapping CSV, and filters ratings, reviews, and relations to `game_id`s that actually exist in `games`.

## Stage 3: enrichment

Requires Stage 2. These are independent of each other.

| Script | Populates |
|---|---|
| `populate_subdomain_ranks.py` | `games.subdomain_ranks`. Treats BGG's `21926` sentinel as unranked and drops it |
| `populate_rating_distribution.py` | `games.rating_distribution`, `games.num_ratings`, recomputed from the 26M rating rows rather than the unused `ratings_distribution.csv` |
| `detect_languages.py` | `reviews.language`, `reviews.language_confidence`. **Run `uv run alembic upgrade head` first**, since two migrations add these columns |
| `update_embeddings.py` | `game_embeddings` |
| `update_search_vectors.py` | `games.search_vector` |

`generate_distributions.py` reads `data/raw/games.csv` directly and writes a committed JSON file, so it needs no database and can run at any point.

## Stage 4: the ABSA chain

Strictly sequential. Each step consumes the previous step's output.

1. `build_review_quality_vocab.py`, a one-time corpus-statistics pass. Only rerun if the review corpus changes substantially.
2. `filter_eligible_reviews.py` sets `reviews.is_absa_eligible` and `quality_score` over the whole corpus.
3. `absa_extract_hf.py` writes `review_aspects`. Resumable, and run in bounded chunks via `--minutes N` rather than one sitting.
4. `absa_aggregate.py` writes `game_aspect_aggregates`. **Rerun after each extraction chunk**, or newly-processed games will not appear in the UI.
5. `generate_summaries.py` writes `game_summaries`, one hardcoded game at a time.

Three scripts sit on disk outside this chain: `absa_filter.py` (a frozen CSV-based pilot, kept for reference) and `count_eligible.py`/`count_clusters.py` (one-off exploration, writing nothing).

## Stage 5: recommendation precompute

Requires Stage 2. All three are independent of each other.

| Script | Writes model IDs |
|---|---|
| `precompute_cf_recommendations.py` | `cf_item_cosine`, `cf_als` |
| `precompute_content_recommendations.py` | `metadata`, `tfidf` |
| `precompute_graph_recommendations.py` | `graph_jaccard`, `deepwalk` |

`popularity`, `embedding`, and `hybrid` have no precompute step. All three are computed at request time and never written to `game_recommendations`. Routing: [architecture/README.md](README.md#recommendation-routing-live-vs-precomputed).

## Reproducibility caveats

- **No orchestration.** Every step is a manual invocation with no dependency checking, retries, or idempotency guarantee beyond what each script does internally. Most either `TRUNCATE` or `ON CONFLICT` their own target.
- **File mtimes are not evidence of run order.** `master_game_categories_clean.csv` is timestamped *before* `master_game_categories.csv`, which only means the `_clean` copy was not regenerated after the last build. This order comes from reading the code.
- **Some raw files are never read.** Dataset 1's `ratings_distribution.csv` and five of Dataset 2's seven files. See [data/README.md](../data/README.md#what-each-file-is-used-for).
- **Precomputed coverage is checked live** and is essentially full. Per-model numbers: [recommenders.md](../ml/recommenders.md).
