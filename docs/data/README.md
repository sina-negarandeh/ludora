# Data

## Provenance

Ludora is built from two Kaggle datasets, merged into one master dataset.

| # | Dataset | Kaggle source | On disk |
|---|---|---|---|
| 1 | Board Games Database from [BoardGameGeek](https://boardgamegeek.com/) ("Threnjen") | [kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) | `data/raw/kaggle_datasets_threnjen_board-games-database-from-boardgamegeek/` |
| 2 | BoardGameGeek Reviews ("jvanelteren") | [kaggle.com/datasets/jvanelteren/boardgamegeek-reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/) | `data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews/` |

Both directories are gitignored in full; nothing under `data/` is tracked in git. Exact license terms and dataset version dates aren't recorded beyond the Kaggle pages linked above; link out to them rather than asserting a license elsewhere.

Every game, rating, and review underneath this project originates with BoardGameGeek and the people who built its community over two decades. This project is a personal proof of concept, not a commentary on BGG or a competitor to it, and it isn't used for any commercial purpose. The data itself belongs to BoardGameGeek and its contributors; nothing here claims otherwise.

### What each file is used for

| File | Role |
|---|---|
| Dataset 1: `games.csv` | Primary game metadata source for the master dataset merge |
| Dataset 1: `mechanics.csv`, `themes.csv`, `subcategories.csv`, `designers_reduced.csv`, `artists_reduced.csv`, `publishers_reduced.csv` | Fallback source for games with no Dataset 2 row, see [Master dataset construction](#master-dataset-construction) |
| Dataset 1: `user_ratings.csv` | Collaborative-filtering training data |
| Dataset 1: `ratings_distribution.csv` | Not used. The app computes rating distributions live from the `ratings` table instead of a static snapshot. |
| Dataset 2: `games_detailed_info2025.csv` | Primary game metadata source for the master dataset merge |
| Dataset 2: `bgg-26m-reviews.csv` | Source for `ratings`/`reviews`/`users` |
| Dataset 2: `games_detailed_info.csv`, `2020-08-19.csv`, `2022-01-08.csv`, `bgg-15m-reviews.csv`, `bgg-19m-reviews.csv` | Not used. Earlier, smaller snapshots superseded by the two files above. |

## BGG terminology

BGG (BoardGameGeek) has several distinct taxonomy fields that are easy to conflate. This project uses BGG's own terms, grounded in [boardgamegeek.com/wiki/page/Category](https://boardgamegeek.com/wiki/page/Category) and [/wiki/page/family](https://boardgamegeek.com/wiki/page/family):

| Term | What it is | Examples | BGG source field |
|---|---|---|---|
| **Category** | BGG's broad subject/format/component classification | Economic, Card Game, Fantasy, Adventure, Dice, Wargame | `boardgamecategory` |
| **Mechanic** | How the game plays | Worker Placement, Deck Building, Area Control | `boardgamemechanic` |
| **Subdomain** | BGG's rank/leaderboard classification: which BGG sub-ranking a game appears on. Distinct from Category, though some categories (Wargame, for instance) automatically promote a game into the matching subdomain. | Strategy, Thematic, Family, Party, Wargame, Abstract Strategy, Children's, Customizable | Derived from rank data, not a `link` field |
| **Family** | The full `boardgamefamily` field: a large, flat bucket of user-curated groupings spanning 72 unrelated namespaces (`Animals`, `Mechanism`, `Crowdfunding`, `Country`, `Theme`, and so on) | `Game: Catan`, `Crowdfunding: Kickstarter`, `Theme: Cthulhu Mythos`, `Series: ...` | `boardgamefamily` |
| **Subfamily** | One specific value within a Family namespace | `Bears` (within `Animals`), `Kickstarter` (within `Crowdfunding`) | `boardgamefamily`, split on its `Group: Value` prefix |
| **Theme** | Specifically the `Theme:` namespace within Family: narrow, specific setting/franchise tags, distinct from Category. Also reachable as one of the 72 Family namespaces; Ludora extracts it into its own table too, since it predates the general Family taxonomy in this project and nothing currently reads it as a plain Family group. | Cthulhu Mythos, Zombies, Alchemy | `boardgamefamily`, filtered to the `Theme:` group |

Ludora models **Category**, **Subdomain**, and **Theme** as three separate tables (`categories`, `subdomains`, `themes`) precisely because BGG treats them as three separate things: a single flat "category" or "theme" concept would conflate a broad subject tag (Category), a leaderboard classification (Subdomain), and a narrow setting tag (Theme). **Family** is modeled as a two-level hierarchy instead of a fourth flat table. `families` holds the 72 namespaces as first-class rows, `subfamilies` holds the roughly 4,200 values with a foreign key to their namespace, because it's the one BGG taxonomy field that's genuinely hierarchical in the source data, and games link to the leaf value (`game_subfamilies`), never to a bare namespace.

## Master dataset construction

`scripts/build_master_dataset.py` outer-merges Dataset 1's `games.csv` with Dataset 2's `games_detailed_info2025.csv` on BGG ID, after asserting BGG ID uniqueness in both sources. Most scalar fields (ratings, weight, playtime, player count, rank, and so on) prefer Dataset 2's value, falling back to Dataset 1 where Dataset 2 has nothing, since Dataset 2 is the more recent scrape.

**Categories, Subdomains, and Themes.** Each entity has a primary source and, for the games with no Dataset 2 row, a fallback:

| Entity | Primary source | Fallback source |
|---|---|---|
| Category | Dataset 2 `boardgamecategory` | Dataset 1 `themes.csv` (non-`Theme_` columns) plus `subcategories.csv`, both verified to be the same BGG Category taxonomy under a different file name |
| Subdomain | Dataset 1 `Cat:*` flags OR Dataset 2 rank-column presence | None needed; both sources are checked directly |
| Theme | Dataset 2 `boardgamefamily`, entries prefixed `Theme:` | Dataset 1 `themes.csv` (`Theme_`-prefixed columns, same taxonomy under a different naming convention) |
| Family | Dataset 2 `boardgamefamily`, the full field split on its `Group: Value` prefix into a namespace and a value (all 72 namespaces, including `Theme:`) | None; Dataset 1 has no equivalent field, so the roughly 428 Dataset-1-only games simply have no Family tags |

**Mechanics, Designers, Artists, Publishers.** Primary source is Dataset 2's stringified list columns (`boardgamemechanic`, `boardgamedesigner`, `boardgameartist`, `boardgamepublisher`); for games with no Dataset 2 row, Dataset 1's corresponding one-hot file (`mechanics.csv`, `designers_reduced.csv`, `artists_reduced.csv`, `publishers_reduced.csv`) fills the gap.

**Game relations** (expansions, implementations, integrations) come from Dataset 2's `boardgameexpansion`/`boardgameimplementation`/`boardgameintegration` fields. These link by game *name*, not BGG ID, in the source data. Ludora resolves each name to a BGG ID via exact, case and whitespace-normalized matching against the merged dataset's own game names. A name that doesn't resolve is kept with a null `related_game_id` rather than dropped, so nothing is silently lost.

Output: `data/processed/master_games.csv` plus one entity/mapping CSV pair each for subdomains, categories, themes, mechanics, designers, artists, and publishers; a `families`/`subfamilies`/`game_subfamilies` trio for the full Family field; and `master_game_relations.csv`.

`scripts/build_interactions_dataset.py` independently streams Dataset 2's `bgg-26m-reviews.csv`, deduplicates on `(user, game_id)`, and writes `master_ratings.csv` (every rating), `master_reviews.csv` (ratings with a written comment), and `master_users.csv`.

Full script-by-script run order: [docs/architecture/data-pipeline.md](../architecture/data-pipeline.md).

## Taxonomy sizes

From `data/processed/master_*.csv` row counts: 8 subdomains, 86 categories, 217 themes, 72 family namespaces (4,208 values), 199 mechanics, 12,255 designers, 13,610 artists, 8,551 publishers.

**17-aspect ABSA taxonomy** (`scripts/absa_extract_hf.py`): Mechanics, Strategy, Theme, Replayability, Components, Artwork, Rulebook, Setup, Learning Curve, Complexity, Downtime, Player Interaction, Balance, Luck, Solo Play, Game Length, Value. Reduced from an original 22 (dropped Gameplay, Immersion, Production Quality, Teardown, Player Count) after checking each against real mention-frequency counts in the review corpus. Full extraction methodology: [docs/ml/absa.md](../ml/absa.md).

## Schema

The relational schema is defined by Alembic migrations in `backend/alembic/versions/`, applied in order. Migration IDs are included for anyone cross-referencing against `backend/alembic/versions/`; they're not meaningful on their own.

1. `c68cea7e830d`: initial `games` table (core scalar columns)
2. `875574550d3c`: add `rank`, `family`
3. `faa4df3d84fb`: replace `family` with a flat `categories` string
4. `00e27df745ad`: normalize categories, designers, mechanics, and publishers into entity and join tables; drop the flat string from step 3
5. `f998ed3df8b5`: add `artists` and its join table, indexes, `NOT NULL` constraints
6. `2388b93dabc8`: `CREATE EXTENSION vector`; add `games.embedding` (384-dim), `embedding_model`, `embedding_updated_at`, `search_vector` (`TSVECTOR`)
7. `f7d3776dc81e`: add `game_recommendations` (composite PK `game_id, recommended_game_id, model`)
8. `04b1ebff26d4`: add `games.num_ratings`, `games.rating_distribution` (JSON)
9. `462f9d4f4b62`: add `games.category_ranks` (JSON)
10. `9fe753fc9003`: add `users`, `ratings`, `reviews`; add several `games` columns (`median_rating`, `num_comments`, `owned_count`, `trading_count`, `wanting_count`, `wishing_count`)
11. `f52e87b1f96c`: add `themes` and its join table
12. `de5ab409f353`: add ABSA tables, `review_aspects` and `game_aspect_aggregates`
13. `ac71b3ec0405`: add `game_summaries`
14. `d4a8f21c6b93`: add `min_playtime`, `max_playtime`, `bayes_avg_rating`, `stddev_rating`, `num_weight_votes`, `thumbnail_url`, `kickstarted`, `is_reimplementation`, `suggested_num_players`, `suggested_playerage`, `suggested_language_dependence`; add `game_relations`
15. `e7a2c58f9b16`: split the taxonomy correctly into `subdomains` (the old `categories`, BGG's rank/leaderboard type), `categories` (BGG's real Category field), and `themes` (BGG Family's `Theme:` group)
16. `a19f6c3e8d47`: rename `games.category_ranks` to `subdomain_ranks`. Same mislabeling as step 15; this column has always held per-subdomain rank, not per-category rank.
17. `10441a9862cc`: add `families` and `game_families`, a first pass at the full BGG Family field modeled as one flat entity table (group name and value as plain columns on the same row)
18. `629567b8e65f`: replace step 17's flat design with a proper two-level hierarchy. `families` (the 72 namespaces, first-class rows) points to `subfamilies` (the roughly 4,200 values, FK'd to their namespace) points to `game_subfamilies` (games link to the leaf value only, since a game is never tagged with a bare namespace in the source data).
19. `49d9f97dc6f8`: add `reviews.language`. `scripts/alter_table.py` previously did this as a raw, unmigrated `ALTER TABLE`, retired in favor of this migration.
20. `f46da67cfb4f`: add `reviews.language_confidence` (fastText's top-1 probability for the `language` guess)
21. `7504c1be2bde`: drop `reviews.created_at`, confirmed `NULL` across all 4.2M rows, since the jvanelteren review source never carried a per-review timestamp
22. `b8e1c4a29f37`: add `game_embeddings` (one row per `(game_id, model)`, unsized `VECTOR`, unique on `(game_id, model)`); drop `games.embedding`, `embedding_model`, `embedding_updated_at`. A fixed-dim single column can't hold more than one embedding model's vectors at once, which blocks comparing or switching models.
23. `c4d8f21a9e56`: `CREATE EXTENSION unaccent`; add a custom `english_unaccent` text search config (copies `english`, runs `unaccent` before stemming). Plain `english` doesn't fold diacritics, so a query for a non-ASCII designer, artist, or publisher name (9 to 10% of them) matched zero rows unless the exact accented spelling was typed.
24. `d91a4c7e3f28`: add `reviews.quality_score`/`is_absa_eligible`, replacing the old JSON-cache ABSA sampling scheme with persisted per-review eligibility, computed once over the full ~4.2M-review corpus by `scripts/filter_eligible_reviews.py` rather than a cache file capped at a pre-restricted sample
25. `129f9cdc157b`: add `review_aspects.prob_positive`/`prob_neutral`/`prob_negative`, the full 3-class softmax rather than just the winning class's confidence, so `scripts/absa_extract_hf.py` can store every prediction, not only ones clearing a confidence bar, and defer any threshold decision to query time
26. `44cec28c864a`: add `reviews.absa_processed_at` plus a partial index matching the resumable-run query shape. True per-review resumability for `scripts/absa_extract_hf.py`, tracking whether a review was attempted independent of whether it produced any storable `review_aspects` rows, backfilled for reviews already represented in `review_aspects`.
27. `1f3e56e3648a`: add `game_recommendations.computed_at`, for freshness tracking on precomputed recommendation rows

### Core tables

| Table | Purpose |
|---|---|
| `games` | One row per BGG game: scalar metadata, `search_vector` (tsvector), `rating_distribution`/`subdomain_ranks` (JSON), `suggested_num_players`/`suggested_playerage`/`suggested_language_dependence` (JSON poll data) |
| `game_embeddings` | Semantic search vectors. One row per `(game_id, model)`, unique-constrained, unsized `VECTOR` column (different embedding models produce different dimensions) so more than one model's vectors can coexist for comparison. |
| `subdomains`, `categories`, `themes`, `mechanics`, `designers`, `artists`, `publishers` + join tables | Normalized many-to-many tag relationships, all `lazy="selectin"` on the `Game` ORM model. See [BGG terminology](#bgg-terminology) for what each one actually means. |
| `families` → `subfamilies` → `game_subfamilies` | The full BGG Family field as a two-level hierarchy: 72 namespace rows, about 4,200 value rows FK'd to their namespace, games linked to the leaf value. Exposed on `Game.families` (the ORM relationship name stays flat for API consistency with the other tag fields, even though the DB layer underneath it is two tables). |
| `game_relations` | Expansion, implementation, and integration links between games, resolved by name (see [Master dataset construction](#master-dataset-construction)) |
| `users`, `ratings` | Numeric-only interactions, used for collaborative filtering |
| `reviews` | Ratings with review text, plus detected `language`/`language_confidence` (fastText's top-1 probability; low-confidence guesses are kept, not discarded, see `scripts/detect_languages.py`), `quality_score`/`is_absa_eligible` (persisted ABSA eligibility, see `scripts/filter_eligible_reviews.py`), and `absa_processed_at` (a per-review resumability marker for `scripts/absa_extract_hf.py`, set regardless of whether the review yielded any storable aspect) |
| `review_aspects` | Per-review, per-aspect ABSA extraction: every winning prediction (17-aspect taxonomy times positive, negative, or neutral sentiment), the full 3-class softmax (`prob_positive`/`prob_neutral`/`prob_negative`), plus confidence and an evidence sentence. `review_id` links back to `reviews`. |
| `game_aspect_aggregates` | Per-game, per-aspect rollup of `review_aspects` (positive, negative, mixed, and neutral counts, mean sentiment), restricted to positive/negative rows clearing `ABSAConfig.WINNER_PROB_THRESHOLD`. `mixed_count`/`neutral_count` are currently always 0, not yet wired into the rollup. |
| `game_recommendations` | Precomputed top-N rows per `(game, model)` pair, read by `RecommendationService` for non-live model IDs; `computed_at` tracks when each row was last written |
| `game_summaries` | One LLM-generated "Community Consensus" paragraph per game |

No `CHECK` constraints exist anywhere in the schema. There's no DB-level rating-range enforcement, for instance; value validity is enforced only in application code, not the database.

## Data quality rules (as implemented, not as a policy document)

- **Staging validation.** `build_master_dataset.py` asserts BGG ID uniqueness in both source datasets before merging.
- **Deduplication.** `(user, game_id)` pair dedup when building interactions (`build_interactions_dataset.py`); exact-duplicate review-text dedup via MD5 hash of normalized text plus bucketed-SimHash near-duplicate detection (`backend/app/core/review_quality.py`, applied at full-corpus scale by `scripts/filter_eligible_reviews.py`; the earlier pilot path, `absa_filter.py`, has its own frozen inline copy); mapping-table dedup via `drop_duplicates()` before load (`ingest_master.py`); DB-level composite primary keys as a final backstop.
- **Review quality and language scoring.** `backend/app/core/review_quality.py` runs a language gate reusing precomputed `reviews.language`/`language_confidence`, then hard filters including a VADER zero-sentiment check, then exact and SimHash near-dup removal, then a weighted density/diversity/specificity/boilerplate score, applied at full-corpus scale by `scripts/filter_eligible_reviews.py`. Reviews scoring at or above `ABSAConfig.QUALITY_SCORE_THRESHOLD` (0.6, calibrated against a real 50K-review score distribution) are ABSA-eligible. This replaces the old `compute_quality_score()` heuristic (fastText-per-call, a hand-picked keyword list, a spam-repetition penalty), which used to be duplicated near-identically in `absa_filter.py` and `absa_extract_hf.py`. `absa_filter.py`, an earlier, frozen pilot path, still has its own inlined copy, decoupled from `ABSAConfig`, but the canonical path no longer does.
- **Relation resolution.** `game_relations.related_game_id` is null wherever the source name doesn't exact-match a known game. Not dropped, not fuzzy-matched. See [Master dataset construction](#master-dataset-construction).
- **Schema validation at ingest time.** There is exactly one `@field_validator` in the whole backend (`backend/app/schemas/game.py`), and it's an API *response* shaper, not an ingestion guard.

## Glossary

Consistent terms used across all Ludora documentation:

| Term | Meaning |
|---|---|
| **Dataset 1 / Threnjen dataset** | `threnjen/board-games-database-from-boardgamegeek` (Kaggle), `data/raw/kaggle_datasets_threnjen_board-games-database-from-boardgamegeek/` |
| **Dataset 2 / jvanelteren dataset** | `jvanelteren/boardgamegeek-reviews` (Kaggle), `data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews/` |
| **Master dataset** | The merged, cleaned output in `data/processed/`, built by `build_master_dataset.py` and `build_interactions_dataset.py` |
| **Category** | BGG's real Category field, see [BGG terminology](#bgg-terminology) |
| **Subdomain** | BGG's rank/leaderboard type (8 values), see [BGG terminology](#bgg-terminology) |
| **Theme** | BGG Family's `Theme:` group only, see [BGG terminology](#bgg-terminology) |
| **Family** | The full BGG `boardgamefamily` field, 72 namespaces, see [BGG terminology](#bgg-terminology) |
| **Subfamily** | One value within a Family namespace, e.g. `Bears` within `Animals`, see [BGG terminology](#bgg-terminology) |
| **Aspect** | One of the 17 ABSA taxonomy labels (Mechanics, Rulebook, Downtime, and so on) |
| **Recommendation model ID** | One of 9 lowercase identifiers (`popularity`, `metadata`, `tfidf`, `embedding`, `graph_jaccard`, `deepwalk`, `cf_item_cosine`, `cf_als`, `hybrid`), see [docs/ml/recommenders.md](../ml/recommenders.md) |
| **Community Consensus** | The product name for the LLM-generated per-game summary paragraph (`game_summaries` table) |
