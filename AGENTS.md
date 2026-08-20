# AGENTS.md

Ludora is a board-game discovery web app: FastAPI + PostgreSQL/pgvector backend, React 19 + TypeScript frontend, offline Python ETL/ML pipeline, built on two merged Kaggle [BoardGameGeek](https://boardgamegeek.com/) datasets, with hybrid search, a 9-model recommendation engine, aspect-based sentiment analysis, and a local-LLM assistant.

This file covers what's true across the whole repo. Also read the nested file for whichever side you're touching:

- [backend/AGENTS.md](backend/AGENTS.md): FastAPI, SQLAlchemy, the ML pipeline, Python conventions
- [frontend/AGENTS.md](frontend/AGENTS.md): React, TypeScript, component conventions

## Orient yourself

| Question | Doc |
|---|---|
| What does this app do, end to end? | `docs/case-study.md` |
| System design, service boundaries, request flow | `docs/architecture/README.md` |
| Offline pipeline: what script runs when | `docs/architecture/data-pipeline.md` |
| Dataset provenance, schema, taxonomy, glossary | `docs/data/README.md` |
| How search / recommenders / ABSA / assistant work | `docs/ml/README.md` |
| What's measured vs. observed vs. not evaluated | `docs/ml/evaluation.md` |
| Every known gap and its fix priority | `docs/roadmap.md`, `docs/limitations.md` |

Link to the relevant doc instead of re-explaining it here.

## Repo map

```
backend/          FastAPI app (app/), evaluation (evaluation/)
frontend/          React 19 + TypeScript + Vite
data/raw/          Two Kaggle datasets, as downloaded; do not hand-edit
data/processed/    Pipeline output (master_*.csv, model artifacts); regenerable, do not hand-edit
scripts/           All offline ETL/ML pipeline scripts, in one place; run via `uv run --project backend python scripts/<name>.py`
docs/              Documentation set (see table above)
```

## Run it

```bash
docker compose up -d
```

Brings up Postgres, the frontend, and pgAdmin, not the backend. The backend must run natively (`cd backend && uv run uvicorn app.main:app --reload`): `SearchService` uses `mlx-embeddings` for semantic search, and MLX only runs on macOS/Apple Silicon, so it can't be containerized on the Linux base image Docker would use.

The database starts empty; nothing here seeds it. Populate it via the pipeline in `docs/setup/README.md` before expecting real data from any endpoint.

A root `Makefile` wraps the commands above plus lint/typecheck/test (`make help` for the full list, `make check` runs the same `ruff` → `pyright` → `pytest` sequence as CI).

## Known debt

Backend CI (`.github/workflows/backend-ci.yml`) runs `ruff` + `pyright` + a small, genuinely infra-free `pytest` suite (`backend/tests/`) on every PR; the original manual `test_*.py` scripts are still print-only and unconverted, and don't run in CI. Frontend has no CI and no test framework at all. This is tracked debt, not steady state; full list and priority in `docs/roadmap.md`. Don't add to it; see the standards below for the bar on new work.

## Standards for new work

- Grep for a filename across the whole repo before adding a script. Do not create a second file with a name that already exists elsewhere.
- Don't claim a recommendation model id is served without checking `RecommendationService.get_recommendations()` against `docs/ml/recommenders.md`; each of the 9 ids routes to its own live query or its own precomputed `game_recommendations` rows.
- New backend routes and new pipeline/recommender scripts need a way to verify they work: a request check, a rerunnable script, a before/after diff. See "Verify your work."
- Match existing terminology exactly: `docs/data/README.md#glossary` (two source datasets, nine recommendation model ids, "Community Consensus").
- If a change alters a capability's status or behavior, check `docs/maintenance/coverage-map.md` for every doc that claims something about it and update them together. Don't fix the first doc you find and stop.
- Don't extend the no-auth, open-CORS, hardcoded-local-credential pattern to new code, and don't change it without asking; auth and deploy hardening are a larger decision this file doesn't own.

## Verify your work

There is no test suite to lean on. A change counts as done once you've actually run one of these and read the output, not before:

- Backend: exercise the endpoint (`uv run --project backend python backend/test_routes.py`, or `curl`) against a running server.
- Frontend: `npm run build` (strict `tsc -b`) passes with zero errors; `npm run lint` passes.
- Docs: every internal link, anchor, and image path you touched resolves; every `file.py:123` reference points at real code.

## Commit messages: Conventional Commits

```
<type>(<scope>): <imperative summary, no trailing period>
```

- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`
- Scope (optional): `backend`, `frontend`, `ml`, `data`, `docs`, `scripts`
- Body (optional): the *why*, not a restatement of the diff

Examples: `feat(ml): precompute cf_als recommendations to game_recommendations`, `fix(frontend): guard GameReviews against an empty language_breakdown`.

## Boundaries

- MUST NOT commit secrets or credential values, including the existing `DATABASE_URL` default in `backend/app/core/config.py`.
- MUST NOT force-push or rewrite published git history.
- MUST NOT edit an already-applied Alembic migration in `backend/alembic/versions/`; add a new one instead.
- SHOULD ask before deleting or regenerating anything under `data/raw/` or `data/processed/`; slow and expensive to rebuild.
- SHOULD ask before changing CORS, auth, or deployment configuration.
