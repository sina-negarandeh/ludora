# Testing

**Status: a real but minimal automated suite runs in CI (lint + type check + 2 infra-free smoke tests); the original print-only scripts below are unconverted and don't run in CI.** Worth stating both halves plainly, since the file layout (two different sets of files named `test_*.py`, in two different directories) could otherwise mislead a reader either way.

## What runs in CI (`.github/workflows/backend-ci.yml`)

On every PR touching `backend/`, in order: `ruff check app/` (lint), `pyright` (type check, `basic` mode, scoped to `app/`), then `pytest` (scoped to `backend/tests/` via `[tool.pytest.ini_options]`, not the repo root -- see why below).

`backend/tests/test_app_smoke.py` is the entire real automated suite today: two tests, both infra-free (no live DB, no local LLM server), using `TestClient` to hit `/health` and `/openapi.json`. Deliberately minimal but genuine -- it catches a broken import, a broken route/schema definition, or an app startup error, which is exactly what a GitHub-hosted Linux runner *can* check. It can't run anything requiring `mlx-embeddings` (Apple Silicon only, see `backend/AGENTS.md`) or a seeded Postgres instance, which is also why the CI job installs only the `dev` dependency group (`uv sync`, no `--group ml`) -- the offline pipeline's heavy ML libraries aren't needed for any of this.

Neither test touches search or embeddings, but `from app.main import app` alone used to fail on Linux anyway: `app/core/embeddings.py` imported `mlx_embeddings` at module top-level, which imports `mlx.core`, which requires Apple Silicon (`libmlx.so`) to even *import*, not just run. Fixed by moving that one import inside the function that actually calls it (`_get_model()`) -- not an ML-testing workaround, just an eager import that had no reason to run before it was needed, confirmed directly: after the fix, importing `app.main` loads zero `mlx*` modules unless something actually calls `encode()`.

Pyright and ruff both run clean today; pyright has one deliberate, tracked exception -- see [Known limitation: SQLAlchemy Column typing](#known-limitation-sqlalchemy-column-typing-under-pyright) below.

## Backend "tests" (all print-based scripts, not pytest suites)

| File | Requires | Uses `assert`? | How it actually runs |
|---|---|---|---|
| `backend/test_api.py` | A live server already running on `:8000` | No | `python test_api.py`, hits `GET /api/games?limit=2` via `urllib`, prints the count |
| `backend/test_games.py` | A live DB | No; internal exceptions are caught and printed via `traceback.print_exc()`, then swallowed | `python test_games.py`. Because the exception is swallowed, `pytest` would report this file's `test()` function as passing even if the DB call fails internally. |
| `backend/test_routes.py` | A live/seeded DB, imports the app in-process via `TestClient` | No | `python test_routes.py`, fires 7 requests, prints only status codes, no assertions on body content; has no `test_*` function, so `pytest test_routes.py` would collect 0 tests |
| `backend/test_assistant.py` | A local LLM server, degrades gracefully with a caught exception if absent | No | `python test_assistant.py` |
| `backend/test_assistant_retry.py` | A local LLM server, blocks forever (`while True`) if one never starts | No | `python test_assistant_retry.py`, despite the name, tests server-readiness polling and a single parse call, not the retry-on-malformed-completion logic `AssistantService.parse_query()` actually has |
| `backend/test_orchestrator.py` | A live DB *and* a live local LLM server | No | `python test_orchestrator.py`, a handful of hardcoded natural-language queries through the full chat pipeline, prints intent and data shape |

None of these six files are wired into CI, and `[tool.pytest.ini_options]`'s `testpaths = ["tests"]` (see above) means plain `pytest`/`uv run pytest` won't even collect them by default anymore -- deliberately: three of the six need a live DB and/or LLM server pytest's default discovery would otherwise try to run for real, and `test_assistant_retry.py` is documented above to block forever without one. Run one directly by name (`uv run python test_orchestrator.py`) when you actually have that infra up.

**What this means concretely**: a regression that changes a response shape, breaks a query, or silently swaps in wrong data would not be caught by anything currently in the repository unless a developer manually runs these scripts and reads the printed output.

## Frontend

No test framework is installed: `frontend/package.json` has no `vitest`, `jest`, `@testing-library/react`, `playwright`, or `cypress` in dependencies or devDependencies, and there's no `test` script. Linting exists (`oxlint`, `frontend/.oxlintrc.json`, enforcing `react/rules-of-hooks` and a constant-export allowance), and `frontend/tsconfig.app.json` runs a strict TypeScript configuration (`noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `erasableSyntaxOnly`). Type-checking via `tsc -b` (part of `npm run build`) is the closest thing to an automated correctness check on the frontend, and it only catches type errors, not behavioral regressions.

## Known limitation: SQLAlchemy Column typing under pyright

`app/database/models.py` uses SQLAlchemy's legacy `Column(...)` declarative style, not 2.0's typed `Mapped[]`/`mapped_column()`. Pyright can't distinguish an instance attribute (`game.rank`, an `int` at runtime) from the class-level `Column` descriptor, so it reports every read or write of a model attribute as `Column[X]` instead of `X`. Confirmed as false positives, not real bugs, by direct runtime behavior throughout the session that added this CI setup.

Three files dense with model-attribute plumbing (`app/services/aspect_service.py`, `summarization_service.py`, `recommendation_service.py`) carry a file-level `# pyright: report...=false` comment for exactly the rule categories this pattern triggers, each with the same explanatory comment pointing back here. Deliberately scoped to those three files, not project-wide, so a real error of the same rule type elsewhere still surfaces. Two more one-line suppressions exist for the standard FastAPI/Pydantic pattern of returning ORM objects or dicts through a `response_model` schema with `from_attributes=True` (`app/api/routes/games.py`, `recommendations.py`).

The real fix is migrating every model class in `models.py` to `Mapped[]`, which SQLAlchemy 2.0 natively supports. Not done as part of adding pyright: it's a genuinely separate, sizable task (touches every model class, and once pyright can see real types there, it may surface *new* findings elsewhere that `Column`'s untyped nature was hiding). Tracked in [docs/roadmap.md](../roadmap.md).

