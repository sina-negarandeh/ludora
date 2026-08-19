# Documentation coverage map

Internal maintenance artifact, not reader-facing product documentation. It supports a scoped doc-sync workflow: when code changes, find every doc that makes a claim about the changed capability instead of relying on grep alone, since grep only catches a fact if every doc phrased it identically, which isn't guaranteed.

**Update this file when**: you add or remove a doc; a capability's owning doc changes; a new doc starts referencing an existing capability or tracked fact; a tracked fact is resolved (move it out of the table, note where).

## How to use this

1. A code change touches path X.
2. Find X, or its capability, in the table below.
3. Everything in "Also referenced in" is a candidate for the same update; check each one.
4. If the change resolves or alters one of the tracked facts in the second table, update every doc listed for that fact, then remove or rewrite the row.
5. If a change introduces a new cross-reference (a doc now mentions something it didn't before), add it to the relevant row.

## Capabilities

| Capability | Owning doc | Key source paths | Also referenced in |
|---|---|---|---|
| Game catalog: browse/filter/sort | `docs/product/features.md#1` | `frontend/src/pages/GamesList.tsx`, `frontend/src/components/GroupedMultiSelect.tsx`, `backend/app/api/routes/games.py`, `backend/app/services/game_service.py` | `README.md`, `docs/architecture/README.md` |
| BGG taxonomy (Subdomain/Category/Theme/Family/Subfamily) | `docs/data/README.md#bgg-terminology` | `backend/app/database/models.py`, `scripts/build_master_dataset.py`, `backend/app/services/metadata_service.py`, `backend/app/api/routes/metadata.py` | `docs/product/features.md`, `docs/case-study.md`, `docs/architecture/README.md` |
| Search: lexical/semantic/hybrid | `docs/ml/search.md` | `backend/app/services/search_service.py`, `backend/app/schemas/game_query.py` | `README.md`, `docs/product/features.md#9`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/case-study.md`, `docs/roadmap.md`, `docs/ml/model-cards/search-lexical.md`, `docs/ml/model-cards/search-semantic.md` |
| Recommendation engine (9 model ids) | `docs/ml/recommenders.md` | `backend/app/services/recommendation_service.py`, `backend/app/recommenders/`, `scripts/precompute_content_recommendations.py`, `scripts/precompute_cf_recommendations.py`, `scripts/precompute_graph_recommendations.py` | `README.md`, `docs/product/features.md#10`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/ml/evaluation.md`, `docs/case-study.md`, `docs/roadmap.md`, `docs/limitations.md`, `AGENTS.md` |
| ABSA (aspect extraction) | `docs/ml/absa.md` | `scripts/filter_eligible_reviews.py`, `scripts/absa_extract_hf.py`, `scripts/absa_aggregate.py`, `backend/app/core/review_quality.py`, `backend/app/services/aspect_service.py` | `docs/product/features.md#7`, `docs/ml/README.md`, `docs/architecture/data-pipeline.md`, `docs/limitations.md` |
| LLM summarization ("Community Consensus") | `docs/ml/absa.md` (downstream section) | `backend/app/services/summarization_service.py`, `scripts/generate_summaries.py` | `docs/product/features.md#7`, `docs/ml/README.md`, `docs/roadmap.md` |
| AI Assistant | `docs/ml/assistant.md` | `backend/app/services/assistant_service.py`, `assistant_orchestrator.py`, `entity_resolver.py` | `README.md`, `docs/product/features.md#2`, `docs/architecture/README.md`, `docs/ml/README.md`, `docs/roadmap.md`, `docs/limitations.md`, `docs/case-study.md` |
| Game detail page (stats/ratings/reviews UI) | `docs/product/features.md#3-6` | `frontend/src/pages/GameDetail.tsx` | `docs/architecture/README.md` |
| Data pipeline / dataset provenance | `docs/data/README.md`, `docs/architecture/data-pipeline.md` | `data/raw/`, `data/processed/`, `scripts/build_master_dataset.py`, `scripts/ingest_master.py` | `README.md`, `docs/case-study.md`, `docs/setup/README.md`, `AGENTS.md` |
| Database schema (migrations) | `docs/data/README.md#schema` | `backend/alembic/versions/` | `docs/architecture/README.md` |
| Testing reality | `docs/engineering/testing.md` | `backend/test_*.py`, `frontend/package.json` | `README.md`, `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`, `docs/limitations.md`, `docs/case-study.md` |
| Setup / security posture | `docs/setup/README.md`, `docs/limitations.md` | `docker-compose.yml`, `backend/app/core/config.py`, `backend/app/main.py` | `README.md`, `AGENTS.md`, `backend/AGENTS.md`, `docs/architecture/README.md`, `docs/case-study.md` |

## Tracked cross-cutting facts

Specific claims that currently appear in multiple docs and are the most likely to change. If one of these changes, every file listed needs the same update; this is exactly the propagation step a partial doc-sync would otherwise miss.

| Fact (current state) | Appears in |
|---|---|
| Two Kaggle datasets, not three | `AGENTS.md`, `README.md`, `docs/case-study.md` |
| 9 recommendation model ids across 4 paradigms (not 10; `cf_svd` and the old `ensemble` model are deleted) | `README.md`, `AGENTS.md`, `docs/architecture/README.md`, `docs/product/features.md`, `docs/case-study.md`, `docs/ml/README.md`, `docs/ml/recommenders.md`, `docs/limitations.md` |
| `data/` is gitignored in full; nothing under it (`raw/`, `processed/`, `models/`) is tracked in git, and large files there are present on disk only | `docs/data/README.md`, `docs/architecture/data-pipeline.md`, `docs/ml/recommenders.md` |
| No automated test suite, no CI | `AGENTS.md`, `README.md`, `docs/engineering/testing.md`, `docs/limitations.md` |
| No auth, CORS wide open, hardcoded local DB credential default | `AGENTS.md`, `backend/AGENTS.md`, `docs/architecture/README.md`, `docs/setup/README.md`, `docs/case-study.md`, `docs/limitations.md` |
| `docker compose up` brings up an empty database (no seed step) | `AGENTS.md`, `README.md`, `docs/setup/README.md` |
| `conversation_id` accepted but unused; no multi-turn assistant memory | `README.md`, `docs/ml/README.md`, `docs/ml/assistant.md`, `docs/roadmap.md`, `docs/limitations.md` |
| Search evaluation results (MRR/NDCG/Recall, all 3 modes) are committed and Measured; recommender diversity and CF ranking-quality results are not yet committed, though both scripts can write them | `docs/case-study.md`, `docs/product/features.md`, `docs/ml/search.md`, `docs/ml/evaluation.md`, `docs/ml/recommenders.md`, `docs/limitations.md`, `docs/roadmap.md`, all recommender/search model cards |
| ABSA classification running in resumable chunks, not full eligible-corpus coverage yet (eligibility itself is already full-corpus) | `docs/product/features.md`, `docs/architecture/data-pipeline.md`, `docs/ml/absa.md`, `docs/ml/README.md`, `docs/limitations.md`, `docs/case-study.md`, `docs/roadmap.md`, `docs/ml/model-cards/absa-deberta.md` |
| Catalog filters: Designer/Artist/Publisher/Year Published (Production group), Players-before-Mechanic and Playtime-before-Complexity ordering | `docs/product/features.md` |
| Commit history spans five calendar days (2026-08-15 to 2026-08-19) | `docs/case-study.md`, `docs/limitations.md` |
| 21 migrations, 27 pipeline scripts, 18 API endpoints (the old `POST /api/games/compare` route is gone; comparison lives entirely in the assistant's `compare` intent) | `README.md`, `docs/case-study.md`, `docs/architecture/README.md` |
| BGG Family: 72 namespaces, about 4,200 values, modeled as `families` → `subfamilies` → `game_subfamilies` | `docs/data/README.md`, `docs/case-study.md`, `docs/product/features.md` |
| AI Assistant has 8 intents, all implemented (`browse`, `search`, `recommend`, `compare`, `get_game`, `get_reviews`, `get_aspects`, `unsupported`); the assistant LLM is `Qwen/Qwen3-4B-MLX-4bit`, same model as summarization | `README.md`, `docs/ml/assistant.md`, `docs/ml/model-cards/assistant-intent-parse.md`, `docs/setup/README.md`, `docs/product/features.md` |

## Not yet covered by this map

Any doc or claim added after this file's last update. Cross-references above were generated by grepping the doc set on 2026-08-19 for each fact's known phrasings; a claim stated in genuinely new wording won't have been caught automatically and may be missing here until the next update.
