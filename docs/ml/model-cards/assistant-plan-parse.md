# Assistant plan parsing

**Category:** LLM-powered NL query assistant · **Status:** Implemented, no benchmark · **Covers `POST /api/assistant/chat`**, the route the frontend actually calls.

## Data

- Input: a single user free-text message, no retrieval or context beyond the message itself and the system prompt's embedded schema plus 26 rules and worked examples covering tag vocabulary, field-filling mechanics, sort-vs-filter disambiguation for every numeric dimension, intent disambiguation, and multi-step planning mechanics.
- No training data. This is pure in-context prompting, not a fine-tuned or trained classifier.

## Model / Architecture

Local instruction-tuned LLM, `Qwen/Qwen3-30B-A3B-MLX-4bit`, deliberately larger than [assistant-intent-parse.md](assistant-intent-parse.md)'s `Qwen/Qwen3-4B-MLX-4bit`, via the OpenAI-compatible endpoint, its own config (`OPENAI_BASE_URL`/`OPENAI_API_KEY`/`PLAN_MODEL_NAME`). `AssistantService.parse_plan()` sends one chat-completion call with the full `ParsedPlan` JSON schema (a list of one or more `ParsedIntent` steps) embedded in the system prompt, thinking mode always allowed (not suppressed via `/no_think`, and not gated behind a first fast attempt), Pydantic-validated.

The model size and thinking-mode choice are both measured, not assumed. Directly against this server, `Qwen/Qwen3-4B-MLX-4bit` reliably produced a structural JSON bug on a query needing real decomposition: one extra trailing closing brace, reproduced byte-identically across temperatures 0.0 and 0.3, so not a sampling fluke a retry could escape, plus real intent misclassifications on harder chained queries. `Qwen/Qwen3-30B-A3B-MLX-4bit` with thinking mode allowed didn't reproduce either failure in the same tests. The latency cost of always allowing thinking was also measured directly (2.3s to 17.9s for one representative query) and accepted, since latency isn't a constraint for this project.