## Known limitation: four files excluded from pyright entirely

`app/core/mlflow_utils.py`, `app/core/review_quality.py`, and `app/recommenders/collaborative/{als,item_cosine}.py` live under `app/` (shared code the offline pipeline's scripts import directly) but are never imported by the live API, and import `ml`-group-only packages (`mlflow`, `nltk`, `scikit-learn`, `implicit`, `pandas`) that a lean `uv sync` deliberately doesn't install -- see the `ml` group's own comment in `backend/pyproject.toml`. CI runs `pyright` against exactly that lean install, not `--all-groups`, so without excluding them, every one of those imports fails as `reportMissingImports`.

Listed explicitly in `[tool.pyright].exclude`, not caught during development: local runs had `--all-groups` synced throughout, so this only surfaced as a real CI failure (11 errors, a fresh Ubuntu runner) after the first push. Fixed by excluding the four files rather than installing `ml` in CI, which would reverse the lean-CI design for the sake of type-checking four files peripheral to the live API (`torch`/`transformers` alone dominate that install). Two per-line `pyright: ignore` comments in `als.py`/`item_cosine.py` for genuine third-party stub gaps (pandas/scipy-sparse operations missing from their stubs) were removed as part of this -- inert once the whole file is excluded, and a stale comment claiming pyright still checks part of a file it doesn't scan at all is worse than no comment.

## What does exist as a quality signal

- **`ruff` and `pyright` on the backend**, both clean and enforced in CI on every PR (see above).
- **Strict TypeScript** across the frontend, which catches an entire class of prop/shape mismatches at build time even without a test suite.
- **Pydantic v2 response models** on every backend route, which catch response-shape errors at serialization time (a malformed object raises rather than silently returning bad JSON).
- **The evaluation scripts** (`backend/evaluation/`) are manual harnesses, not regression tests: for search, results are committed and reproducible, which makes them a real quality signal; for recommenders and CF, the script exists but hasn't been run to produce a committed result yet. See [docs/ml/evaluation.md](../ml/evaluation.md).

## Highest-value next steps (not started)

1. Convert the six DB/LLM-dependent scripts above into real `pytest` tests under `backend/tests/`, using a fixture (`conftest.py`) for a test database instead of a hand-seeded local Postgres instance, and a way to skip (not hang on) the LLM-dependent ones when no server is running. Only then would CI plausibly ever run them; a GitHub-hosted runner still can't provide `mlx-embeddings` regardless (Apple Silicon only).
2. Migrate `app/database/models.py` to SQLAlchemy 2.0's `Mapped[]` typed columns, removing the scoped pyright suppressions above. See [docs/roadmap.md](../roadmap.md).
3. Add `vitest` and React Testing Library for at least the filter/sort logic in `GamesList.tsx` and the gauge math in `GameDetail.tsx`, both pure enough to unit test without a running backend.

## Related code

- `backend/tests/test_app_smoke.py` (real, CI-run) and `backend/test_api.py`, `test_games.py`, `test_routes.py`, `test_assistant.py`, `test_assistant_retry.py`, `test_orchestrator.py` (print-only, not CI-run)
- `backend/pyproject.toml` (`[dependency-groups]`, `[tool.ruff]`, `[tool.pyright]`, `[tool.pytest.ini_options]`)
- `.github/workflows/backend-ci.yml`
- `frontend/package.json`, `frontend/.oxlintrc.json`, `frontend/tsconfig.app.json`
