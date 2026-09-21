# AGENTS.md

Ludora is a board-game discovery web app. It has a FastAPI + PostgreSQL/pgvector backend, a React 19 + TypeScript frontend, and an offline Python ETL/ML pipeline. It is built on two merged Kaggle [BoardGameGeek](https://boardgamegeek.com/) datasets.

It provides hybrid search, a 9-model recommendation engine, aspect-based sentiment analysis, and a local-LLM assistant.

This file covers what's true across the whole repo. Also read the nested file for whichever side you're touching:

- [backend/AGENTS.md](backend/AGENTS.md): FastAPI, SQLAlchemy, the ML pipeline, Python conventions
- [frontend/AGENTS.md](frontend/AGENTS.md): React, TypeScript, component conventions
- [ios/AGENTS.md](ios/AGENTS.md): Swift, SwiftUI, the LudoraKit package, iOS conventions

## Orient yourself

| Question | Doc |
|---|---|
| What does this app do, end to end? | `README.md`, then `docs/README.md` |
| System design, service boundaries, request flow | `docs/architecture/README.md` |
| Offline pipeline: what script runs when | `docs/architecture/data-pipeline.md` |
| Dataset provenance, schema, taxonomy, glossary | `docs/data/README.md` |
| How search / recommenders / ABSA / assistant work | `docs/ml/` |
| What each client screen looks like | `frontend/README.md`, `ios/README.md` |
| What the native iOS client covers, and what it leaves out | `ios/AGENTS.md` |

Link to the relevant doc instead of re-explaining it here.

## Repo map

```
backend/          FastAPI app (app/), evaluation (evaluation/)
frontend/          React 19 + TypeScript + Vite
ios/               Native SwiftUI client (LudoraKit package + app target)
data/raw/          Two Kaggle datasets, as downloaded; do not hand-edit
data/processed/    Pipeline output (master_*.csv, model artifacts); regenerable, do not hand-edit
scripts/           All offline ETL/ML pipeline scripts, in one place; run via `uv run --project backend python scripts/<name>.py`
scripts/tools/     Repo tooling, kept out of the pipeline count above (e.g. `check_docs.py`)
docs/              Documentation set (see table above)
```

## Run it

```bash
docker compose up -d
```

This starts Postgres, the frontend, and pgAdmin, but not the backend. The backend must run natively: `cd backend && uv run uvicorn app.main:app --reload`. `SearchService` uses `mlx-embeddings` for semantic search, and MLX only runs on macOS/Apple Silicon. Docker would use a Linux base image, so the backend cannot be containerized.

The database starts empty. Nothing here seeds it. Populate it via the pipeline in `docs/setup/README.md` before expecting real data from any endpoint.

A root `Makefile` wraps the commands above plus lint/typecheck/test (`make help` for the full list, `make check` runs the same `ruff` → `pyright` → `pytest` sequence as CI).

## Known debt

Backend CI (`.github/workflows/backend-ci.yml`) runs `ruff` + `pyright` + a small, genuinely infra-free `pytest` suite (`backend/tests/`) on every PR. The original manual `test_*.py` scripts are still print-only and unconverted, and don't run in CI. Frontend has no CI and no test framework at all.

This is tracked debt, not steady state. Each doc carries its own **Known limitations** section. Don't add to it. See the standards below for the bar on new work.

## Standards for new work

- Grep for a filename across the whole repo before adding a script. Do not create a second file with a name that already exists elsewhere.
- Don't claim a recommendation model id is served without checking `RecommendationService.get_recommendations()` against `docs/ml/recommenders.md`. Each of the 9 ids routes to its own live query or its own precomputed `game_recommendations` rows.
- New backend routes and new pipeline/recommender scripts need a way to check they work: a request check, a rerunnable script, a before/after diff. See "Check your work."
- Match existing terminology exactly: `docs/data/README.md#glossary` (two source datasets, nine recommendation model ids, "Community Consensus").
- Docs carry **why and how to run it**, not a narration of what the code does. A number in a doc must be one that was measured, and the doc says how it was measured.
- Each fact lives in exactly one doc. If you find yourself updating the same claim in two files, consolidate it instead. `make docs-check` enforces this for the derivable counts.
- Don't extend the no-auth, open-CORS, hardcoded-local-credential pattern to new code, and don't change it without asking. Auth and deploy hardening are a larger decision this file doesn't own.

## Check your work

There is no test suite to lean on. A change counts as done once you've actually run one of these and read the output, not before:

- Backend: exercise the endpoint (`uv run --project backend python backend/test_routes.py`, or `curl`) against a running server.
- Frontend: `npm run build` (strict `tsc -b`) passes with zero errors. `npm run lint` passes.
- Docs: every internal link, anchor, and image path you touched resolves. Every `file.py:123` reference points at real code.

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
- MUST NOT edit an already-applied Alembic migration in `backend/alembic/versions/`. Add a new one instead.
- SHOULD ask before deleting or regenerating anything under `data/raw/` or `data/processed/`. Both are slow and expensive to rebuild.
- SHOULD ask before changing CORS, auth, or deployment configuration.
