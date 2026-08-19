# backend/AGENTS.md

Scope: `backend/`. Read [../AGENTS.md](../AGENTS.md) first.

## Stack

Python >=3.10, managed with `uv`. FastAPI >=0.111, SQLAlchemy >=2.0.30, Alembic >=1.13.1, Pydantic >=2.7.4 + pydantic-settings, `psycopg[binary]` (psycopg3), PostgreSQL 15 + pgvector. ML: `mlx-embeddings` (search embeddings, Qwen3-Embedding-0.6B on Apple MLX), sentence-transformers (used only by `scripts/count_clusters.py`'s review-dedup path), scikit-learn, `implicit` (ALS), fastText, HuggingFace `transformers`. LLM: `openai` SDK against a local OpenAI-compatible server, not OpenAI's API.

## Commands

This is the only way to run the API. There's no working Docker path, since `mlx-embeddings` (search embeddings) requires macOS/Apple Silicon and can't run in a Linux container. Detail: `docs/architecture/README.md#local-orchestration`.

```bash
uv sync                                          # install deps
uv run uvicorn app.main:app --reload             # run the API (from backend/)
uv run alembic upgrade head                      # apply migrations
uv run alembic revision --autogenerate -m "..."  # new migration, never hand-edit an applied one
uv run python evaluation/evaluate_search.py      # evaluation scripts (search results are committed; recommenders/CF aren't run yet)
```

## Architecture

Routes never touch SQLAlchemy directly: `app/api/routes/*.py` calls `app/services/*.py`, which calls the ORM (`app/database/models.py`) or a recommender (`app/recommenders/`). Every new route needs a `response_model` and an OpenAPI `summary`/`description`.

Only two recommender classes exist, under `app/recommenders/collaborative/` (`ItemCosineRecommender`, `ALSRecommender`, subclassing `BaseRecommender`). The other model ids, popularity, TF-IDF, metadata, embedding, hybrid, graph Jaccard, DeepWalk, are procedural script logic, not classes. Detail: `docs/ml/recommenders.md`.

## Offline pipeline

All 27 ML/data scripts (build/ingest, ABSA, summarization, embeddings, search vectors, recommendation precompute) live in the repo-root `scripts/`, not under `backend/`. Confirm what a script actually writes before assuming it's live; several compute output nothing downstream reads. Run order: `docs/architecture/data-pipeline.md`.

## Local LLM

`AssistantService` and `SummarizationService` call `OPENAI_BASE_URL` (default `http://localhost:8080/v1`) / `LLM_MODEL_NAME` (default `Qwen/Qwen3-4B-MLX-4bit`), an OpenAI-SDK-compatible local server, with structured JSON output validated against a Pydantic schema. Everything else in the app works without it running.

## Testing

No `pytest` is installed; `test_*.py` scripts print output, they don't assert, and several require a live DB and/or the local LLM server. If you add real coverage, add `pytest` as a dev dependency and put shared fixtures in a `conftest.py` rather than hand-rolling DB setup per script. Detail: `docs/engineering/testing.md`.

## Security

CORS and the default DB credential: see boundaries in `../AGENTS.md`. Don't change either without asking.
