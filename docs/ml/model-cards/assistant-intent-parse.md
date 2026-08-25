# Assistant intent parsing

**Category:** LLM-powered NL query assistant · **Status:** Implemented, no benchmark · **Covers `POST /api/assistant/parse` only**, a debug/introspection route, not what the frontend calls. Live chat traffic runs on a different, larger model; see [assistant-plan-parse.md](assistant-plan-parse.md).

## Data

- Input: a single user free-text message, no retrieval or context beyond the message itself and the system prompt's embedded schema plus hand-written examples.
- No training data. This is pure in-context prompting, not a fine-tuned or trained classifier.

## Model / Architecture

Local instruction-tuned LLM (`Qwen/Qwen3-4B-MLX-4bit`), via the OpenAI-compatible endpoint, its own config (`OPENAI_BASE_URL`/`OPENAI_API_KEY`/`LLM_MODEL_NAME`), deliberately separate from summarization's (`SUMMARIZATION_*`), since this is a live request-time call and summarization is an offline batch job; see [summarization-llm.md](summarization-llm.md). `AssistantService.parse_query()` drives it through a [PydanticAI](https://ai.pydantic.dev/) agent in `PromptedOutput` mode, `/no_think`-prefixed (this model never needs to reason, only classify). PydanticAI renders the `ParsedIntent` schema into the prompt and validates what comes back; the hand-written rules text carries the same 26 rules and worked examples [assistant-plan-parse.md](assistant-plan-parse.md)'s model uses. On a validation failure it re-prompts with the error attached, up to `AssistantConfig.MAX_LLM_RETRIES` (2) times before raising, which also covers the empty-completion flake `SummarizationService` was built to tolerate. Kept small deliberately: single-intent classification has never shown a reliability problem at this size, unlike multi-step planning. See the other card for the measured comparison that justifies the split.

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

**Status: does not exist as a benchmark, and no smoke test exercises this route specifically.** `backend/test_orchestrator.py` (the repo's only intent-parsing smoke test) hits `/api/assistant/chat`, which runs on the plan-parsing model, not this one. See [assistant-plan-parse.md](assistant-plan-parse.md#evaluation) for what that script actually covers, and note there that it's currently out of date. Nothing in the repo currently exercises `parse_query()`/`/parse` directly beyond ad hoc manual `curl` calls.

## Known limitations

- `conversation_id` is accepted by the API but never read anywhere; no multi-turn memory (shared with the plan-parsing route, see the other card).
- No evaluation set covers the full 8-intent space (`browse`, `search`, `recommend`, `compare`, `get_game`, `get_reviews`, `get_aspects`, `unsupported`), and this specific route has no smoke test at all (above).
