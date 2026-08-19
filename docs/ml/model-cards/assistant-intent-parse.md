# Assistant intent parsing

**Category:** LLM-powered NL query assistant · **Status:** Implemented, no benchmark

## Data

- Input: a single user free-text message, no retrieval or context beyond the message itself and the system prompt's embedded schema plus hand-written examples.
- No training data. This is pure in-context prompting, not a fine-tuned or trained classifier.

## Model / Architecture

Local instruction-tuned LLM (`Qwen/Qwen3-4B-MLX-4bit`), via the OpenAI-compatible endpoint, its own config (`OPENAI_BASE_URL`/`OPENAI_API_KEY`/`LLM_MODEL_NAME`), deliberately separate from summarization's (`SUMMARIZATION_*`), since this is a live request-time call and summarization is an offline batch job; see [summarization-llm.md](summarization-llm.md). `AssistantService.parse_query()` sends one chat-completion call with the full `ParsedIntent` JSON schema embedded in the system prompt plus a handful of worked examples, JSON-schema-constrained, Pydantic-validated (`ParsedIntent.model_validate_json()`). On a validation failure, it retries up to `AssistantConfig.MAX_LLM_RETRIES` (2) times before raising, since the same class of empty-completion flake `SummarizationService` was built to tolerate shows up here too. `AssistantOrchestrator` then dispatches on the parsed `intent` enum via a plain `if`/`elif`, not a semantic embedding classifier, just routing on a string the LLM filled in.

Entity resolution (game, category, theme, mechanic, designer, artist, publisher names) is a separate, non-ML lowercase-name lookup cache (`EntityResolver`) plus delegation to lexical search for game names; no fuzzy-matching library involved.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::AssistantConfig`; LLM endpoint config in `backend/app/core/config.py::Settings`.

| Param | Value |
|---|---|
| `TEMPERATURE` | 0.0 |
| `MAX_TOKENS` | 4,096 |
| `MAX_LLM_RETRIES` | 2 (3 attempts total per call) |
| `LLM_MODEL_NAME` | `Qwen/Qwen3-4B-MLX-4bit` |

No random seed applicable; this is a live LLM call, not a fit or sampling step.

## Training

None. Pure prompting, no fine-tuning, no classifier trained for intent routing.

## Artifact

None. Every call is live against the local LLM server; nothing is precomputed or cached.

## Evaluation

**Status: does not exist as a benchmark**, but a print-only smoke test has been upgraded into a small, MLflow-tracked one:

- Script: `backend/test_orchestrator.py`, hardcoded queries against the live `/api/assistant/chat` endpoint, each with a minimal expected-behavior check (correct `intent`, and correct `needs_clarification` for a deliberately-ambiguous query).
- Fixed eval set, explicitly versioned: `EVAL_DATASET_VERSION = "smoke_v2"` (bump this whenever `TEST_CASES` changes meaningfully), the same idea as `SearchConfig`'s `search_queries.json` but for a prompted feature where the "dataset" is just the fixed case list, not an external file.
- MLflow experiment: `llm/intent_parsing` (run name `smoke_test`), logging `n_queries`, `eval_dataset_version`, `llm_model`, `temperature`, and a 12-char SHA-256 hash of the static system prompt (`AssistantService._build_system_prompt()`, extracted specifically so this hash can be computed without duplicating the prompt text) as params; `pass_rate`, `latency_p50_seconds`, `latency_p95_seconds`, and a 0/1 metric per query as metrics.
- Can write `backend/evaluation/results/assistant_intent_eval_latest.json`, but hasn't been run since that capability was added; no committed file exists yet. See [docs/ml/evaluation.md](../evaluation.md).
- Command: `uv run --project backend python test_orchestrator.py`

This is still a small smoke test, not a real benchmark. It checks the pipeline doesn't regress on a few known cases, not that intent parsing is generally accurate across the space of things a user might ask.

## Known limitations

- `compare` needs two or more named titles in the query; a franchise or series reference doesn't resolve to a concrete pair yet.
- The assistant's structured filter set has no playtime fields, unlike the catalog's direct browse and search filters.
- `conversation_id` is accepted by the API but never read anywhere; no multi-turn memory.
- No evaluation set covers the full 8-intent space (`browse`, `search`, `recommend`, `compare`, `get_game`, `get_reviews`, `get_aspects`, `unsupported`); the smoke test checks a handful of hardcoded queries, not the whole space.
