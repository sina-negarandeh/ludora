# Testing

**Status: no automated test suite exists.** Worth stating plainly, since the file layout (files named `test_*.py`) could otherwise mislead a reader: none of them use an assertion framework, and none of them run in CI, since there's no CI configured at all. See [docs/limitations.md](../limitations.md).

## Backend "tests" (all print-based scripts, not pytest suites)

| File | Requires | Uses `assert`? | How it actually runs |
|---|---|---|---|
| `backend/test_api.py` | A live server already running on `:8000` | No | `python test_api.py`, hits `GET /api/games?limit=2` via `urllib`, prints the count |
| `backend/test_games.py` | A live DB | No; internal exceptions are caught and printed via `traceback.print_exc()`, then swallowed | `python test_games.py`. Because the exception is swallowed, `pytest` would report this file's `test()` function as passing even if the DB call fails internally. |
| `backend/test_routes.py` | A live/seeded DB, imports the app in-process via `TestClient` | No | `python test_routes.py`, fires 7 requests, prints only status codes, no assertions on body content; has no `test_*` function, so `pytest test_routes.py` would collect 0 tests |
| `backend/test_assistant.py` | A local LLM server, degrades gracefully with a caught exception if absent | No | `python test_assistant.py` |
| `backend/test_assistant_retry.py` | A local LLM server, blocks forever (`while True`) if one never starts | No | `python test_assistant_retry.py`, despite the name, tests server-readiness polling and a single parse call, not the retry-on-malformed-completion logic `AssistantService.parse_query()` actually has |
| `backend/test_orchestrator.py` | A live DB *and* a live local LLM server | No | `python test_orchestrator.py`, a handful of hardcoded natural-language queries through the full chat pipeline, prints intent and data shape |

None of these files are wired into any CI job; there's no CI configuration in the repo at all. `backend/pyproject.toml` has no `pytest` dependency and no `[tool.pytest.ini_options]` section, so pytest isn't even installed by default.

**What this means concretely**: a regression that changes a response shape, breaks a query, or silently swaps in wrong data would not be caught by anything currently in the repository unless a developer manually runs these scripts and reads the printed output.

## Frontend

No test framework is installed: `frontend/package.json` has no `vitest`, `jest`, `@testing-library/react`, `playwright`, or `cypress` in dependencies or devDependencies, and there's no `test` script. Linting exists (`oxlint`, `frontend/.oxlintrc.json`, enforcing `react/rules-of-hooks` and a constant-export allowance), and `frontend/tsconfig.app.json` runs a strict TypeScript configuration (`noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `erasableSyntaxOnly`). Type-checking via `tsc -b` (part of `npm run build`) is the closest thing to an automated correctness check on the frontend, and it only catches type errors, not behavioral regressions.

## What does exist as a quality signal

- **Strict TypeScript** across the frontend, which catches an entire class of prop/shape mismatches at build time even without a test suite.
- **Pydantic v2 response models** on every backend route, which catch response-shape errors at serialization time (a malformed object raises rather than silently returning bad JSON).
- **The evaluation scripts** (`backend/evaluation/`) are manual harnesses, not regression tests: for search, results are committed and reproducible, which makes them a real quality signal; for recommenders and CF, the script exists but hasn't been run to produce a committed result yet. See [docs/ml/evaluation.md](../ml/evaluation.md).

## Highest-value next steps (not started)

1. Add `pytest` and `httpx`/`TestClient`-based assertions to the existing DB-dependent scripts. The request/response wiring to convert is already there; only the `assert` statements are missing.
2. Add a `conftest.py` with a test-database fixture so backend tests don't require a hand-seeded local Postgres instance.
3. Add `vitest` and React Testing Library for at least the filter/sort logic in `GamesList.tsx` and the gauge math in `GameDetail.tsx`, both pure enough to unit test without a running backend.
4. Wire whichever of the above exists into a CI workflow; none currently runs on push or PR.

## Related code

- `backend/test_api.py`, `test_games.py`, `test_routes.py`, `test_assistant.py`, `test_assistant_retry.py`, `test_orchestrator.py`
- `backend/pyproject.toml`
- `frontend/package.json`, `frontend/.oxlintrc.json`, `frontend/tsconfig.app.json`
