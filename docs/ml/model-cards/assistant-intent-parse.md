# Assistant intent parsing

**Category:** LLM-powered NL query assistant · **Status:** Implemented, no benchmark

## Data

- Input: a single user free-text message, no retrieval/context beyond the message itself and the system prompt's embedded schema + hand-written few-shot examples.
- No training data — this is pure in-context prompting, not a fine-tuned or trained classifier.

## Model / Architecture

Local instruction-tuned LLM (`Qwen/Qwen3-30B-A3B-MLX-4bit` by default), via the OpenAI-compatible endpoint — its own config (`OPENAI_BASE_URL`/`OPENAI_API_KEY`/`LLM_MODEL_NAME`), deliberately separate from summarization's (`SUMMARIZATION_*`, a smaller `Qwen/Qwen3-4B-MLX-4bit` by default), since this is a live request-time call and summarization is an offline batch job — see [summarization-llm.md](summarization-llm.md). `AssistantService.parse_query()` sends one chat-completion call with the full `ParsedIntent` JSON schema embedded in the system prompt plus a handful of worked examples, JSON-schema-constrained, Pydantic-validated (`ParsedIntent.model_validate_json()`, **no retry on validation failure**). `AssistantOrchestrator` then dispatches on the parsed `intent` enum via a plain `if`/`elif` — not a semantic embedding classifier, just routing on a string the LLM filled in.

Entity resolution (game/category/theme/mechanic names) is a separate, non-ML lowercase-name lookup cache (`EntityResolver`) plus delegation to lexical search for game names — no fuzzy-matching library involved.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::AssistantConfig`; LLM endpoint config in `backend/app/core/config.py::Settings`.

| Param | Value |
|---|---|
| `TEMPERATURE` | 0.0 |
| `MAX_TOKENS` | 4,096 |
| `LLM_MODEL_NAME` | `Qwen/Qwen3-30B-A3B-MLX-4bit` |

No random seed applicable — this is a live LLM call, not a fit/sampling step.

## Training

None — pure prompting, no fine-tuning, no classifier trained for intent routing.

## Artifact

None — every call is live against the local LLM server; nothing is precomputed or cached.

## Evaluation

**Status: does not exist as a benchmark**, but this session upgraded the existing print-only smoke test into a small, persisted one:

- Script: `backend/test_orchestrator.py` — 3 hardcoded queries against the live `/api/assistant/chat` endpoint, each with a minimal expected-behavior check (correct `intent`, and correct `needs_clarification` for the deliberately-ambiguous "Compare Catan with the 1995 edition" query). Previously this only printed output for manual inspection with no pass/fail concept at all.
- Fixed eval set, explicitly versioned: `EVAL_DATASET_VERSION = "smoke_v1"` (bump this whenever `TEST_CASES` changes meaningfully, same idea as `SearchConfig`'s `search_queries.json` but for a prompted feature where the "dataset" is just the fixed case list, not an external file).
- MLflow experiment: `llm/intent_parsing` (run name `smoke_test`) — logs `n_queries`, `eval_dataset_version`, `llm_model`, `temperature`, and a 12-char SHA-256 hash of the static system prompt (`AssistantService._build_system_prompt()`, extracted specifically so this hash can be computed without duplicating the prompt text) as params; `pass_rate`, `latency_p50_seconds`, `latency_p95_seconds`, and a 0/1 metric per query as metrics — so a regression in intent parsing, prompt drift, or latency all show up as metric movement over time instead of silently passing whatever the LLM happens to return.
- Results file: `backend/evaluation/results/assistant_intent_eval_latest.json` — includes the prompt hash, pass rate, and per-query latency/pass detail.
- Command: `uv run --project backend python test_orchestrator.py`

This is still a **3-query smoke test, not a real benchmark** — it checks the pipeline doesn't regress on a few known cases, not that intent parsing is generally accurate across the space of things a user might ask.

## Known limitations

- `get_reviews`/`get_aspects` intents exist in the schema but fall back to the generic "get game" handler — not fully implemented in the orchestrator.
- `conversation_id` is accepted by the API but never read anywhere — no multi-turn memory.
- No retry on JSON-schema validation failure — a malformed LLM response fails the whole request rather than retrying.
