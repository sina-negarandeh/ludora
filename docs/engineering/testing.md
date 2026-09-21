# Testing

**Status: a real but minimal automated suite runs in CI. The original print-only scripts are unconverted and do not run**. Both halves matter, because the layout puts two different sets of files named `test_*.py` in two different directories and could mislead a reader either way.

## What runs in CI

On every PR touching `backend/`: `ruff check app/`, then `pyright` (basic, scoped to `app/`), then `pytest` scoped to `backend/tests/`. Both linters are clean today, with one tracked exception below.

**Everything in `backend/tests/` is infra-free**, no live DB and no local LLM server. That is the whole reason a GitHub-hosted Linux runner can run all of it, and it is why the CI job installs only the `dev` group. The offline pipeline's heavy ML libraries are not needed to check that the app imports and the state machine behaves.

- `test_app_smoke.py` hits `/health` and `/openapi.json` through `TestClient`. Deliberately minimal but genuine: it catches a broken import, a broken route or schema definition, and an app startup error.
- `test_plan_executor.py` drives the assistant's recovery cycle with a fake orchestrator, no HTTP layer at all. Why that cycle specifically: [assistant.md](../ml/assistant.md).
- `test_search_query_normalization.py` and `test_distributions.py` pin pure functions.

### The import that broke Linux CI

Neither smoke test touches search, but `from app.main import app` alone used to fail on Linux. `app/core/embeddings.py` imported `mlx_embeddings` at module top level, which imports `mlx.core`, which needs Apple Silicon to even *import*, not just to run.

Fixed by moving that one import inside the function that calls it. **This was not an ML-testing workaround.** It was an eager import with no reason to run before it was needed. Checked directly: after the fix, importing `app.main` loads zero `mlx*` modules unless something calls `encode()`.

## The six print-only scripts

`backend/test_api.py`, `test_games.py`, `test_routes.py`, `test_assistant.py`, `test_assistant_retry.py`, `test_orchestrator.py`. **None has a single `assert`.** They print and you read the output.

Three specific traps:

- **`test_games.py` swallows its own exceptions** through `traceback.print_exc()`, so `pytest` would report it passing even when the DB call fails.
- **`test_routes.py` has no `test_*` function**, so `pytest` would collect 0 tests from it.
- **`test_assistant_retry.py` blocks forever** (`while True`) if no LLM server ever starts. Despite its name it tests readiness polling, not the retry-on-malformed-completion logic that `parse_query()` actually has.

`testpaths = ["tests"]` means plain `pytest` will not collect any of them, which is deliberate given the above. Run one directly by name when you have the infra up.

**What this means concretely: nothing in the repository catches a regression today.** Not a changed response shape, not a broken query, not silently wrong data. Someone has to run these by hand and read the output.

## Frontend

No test framework is installed and no `test` script exists. `oxlint` and strict `tsc -b` (via `npm run build`) are the only automated checks, and they catch type errors, not behavioral regressions.

## Known limitation: SQLAlchemy `Column` typing under pyright

`app/database/models.py` uses the legacy `Column(...)` style rather than 2.0's `Mapped[]`. Pyright cannot tell an instance attribute (`game.rank`, an `int` at runtime) from the class-level descriptor, so it reports every model-attribute read as `Column[X]` instead of `X`. Checked against runtime behaviour as false positives, not real bugs.

Three service files dense with model-attribute plumbing carry a file-level suppression for exactly those rule categories, each with a comment pointing here. **Scoped to those three deliberately**, so the same rule still fires elsewhere. Two more one-line suppressions cover the standard FastAPI pattern of returning ORM objects through a `response_model` with `from_attributes=True`.

The real fix is migrating every model class to `Mapped[type] = mapped_column(...)`, then removing the suppressions and re-running pyright to catch whatever the untyped style was hiding. That is a genuinely separate, sizable task.

## Known limitation: four files excluded from pyright

`app/core/mlflow_utils.py`, `app/core/review_quality.py`, and `app/recommenders/collaborative/{als,item_cosine}.py` sit under `app/` as shared code the pipeline scripts import directly. The live API never imports them, and they need `ml`-group packages that a lean `uv sync` does not install. CI runs pyright against exactly that lean install, so every one of those imports failed as `reportMissingImports`.

**This surfaced as a real CI failure after the first push**, 11 errors on a fresh Ubuntu runner. Local runs had `--all-groups` synced throughout, so it was invisible until then.

Excluding the four files was the fix rather than installing `ml` in CI. That install would reverse the lean-CI design, to type-check four files peripheral to the live API, and `torch` and `transformers` alone dominate it. Two per-line `pyright: ignore` comments inside those files came out at the same time. They are inert once the whole file is excluded. A comment claiming pyright still checks part of a file it does not scan is worse than no comment.

## What does count as a quality signal

- `ruff` and `pyright`, clean and enforced on every backend PR.
- Strict TypeScript, which catches a whole class of prop and shape mismatches at build time.
- Pydantic v2 response models on every route, so a malformed object raises at serialization rather than returning bad JSON.
- The evaluation scripts in `backend/evaluation/`. Search results are committed and reproducible, which makes them real. The others have not been run to produce a committed result.
