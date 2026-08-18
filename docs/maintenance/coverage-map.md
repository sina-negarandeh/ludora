# Documentation coverage map

Internal maintenance artifact, not reader-facing product documentation. It supports a scoped doc-sync workflow: when code changes, find every doc that makes a claim about the changed capability instead of relying on grep alone (grep only catches a fact if every doc phrased it identically, which isn't guaranteed).

**Update this file when**: you add or remove a doc; a capability's owning doc changes; a new doc starts referencing an existing capability or tracked fact; a tracked fact is resolved (move it out of the table, note where).

## How to use this

1. A code change touches path X.
2. Find X, or its capability, in the table below.
3. Everything in "Also referenced in" is a candidate for the same update — check each one.
4. If the change resolves or alters one of the tracked facts in the second table, update every doc listed for that fact, then remove or rewrite the row.
5. If a change introduces a new cross-reference (a doc now mentions something it didn't before), add it to the relevant row.

## Capabilities

| Capability | Owning doc | Key source paths | Also referenced in |
|---|---|---|---|
| Game catalog: browse/filter/sort | `docs/product/features.md#1` | `frontend/src/pages/GamesList.tsx`, `frontend/src/components/GroupedMultiSelect.tsx`, `backend/app/api/routes/games.py`, `backend/app/services/game_service.py` | `README.md`, `docs/architecture/README.md` |
| BGG taxonomy (Subdomain/Category/Theme/Family/Subfamily) | `docs/data/README.md#bgg-terminology` | `backend/app/database/models.py`, `scripts/build_master_dataset.py`, `backend/app/services/metadata_service.py`, `backend/app/api/routes/metadata.py` | `docs/product/features.md`, `docs/case-study.md`, `docs/architecture/README.md` |
| Search: lexical/semantic/hybrid | `docs/ml/search.md` | `backend/app/services/search_service.py`, `backend/app/schemas/game_query.py` | `README.md`, `docs/product/features.md#9`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/case-study.md`, `docs/roadmap.md`, `docs/ml/model-cards/search-lexical.md`, `docs/ml/model-cards/search-semantic.md` |
| Recommendation engine (10 model ids) | `docs/ml/recommenders.md` | `backend/app/services/recommendation_service.py`, `backend/app/recommenders/`, `scripts/precompute_content_recommendations.py`, `scripts/precompute_svd_recommendations.py`, `scripts/precompute_cf_recommendations.py`, `scripts/precompute_graph_recommendations.py` | `README.md`, `docs/product/features.md#10`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/ml/evaluation.md`, `docs/case-study.md`, `docs/roadmap.md`, `docs/limitations.md`, `AGENTS.md` |
| ABSA (aspect extraction) | `docs/ml/absa.md` | `scripts/absa_extract_hf.py`, `absa_aggregate.py`, `absa_filter.py`, `generate_stratified_sample.py` | `docs/product/features.md#7`, `docs/ml/README.md`, `docs/architecture/data-pipeline.md`, `docs/limitations.md` |
| LLM summarization ("Community Consensus") | `docs/ml/absa.md` (downstream section) | `backend/app/services/summarization_service.py`, `scripts/generate_summaries.py` | `docs/product/features.md#7`, `docs/ml/README.md`, `docs/roadmap.md` |
| AI Assistant | `docs/ml/assistant.md` | `backend/app/services/assistant_service.py`, `assistant_orchestrator.py`, `entity_resolver.py` | `README.md`, `docs/product/features.md#2`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/roadmap.md`, `docs/limitations.md`, `docs/case-study.md` |
| Game detail page (stats/ratings/reviews UI) | `docs/product/features.md#3-6` | `frontend/src/pages/GameDetail.tsx` | `docs/architecture/README.md` |
| Data pipeline / dataset provenance | `docs/data/README.md`, `docs/architecture/data-pipeline.md` | `data/raw/`, `data/processed/`, `scripts/build_master_dataset.py`, `scripts/ingest_master.py` | `README.md`, `docs/case-study.md`, `docs/setup/README.md`, `AGENTS.md` |
| Database schema (migrations) | `docs/data/README.md#schema` | `backend/alembic/versions/` | `docs/architecture/README.md` |
| Testing reality | `docs/engineering/testing.md` | `backend/test_*.py`, `frontend/package.json` | `README.md`, `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`, `docs/limitations.md`, `docs/case-study.md` |
| Setup / security posture | `docs/setup/README.md`, `docs/limitations.md` | `docker-compose.yml`, `backend/app/core/config.py`, `backend/app/main.py` | `README.md`, `AGENTS.md`, `backend/AGENTS.md`, `docs/architecture/README.md`, `docs/case-study.md` |

## Tracked cross-cutting facts

Specific claims that currently appear in multiple docs and are the most likely to change. If one of these changes, every file listed needs the same update — this is exactly the propagation step a partial doc-sync would otherwise miss.

| Fact (current state) | Appears in |
|---|---|
| Two Kaggle datasets, not three | `AGENTS.md`, `README.md`, `docs/case-study.md` |
| 10 recommendation model ids (not 9) | `README.md`, `AGENTS.md`, `docs/architecture/README.md`, `docs/product/features.md`, `docs/case-study.md`, `docs/ml/README.md`, `docs/ml/recommenders.md`, `docs/limitations.md` |
| 4 of 10 model ids (`embedding`/`metadata`/`tfidf`/`hybrid`) route to one live query | `AGENTS.md`, `README.md`, `docs/case-study.md`, `docs/product/features.md`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/ml/recommenders.md`, `docs/roadmap.md`, `docs/limitations.md` |
| `data/` is gitignored in full — nothing under it (`raw/`, `processed/`, `models/`) is tracked in git; large files there are present on disk only | `docs/data/README.md`, `docs/architecture/data-pipeline.md`, `docs/ml/recommenders.md`, `docs/audit/phase-1-audit.md` |
| No automated test suite, no CI | `AGENTS.md`, `README.md`, `docs/engineering/testing.md`, `docs/limitations.md` |
| No auth, CORS wide open, hardcoded local DB credential default | `AGENTS.md`, `backend/AGENTS.md`, `docs/architecture/README.md`, `docs/setup/README.md`, `docs/case-study.md`, `docs/limitations.md` |
| `docker compose up` brings up an empty database (no seed step) | `AGENTS.md`, `README.md`, `docs/setup/README.md` |
| `conversation_id` accepted but unused — no multi-turn assistant memory | `README.md`, `docs/ml/README.md`, `docs/ml/assistant.md`, `docs/roadmap.md`, `docs/limitations.md` |
| `get_reviews`/`get_aspects` assistant intents fall back to `get_game` | `docs/product/features.md`, `docs/ml/assistant.md`, `docs/roadmap.md`, `docs/limitations.md` |
| ABSA covers 100 games / 10,000 sampled reviews, not the full corpus | `docs/product/features.md`, `docs/architecture/data-pipeline.md`, `docs/ml/absa.md`, `docs/ml/README.md`, `docs/limitations.md` |
| Evaluation scripts compute real metrics but never persist a results file (numbers shown are "Observed," not "Measured") | `docs/case-study.md`, `docs/product/features.md`, `docs/ml/search.md`, `docs/ml/evaluation.md`, `docs/limitations.md`, `backend/AGENTS.md` |
| Commit history spans two calendar days (2026-08-15/16) | `docs/case-study.md`, `docs/data/README.md`, `docs/limitations.md` |
| 21 migrations, 27 pipeline scripts, 19 API endpoints | `README.md`, `docs/case-study.md`, `docs/architecture/README.md` |
| BGG Family: 72 namespaces, ~4,200 values, modeled as `families` → `subfamilies` → `game_subfamilies` | `docs/data/README.md`, `docs/case-study.md`, `docs/product/features.md` |

## Not yet covered by this map

Any doc or claim added after this file's last update. Cross-references above were generated by grepping the doc set on 2026-08-17 for each fact's known phrasings — a claim stated in genuinely new wording won't have been caught automatically and may be missing here until the next update.