Parsing goes through a [PydanticAI](https://ai.pydantic.dev/) agent in `PromptedOutput` mode: the schema is rendered into the prompt and plain JSON comes back, which PydanticAI validates against `ParsedPlan`. On a violation it re-prompts the model with the validation error attached, up to `AssistantConfig.MAX_LLM_RETRIES` (2) times, so each attempt is a different and more constrained question rather than a replay of the same one. Thinking-mode `<think>` blocks are separated out by the library rather than stripped by hand.

`PromptedOutput` is not PydanticAI's default, and the choice was measured against this server rather than assumed. `NativeOutput` (a `json_schema` response format) fails on the plan schema whenever thinking mode is on, which this model always runs with, and kept failing after raising `max_tokens` to this app's own 4,096, so it is not a token ceiling. `ToolOutput`, the library default, needs tool-calling support. `PromptedOutput` is the one mode that works for both this card's model and the single-intent one.

There is still no schema-enforced or grammar-constrained decoding anywhere in this pipeline, confirmed by reading the installed `mlx_lm.server`'s source (v0.31.3): it has no schema-aware decode hook. Validity comes from prompting plus validate-and-retry, not a token-level guarantee. See [docs/ml/assistant.md](../assistant.md).

`ParsedPlan.steps` is truncated to `AssistantConfig.MAX_PLAN_STEPS` (3) after parsing, deterministically in application code, not requested of the model. `AssistantOrchestrator.execute_plan()` then compiles the plan into a validated dependency graph (`plan_graph.compile_plan()`) before executing anything. See [docs/ml/assistant.md](../assistant.md#multi-step-planning-and-execution) for the mechanism, including how a step's `$stepN` placeholder gets resolved against an earlier step's result.

Entity resolution (game, category, theme, mechanic, designer, artist, publisher names) is a separate, non-ML lowercase-name lookup cache (`EntityResolver`) plus delegation to lexical search for game names; no fuzzy-matching library involved. A name already resolved by an earlier step in the same plan skips this path entirely (`_known_bgg_ids`).

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::AssistantConfig`; LLM endpoint config in `backend/app/core/config.py::Settings`.

| Param | Value |
|---|---|
| `TEMPERATURE` | 0.0 (every attempt, retries included) |
| `MAX_TOKENS` | 4,096 |
| `MAX_LLM_RETRIES` | 2 (3 attempts total per call) |
| `MAX_PLAN_STEPS` | 3, enforced by the app after parsing |
| `PLAN_MODEL_NAME` | `Qwen/Qwen3-30B-A3B-MLX-4bit` |

No random seed applicable; this is a live LLM call, not a fit or sampling step. In practice, calls at `TEMPERATURE=0.0` against this server have been observed as near-deterministic for a fixed prompt, but not perfectly so across process boundaries. See Known limitations.

## Training

None. Pure prompting, no fine-tuning, no classifier trained for plan decomposition.

## Artifact

None. Every call is live against the local LLM server; nothing is precomputed or cached.

## Evaluation

**Status: does not exist as a benchmark**, but a print-only smoke test has been upgraded into a small, MLflow-tracked one, with a caveat:

- Script: `backend/test_orchestrator.py`, hardcoded queries against the live `/api/assistant/chat` endpoint, each with a minimal expected-behavior check (correct `intent`, and correct `needs_clarification` for a deliberately-ambiguous query).
- Fixed eval set, explicitly versioned: `EVAL_DATASET_VERSION = "smoke_v2"` (bump this whenever `TEST_CASES` changes meaningfully), the same idea as `SearchConfig`'s `search_queries.json` but for a prompted feature where the "dataset" is just the fixed case list, not an external file.
- MLflow experiment: `llm/intent_parsing` (run name `smoke_test`), logging `n_queries`, `eval_dataset_version`, `llm_model`, `temperature`, and a 12-char SHA-256 hash of the static system prompt as params; `pass_rate`, `latency_p50_seconds`, `latency_p95_seconds`, and a 0/1 metric per query as metrics.
- Can write `backend/evaluation/results/assistant_intent_eval_latest.json`, but hasn't been run since that capability was added; no committed file exists yet. See [docs/ml/evaluation.md](../evaluation.md).
- Command: `uv run --project backend python test_orchestrator.py`

**This script is currently out of date, not just small.** `EVAL_DATASET_VERSION = "smoke_v2"`'s own comment states the `compare` intent was removed from the assistant. That was true for one prior commit and is false today: `compare` is exercised heavily, including a one-to-many and multi-dependency chaining mechanism this script predates entirely and doesn't test. Running it today would assert a wrong fact, not just miss coverage. Fixing this is tracked in [docs/roadmap.md](../../roadmap.md).

## Known limitations

- No schema-enforced or grammar-constrained decoding. See Model/Architecture above and [docs/roadmap.md](../../roadmap.md) for what closing this gap would take.
- `conversation_id` is accepted by the API but never read anywhere; no multi-turn memory. A plan's steps can reference each other, but only within the one message that produced them.
- `MAX_PLAN_STEPS` (3) is a hard ceiling; a request needing a fourth step is silently truncated rather than re-prompted.
- Measured, reproducible prompt sensitivity: sort/limit fields are occasionally dropped by the model specifically in a multi-dependency compare (two independent steps merging into one compare), even though the identical instruction is followed reliably in a single-dependency chain. `_resolve_step()` detects the resulting ambiguity and returns a clean error rather than guessing, but the request itself doesn't complete. Two different prompt formulations were measured to each fix one of two adjacent cases while silently breaking the other, before a version that holds both was found: evidence this is a genuine long-system-prompt fragility, not a one-off wording bug.
- The evaluation smoke test is out of date (see Evaluation above) and covers only a handful of hardcoded queries against the full space of things a user might ask.
