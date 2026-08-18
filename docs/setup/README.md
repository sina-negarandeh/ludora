# Setup

## Prerequisites

- Docker and Docker Compose (for the containerized path)
- Python 3.10+ with [`uv`](https://docs.astral.sh/uv/) (for native backend/ML script execution)
- Node.js (for native frontend execution)
- Apple Silicon Mac, if you want the AI Assistant / Community Consensus features working locally (they call [Apple MLX](https://github.com/ml-explore/mlx) — see [Local LLM server](#local-llm-server) below). Everything else (catalog, search, recommendations, ABSA display) works without it, since those features read precomputed data.

## Quick start: Docker Compose + native backend

```bash
docker compose up -d
```

This starts three services (`docker-compose.yml`): `db` (`pgvector/pgvector:pg15`, port 5432, with a `pg_isready` healthcheck), `frontend` (Vite dev server, port 5173, `npm run dev -- --host 0.0.0.0`), and `pgadmin` (`dpage/pgadmin4`, port 5050, a database-inspection UI — login `admin@ludora.dev` / `admin`).

**There is no `backend` service — the backend always runs natively, never in Docker.** `SearchService` uses `mlx-embeddings` (Qwen3-Embedding-0.6B) for semantic search, and MLX is built on Apple's Metal/Accelerate frameworks — it only runs on macOS with Apple Silicon. A container built from a Linux base image (which is what `docker build` on this machine would produce) cannot install or run `mlx` at all; this isn't a missing-dependency bug, it's a platform constraint no Dockerfile can fix. Run it with:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

- Frontend: http://localhost:5173
- API + Swagger docs: http://localhost:8000/docs
- Postgres: `localhost:5432`
- pgAdmin: http://localhost:5050 (add a server with host `db`, port `5432`, user `ludora`)

**Important — this brings up an empty database.** Nothing here runs any seed/migration step. To get a working catalog you need to (1) apply the Alembic migrations, then (2) run the data pipeline. See [Populating the database](#populating-the-database) below. If you're working against a Postgres volume someone already populated, you can skip this.

## Native development

**Frontend** (Docker Compose already covers this by default, but native works too):
```bash
cd frontend
npm install
npm run dev
```

**Migrations** (from `backend/`, against whichever `DATABASE_URL` is active):
```bash
cd backend
uv run alembic upgrade head
```

## Populating the database

There is no single seed command — the data pipeline is a sequence of standalone scripts. Full script-by-script detail, including which raw files are actually read, is in [docs/architecture/data-pipeline.md](../architecture/data-pipeline.md). At minimum, in order:

All pipeline scripts import from the `app` package, so they need to run under the backend's `uv` project even though they live outside `backend/` — from the repo root, that means `uv run --project backend python scripts/<name>.py`, not a bare `uv run python`:

```bash
# 1. Build the master CSVs from data/raw/ (both Kaggle datasets — see docs/data/README.md)
uv run --project backend python scripts/build_master_dataset.py
uv run --project backend python scripts/build_interactions_dataset.py

# 2. Load Postgres
uv run --project backend python scripts/ingest_master.py

# 3. Enrichment (subdomain ranks, rating distributions, embeddings, search vectors)
uv run --project backend python scripts/populate_subdomain_ranks.py
uv run --project backend python scripts/populate_rating_distribution.py
uv run --project backend python scripts/update_embeddings.py
uv run --project backend python scripts/update_search_vectors.py
```

ABSA extraction, LLM summarization, and recommendation precompute are additional, optional stages layered on top — see [docs/architecture/data-pipeline.md](../architecture/data-pipeline.md#stage-4--absa-chain-sequential-each-step-depends-on-the-previous-ones-output) for the full chain. These commands are written from reading the scripts' source, not from a documented runbook that existed in the repo before this doc — if a command fails, check the script's argument parser (several accept `--` flags not shown here) before assuming the doc is wrong.

## Local LLM server

The AI Assistant and LLM summarization features call an OpenAI-compatible local server. The code defaults to `http://localhost:8080/v1` and model name `Qwen/Qwen3-30B-A3B-MLX-4bit` (both overridable via `OPENAI_BASE_URL`/`LLM_MODEL_NAME` environment variables — see `backend/app/services/assistant_service.py`, `summarization_service.py`). To run it (Apple Silicon only):

```bash
mlx_lm.server --model "Qwen/Qwen3-30B-A3B-MLX-4bit"
```

Without this running, every other feature (catalog, search, recommendations, ABSA aspect cards) still works — only the AI Assistant chat and any *new* Community Consensus generation require it. Existing `game_summaries` rows will still display without the LLM server running.

Since the backend runs natively (see above), it reaches this at the default `http://localhost:8080/v1` directly — no Docker networking indirection needed.

## Environment variables

| Variable | Default | Where |
|---|---|---|
| `DATABASE_URL` | Local dev connection string (see `backend/app/core/config.py`) | Backend, overridable via `.env` (not committed) or environment |
| `OPENAI_BASE_URL` | `http://localhost:8080/v1` | Backend (assistant + summarization) |
| `OPENAI_API_KEY` | `not-needed-for-local` (placeholder, not a real key) | Backend |
| `LLM_MODEL_NAME` | `Qwen/Qwen3-30B-A3B-MLX-4bit` | Backend |
| `VITE_API_URL` | `http://localhost:8000` | Frontend |
| `RAW_DATA_THRENJEN_DIR` | `data/raw/kaggle_datasets_threnjen_board-games-database-from-boardgamegeek` | Pipeline scripts (repo-root-relative; the default just works when run from the repo root, as documented above) |
| `RAW_DATA_JVANELTEREN_DIR` | `data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews` | Pipeline scripts, same default |
| `PROCESSED_DATA_DIR` | `data/processed` | Pipeline scripts, same default |

`backend/app/core/config.py` ships a hardcoded default database credential for local development. See [docs/limitations.md](../limitations.md) for why this needs to change before any non-local use — no credential values are reproduced in this documentation set.

## Verifying it worked

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/games?limit=1"
```

The second call should return a non-empty `items` array once the database has been populated.
