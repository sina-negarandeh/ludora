# Architecture

Ludora is two systems joined by PostgreSQL: an **offline Python pipeline** (27 scripts) that turns raw CSVs into populated tables and precomputed recommendation/ABSA rows, and a **stateless FastAPI service** that reads those tables at request time. Almost nothing is computed live except lexical/semantic search and four of the ten recommendation model IDs (see [Known limitation](#known-limitation-four-recommendation-ids-collapse-to-one-query) below).

For the step-by-step data pipeline (what runs in what order, what each script reads/writes), see [data-pipeline.md](data-pipeline.md). For dataset provenance and schema, see [docs/data/README.md](../data/README.md).

## System diagram

```mermaid
flowchart LR
    subgraph Offline["Offline pipeline — run manually, in order"]
        RAW["Raw CSVs\ndata/raw/**"] --> MERGE["build_master_dataset.py\nbuild_interactions_dataset.py"]
        MERGE --> INGEST["ingest_master.py\nCOPY into Postgres"]
        INGEST --> ENRICH["Enrichment scripts\nsubdomain ranks · rating distributions\nembeddings · search vectors · language ID"]
        ENRICH --> ABSA["ABSA chain\nabsa_filter -> generate_stratified_sample\n-> absa_extract_hf -> absa_aggregate"]
        ENRICH --> RECS["Recommendation precompute\ntrain_svd · precompute_recommendations\nprecompute_cf_recommendations\nprecompute_graph_recommendations"]
        ABSA --> SUMM["generate_summaries.py\ncalls local LLM"]
    end

    subgraph DB["PostgreSQL 15 + pgvector"]
        TBLS[("games · ratings · reviews\nreview_aspects · game_aspect_aggregates\ngame_recommendations · game_summaries")]
    end

    INGEST --> TBLS
    ENRICH --> TBLS
    ABSA --> TBLS
    RECS --> TBLS
    SUMM --> TBLS

    subgraph Online["Online system — FastAPI, stateless, no auth"]
        API["Routes\ngames · search · metadata\nrecommendations · assistant"]
        SVC["Service layer\nGameService · SearchService · RecommendationService\nAspectService · AssistantOrchestrator · EntityResolver"]
        API --> SVC
    end

    TBLS <--> SVC
    SVC -- "intent parsing + summarization\n(OpenAI-compatible calls)" --> MLX["Local MLX server\nQwen3-30B-A3B-MLX-4bit"]

    FE["React 19 frontend\nGamesList · GameDetail · AssistantDrawer"] -- "HTTP (axios / fetch)" --> API
```

## Layered backend design

The backend follows a **routes → services → (ORM models / recommenders)** layering, introduced deliberately in commit `c89a915` ("Refactor backend architecture to Layered Design (Services + Resource API)"). Route handlers never touch SQLAlchemy directly — each instantiates a service class and returns its result through a Pydantic `response_model`. Every route (except `/health`) carries an explicit OpenAPI `summary` and `description`, added in commit `df892ef`.

### API surface — 19 endpoints across 6 files

| File → mount | Endpoints |
|---|---|
| `backend/app/main.py` | `GET /health` |
| `backend/app/api/routes/games.py` → `/api/games` | `GET /`, `POST /compare`, `GET /{bgg_id}`, `GET /{bgg_id}/reviews`, `GET /{game_id}/aspects` |
| `backend/app/api/routes/search.py` → `/api/search` | `POST /` |
| `backend/app/api/routes/metadata.py` → `/api` | `GET /subdomains`, `/categories`, `/themes`, `/families`, `/mechanics`, `/designers`, `/publishers`, `/artists` |
| `backend/app/api/routes/recommendations.py` → `/api` | `GET /recommendation-models`, `GET /games/{game_id}/recommendations` |
| `backend/app/api/routes/assistant.py` → `/api/assistant` | `POST /parse`, `POST /chat` |

Full request/response shapes are in the live Swagger UI (`http://localhost:8000/docs` once running) — this doc does not duplicate the OpenAPI spec.

**Frontend↔backend surface gaps** (confirmed by reading both sides): `GET /api/artists`, `GET /api/recommendation-models`, and `POST /api/games/compare` are implemented and reachable but never called anywhere in `frontend/src/`. `GET /api/games/{id}/aspects` *is* called from `GameDetail.tsx`, but with an inline `axios` call rather than through the shared `frontend/src/api/games.ts` client — a small consistency gap, not a functional bug.

### Service layer

| Service (`backend/app/services/`) | Responsibility | Called by |
|---|---|---|
| `GameService` | Catalog list/detail/compare | `routes/games.py`, `AssistantOrchestrator` |
| `SearchService` | Lexical, semantic, hybrid (RRF) search + shared filter logic | `routes/search.py`, `AssistantOrchestrator`, `EntityResolver` |
| `RecommendationService` | Routes 10 model IDs to either a live pgvector query or a precomputed-table read | `routes/recommendations.py`, `AssistantOrchestrator` |
| `ReviewService` | Paginated review browsing, language/rating filters | `routes/games.py` |
| `AspectService` | ABSA aggregate lookup per game | `routes/games.py` |
| `MetadataService` | Subdomain/category/theme/family/mechanic/designer/publisher/artist lookups | `routes/metadata.py` |
| `AssistantService` | Calls the local LLM, validates output against `ParsedIntent` | `routes/assistant.py` |
| `AssistantOrchestrator` | Dispatches a parsed intent to the service above matching it | `routes/assistant.py` |
| `EntityResolver` | Resolves fuzzy game/category/theme/mechanic names via `SearchService` lexical search + class-level caches | `AssistantOrchestrator` |
| `SummarizationService` | Builds the "Community Consensus" paragraph from ABSA aggregates via the local LLM | **Offline only** — `scripts/generate_summaries.py`; no live route calls it |

Full detail on the ML-relevant services (`SearchService`, `RecommendationService`, `AssistantService`/`AssistantOrchestrator`, `SummarizationService`) is in [docs/ml/](../ml/README.md), not repeated here.

## Request flows

**Browse** — `GamesList.tsx` → `GET /api/games` (filters: subdomains/categories/families/mechanics/exact_players/min·max_players/min·max_weight/min·max_playtime; sort: rank/rating/year/complexity/name) → `GameService.get_games()` → SQLAlchemy with `selectin` eager loading for relationships → `PaginatedGames` → `GameCard` grid.

**Search** — search bar → `POST /api/search` with a `mode` of `lexical`/`semantic`/`hybrid` → `SearchService.search()`. Lexical and semantic candidate sets (100 each) are fused with Reciprocal Rank Fusion (`k=60`), then `apply_game_filters()` runs on the fused set, then results are paginated. See [docs/ml/search.md](../ml/search.md) for the exact formula.

**Game detail** — `GameDetail.tsx` mounts and independently fires `GET /api/games/{id}` (detail + manually-attached `GameSummary`), `GET /api/games/{id}/recommendations?model=hybrid` (default model), `GET /api/games/{id}/reviews` (paginated, 4/page), and `GET /api/games/{id}/aspects`. These are four independent requests, not one aggregated payload.

**AI Assistant** — `AssistantDrawer.tsx` → `POST /api/assistant/chat` → `AssistantService.parse_query()` sends the message plus the `ParsedIntent` JSON schema to the local LLM (`response_format={"type":"json_object"}`, one attempt, no retry) → `AssistantOrchestrator.execute()` pattern-matches on `intent.intent` and calls `GameService`/`SearchService`/`RecommendationService`/`EntityResolver` → `AssistantResponse` rendered by `AssistantMessageBubble`. See [docs/ml/assistant.md](../ml/assistant.md) for intent coverage and known gaps.

**Offline pipeline** — see [data-pipeline.md](data-pipeline.md) for the full script-by-script trace and run order.

## Known limitation: four recommendation IDs collapse to one query

`RecommendationService.get_recommendations()` has a single branch — `if model in ["embedding", "metadata", "tfidf", "hybrid"]` — that routes **all four** of those model IDs to the identical live query: `GameEmbedding.embedding.cosine_distance(source_embedding.embedding)` (filtered to the currently-configured model). Offline scripts (`scripts/precompute_content_recommendations.py`) do compute genuinely distinct TF-IDF, metadata-similarity, and weighted-hybrid scores and write them to `game_recommendations`, but the service's `if` branch intercepts those four model IDs before the code path that would read those precomputed rows is ever reached — so those rows are written but never served. Only `popularity` (live rank query) and the five collaborative/graph model IDs (`cf_item_cosine`, `cf_svd`, `cf_als`, `graph_jaccard`, `deepwalk`) actually read from the precomputed `game_recommendations` table. Full detail is in [docs/ml/recommenders.md](../ml/recommenders.md).

## Configuration and security posture

The app has **no authentication layer** — no login, no session, no auth dependency on any route. CORS is wide open (`allow_origins=["*"]`, `backend/app/main.py`, commented `# For development`). The only configured setting, `DATABASE_URL` (`backend/app/core/config.py`), has a hardcoded local-development default credential. This is appropriate for a portfolio project run locally but would need to change before any public deployment — full detail in [docs/limitations.md](../limitations.md); no credential values are reproduced in any doc.

## Local orchestration

`docker-compose.yml` defines three services: `db` (`pgvector/pgvector:pg15`, port 5432, `pg_isready` healthcheck), `frontend` (built from `frontend/Dockerfile`, port 5173, Vite dev server), and `pgadmin` (`dpage/pgadmin4`, port 5050, a database-inspection UI with no bearing on the app itself). The frontend reaches the backend via an absolute `VITE_API_URL`, not a dev-server proxy.

**The backend is deliberately not a Compose service.** It was originally containerized (`backend/Dockerfile`, `python:3.12-slim`), but `SearchService` now depends on `mlx-embeddings` for semantic search (Qwen3-Embedding-0.6B), and MLX is built on Apple's Metal/Accelerate frameworks — it has no Linux implementation at all, so no `python:3.12-slim`-based image can ever install or run it, rebuild or not. `backend/Dockerfile` was removed rather than left as dead, broken config. The backend runs natively instead: `cd backend && uv run uvicorn app.main:app --reload`. See [docs/setup/README.md](../setup/README.md) for verified run commands.
