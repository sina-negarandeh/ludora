# backend/AGENTS.md

Scope: `backend/`. Read [../AGENTS.md](../AGENTS.md) first.

## Stack

Python >=3.10, managed with `uv`. FastAPI >=0.111, SQLAlchemy >=2.0.30, Alembic >=1.13.1, Pydantic >=2.7.4 + pydantic-settings, `psycopg[binary]` (psycopg3), PostgreSQL 15 + pgvector, `structlog` (request + assistant LLM-call logging, see `docs/architecture/README.md`). ML: `mlx-embeddings` (search embeddings, Qwen3-Embedding-0.6B on Apple MLX), sentence-transformers (used only by `scripts/count_clusters.py`'s review-dedup path), scikit-learn, `implicit` (ALS), fastText, HuggingFace `transformers`. LLM: [PydanticAI](https://ai.pydantic.dev/) (`pydantic-ai-slim[openai]`) for typed parsing against a local OpenAI-compatible server, not OpenAI's API, and [LangGraph](https://langchain-ai.github.io/langgraph/) for multi-step plan execution. Detail: `docs/ml/assistant.md`.

## Commands

This is the only way to run the API. There's no working Docker path, since `mlx-embeddings` (search embeddings) requires macOS/Apple Silicon and can't run in a Linux container. Detail: `docs/architecture/README.md#local-orchestration`.

```bash
uv sync                                          # install deps: main + dev group only (pytest, ruff, pyright) -- enough to run the API
uv sync --group ml                               # also pull in the offline pipeline's ML libraries (torch, transformers, mlflow, ...); needed for scripts/ and evaluation/
uv sync --all-groups                             # dev + ml together
uv run uvicorn app.main:app --reload             # run the API (from backend/)
uv run alembic upgrade head                      # apply migrations
uv run alembic revision --autogenerate -m "..."  # new migration, never hand-edit an applied one
uv run ruff check app/                           # lint (also runs in CI on every PR)
uv run pyright                                   # type check (also runs in CI on every PR)
uv run pytest                                    # backend/tests/ only -- see Testing below
uv run python evaluation/evaluate_search.py      # evaluation scripts (needs --group ml first; search results are committed, recommenders/CF aren't run yet)
```

The repo-root `Makefile` wraps the common ones (`make backend`, `make lint`, `make typecheck`, `make test`, `make check` for all three in CI's order); `make help` for the full list.

## Architecture

Routes never touch SQLAlchemy directly: `app/api/routes/*.py` calls `app/services/*.py`, which calls the ORM (`app/database/models.py`) or a recommender (`app/recommenders/`). Every new route needs a `response_model` and an OpenAPI `summary`/`description`.

Only two recommender classes exist, under `app/recommenders/collaborative/` (`ItemCosineRecommender`, `ALSRecommender`, subclassing `BaseRecommender`). The other model ids, popularity, TF-IDF, metadata, embedding, hybrid, graph Jaccard, DeepWalk, are procedural script logic, not classes. Detail: `docs/ml/recommenders.md`.

## Offline pipeline

All 27 ML/data scripts (build/ingest, ABSA, summarization, embeddings, search vectors, recommendation precompute) live in the repo-root `scripts/`, not under `backend/`. Confirm what a script actually writes before assuming it's live; several compute output nothing downstream reads. Run order: `docs/architecture/data-pipeline.md`.

## Local LLM

`AssistantService` and `SummarizationService` call `OPENAI_BASE_URL` (default `http://localhost:8080/v1`) / `LLM_MODEL_NAME` (default `Qwen/Qwen3-4B-MLX-4bit`), an OpenAI-SDK-compatible local server, with structured JSON output validated against a Pydantic schema. Everything else in the app works without it running.

## Testing

`ruff`, `pyright`, and `pytest` are dev dependencies (`uv sync`; excluded from a lean install via `uv sync --no-dev`) and all three run in CI on every PR (`.github/workflows/backend-ci.yml`). `pytest` is scoped to `backend/tests/` (`[tool.pytest.ini_options]`), a small, genuinely infra-free suite -- not the repo-root `test_*.py` scripts, which still print output instead of asserting, several of which require a live DB and/or the local LLM server pytest's default discovery would otherwise try to run for real. If you add real coverage for those, put shared fixtures in a `conftest.py` rather than hand-rolling DB setup per script. Detail: `docs/engineering/testing.md`.

## Security

CORS and the default DB credential: see boundaries in `../AGENTS.md`. Don't change either without asking.
