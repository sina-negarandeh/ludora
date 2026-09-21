# Data

## Provenance

Ludora is built from two Kaggle datasets, merged into one master dataset.

| # | Dataset | Kaggle source | On disk |
|---|---|---|---|
| 1 | Board Games Database from [BoardGameGeek](https://boardgamegeek.com/) ("Threnjen") | [kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/) | `data/raw/kaggle_datasets_threnjen_board-games-database-from-boardgamegeek/` |
| 2 | BoardGameGeek Reviews ("jvanelteren") | [kaggle.com/datasets/jvanelteren/boardgamegeek-reviews](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews/) | `data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews/` |

Both directories are gitignored in full. Nothing under `data/` is tracked in git. Exact license terms and dataset version dates aren't recorded beyond the Kaggle pages linked above. Link out to them rather than asserting a license elsewhere.

Every game, rating, and review underneath this project originates with BoardGameGeek and the people who built its community over two decades. Ludora is not a commentary on BGG or a competitor to it, and it is not used for any commercial purpose. The data itself belongs to BoardGameGeek and its contributors. Nothing here claims otherwise.

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
| **Family** | The full `boardgamefamily` field. A large, flat bucket of user-curated groupings spanning 72 unrelated namespaces: `Animals`, `Mechanism`, `Crowdfunding`, `Country`, `Theme`, and so on | `Game: Catan`, `Crowdfunding: Kickstarter`, `Theme: Cthulhu Mythos`, `Series: ...` | `boardgamefamily` |
| **Subfamily** | One specific value within a Family namespace | `Bears` (within `Animals`), `Kickstarter` (within `Crowdfunding`) | `boardgamefamily`, split on its `Group: Value` prefix |
| **Theme** | Specifically the `Theme:` namespace within Family: narrow, specific setting/franchise tags, distinct from Category. Also reachable as one of the 72 Family namespaces. Ludora extracts it into its own table too. It predates the general Family taxonomy in this project, and nothing currently reads it as a plain Family group. | Cthulhu Mythos, Zombies, Alchemy | `boardgamefamily`, filtered to the `Theme:` group |

Ludora models **Category**, **Subdomain**, and **Theme** as three separate tables (`categories`, `subdomains`, `themes`). BGG treats them as three separate things. A single flat "category" or "theme" concept would conflate a broad subject tag (Category), a leaderboard classification (Subdomain), and a narrow setting tag (Theme). **Family** is modeled as a two-level hierarchy instead of a fourth flat table. `families` holds the 72 namespaces as first-class rows. `subfamilies` holds the roughly 4,200 values with a foreign key to their namespace. Family is the one BGG taxonomy field that is genuinely hierarchical in the source data. Games link to the leaf value (`game_subfamilies`), never to a bare namespace.

## Master dataset construction

`scripts/build_master_dataset.py` outer-merges Dataset 1's `games.csv` with Dataset 2's `games_detailed_info2025.csv` on BGG ID, after asserting BGG ID uniqueness in both sources. Most scalar fields prefer Dataset 2's value: ratings, weight, playtime, player count, rank, and so on. They fall back to Dataset 1 where Dataset 2 has nothing, since Dataset 2 is the more recent scrape.

**Categories, Subdomains, and Themes**. Each entity has a primary source and, for the games with no Dataset 2 row, a fallback:

| Entity | Primary source | Fallback source |
|---|---|---|
| Category | Dataset 2 `boardgamecategory` | Dataset 1 `themes.csv` (non-`Theme_` columns) plus `subcategories.csv`. Both were checked to be the same BGG Category taxonomy under a different file name |
| Subdomain | Dataset 1 `Cat:*` flags OR Dataset 2 rank-column presence | None needed. Both sources are checked directly |
| Theme | Dataset 2 `boardgamefamily`, entries prefixed `Theme:` | Dataset 1 `themes.csv` (`Theme_`-prefixed columns, same taxonomy under a different naming convention) |
| Family | Dataset 2 `boardgamefamily`. The full field splits on its `Group: Value` prefix into a namespace and a value, across all 72 namespaces, including `Theme:` | None. Dataset 1 has no equivalent field, so the roughly 428 Dataset-1-only games simply have no Family tags |

**Mechanics, Designers, Artists, Publishers**. Primary source is Dataset 2's stringified list columns (`boardgamemechanic`, `boardgamedesigner`, `boardgameartist`, `boardgamepublisher`). For games with no Dataset 2 row, Dataset 1's corresponding one-hot file (`mechanics.csv`, `designers_reduced.csv`, `artists_reduced.csv`, `publishers_reduced.csv`) fills the gap.

**Game relations** (expansions, implementations, integrations) come from Dataset 2's `boardgameexpansion`/`boardgameimplementation`/`boardgameintegration` fields. These link by game *name*, not BGG ID, in the source data. Ludora resolves each name to a BGG ID via exact, case and whitespace-normalized matching against the merged dataset's own game names. A name that doesn't resolve is kept with a null `related_game_id` rather than dropped, so nothing is silently lost.

Output: `data/processed/master_games.csv` plus one entity/mapping CSV pair each for subdomains, categories, themes, mechanics, designers, artists, and publishers. A `families`/`subfamilies`/`game_subfamilies` trio for the full Family field. And `master_game_relations.csv`.

`scripts/build_interactions_dataset.py` independently streams Dataset 2's `bgg-26m-reviews.csv`, deduplicates on `(user, game_id)`, and writes `master_ratings.csv` (every rating), `master_reviews.csv` (ratings with a written comment), and `master_users.csv`.

Full script-by-script run order: [docs/architecture/data-pipeline.md](../architecture/data-pipeline.md).

## Taxonomy sizes

From `data/processed/master_*.csv` row counts: 8 subdomains, 86 categories, 217 themes, 72 family namespaces (4,208 values), 199 mechanics, 12,255 designers, 13,610 artists, 8,551 publishers.

The ABSA taxonomy is a separate 17-aspect set, cut from 22 against real mention counts. Listed with its rationale in [absa.md](../ml/absa.md).

## Schema

Defined by the Alembic migrations in `backend/alembic/versions/`, applied in order.

**Family is the one BGG taxonomy field that is genuinely hierarchical in the source.** It therefore gets `families` → `subfamilies` → `game_subfamilies`. Every other tag uses a flat entity-plus-join pattern. Family was modeled that way once, and corrected.

### Core tables

| Table | Purpose |
|---|---|
| `games` | One row per BGG game: scalar metadata, `search_vector`, and JSON columns for `rating_distribution`, `subdomain_ranks`, and the three suggested-* polls |
| `game_embeddings` | Semantic search vectors, one row per `(game_id, model)` |
| `subdomains`, `categories`, `themes`, `mechanics`, `designers`, `artists`, `publishers` | Normalized tag tables plus join tables, all `lazy="selectin"` on the `Game` model. See [BGG terminology](#bgg-terminology) for what each means |
| `families` → `subfamilies` → `game_subfamilies` | The Family hierarchy above. Exposed as `Game.families`, flat, for API consistency with the other tag fields |
| `game_relations` | Expansion, implementation, and integration links, resolved by name |
| `users`, `ratings` | Numeric-only interactions, for collaborative filtering |
| `reviews` | Ratings with text, plus the derived `language`, `quality_score`, `is_absa_eligible`, and `absa_processed_at` columns |
| `review_aspects`, `game_aspect_aggregates` | Per-review ABSA output and its per-game rollup. See [absa.md](../ml/absa.md) |
| `game_recommendations` | Precomputed top-N per `(game, model)`, with `computed_at` |
| `game_summaries` | One Community Consensus paragraph per game |

**No `CHECK` constraints exist anywhere.** There is no DB-level rating-range enforcement. Validity is enforced in application code, where it is enforced at all.

## Data quality rules, as implemented

- **Staging.** `build_master_dataset.py` asserts BGG ID uniqueness in both sources before merging.
- **Deduplication.** `(user, game_id)` pairs when building interactions. Exact review text by MD5 of the normalized string, plus bucketed SimHash for near-duplicates. Mapping tables via `drop_duplicates()` before load. Composite primary keys as the final backstop.
- **Review quality.** A four-stage, model-free filter decides ABSA eligibility at full-corpus scale. Full design and the measured precision ceiling: [absa.md](../ml/absa.md).
- **Relation resolution.** `game_relations.related_game_id` is null wherever the source name does not exact-match a known game. Not dropped, not fuzzy-matched.
- **There is exactly one `@field_validator` in the whole backend**, and it shapes an API *response* rather than guarding ingestion.

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
