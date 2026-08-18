# LLM summarization — "Customers say" paragraph

**Category:** Reviews NLP · **Status:** Implemented, run for exactly one game

## Data

- Source: `game_aspect_aggregates` (per-aspect sentiment rollups) + `review_aspects` (per-review evidence sentences), both produced by [absa-deberta.md](absa-deberta.md) — this stage has no independent data of its own, it summarizes ABSA's output.
- Eligibility gate: a game needs at least `MIN_REVIEWS_FOR_ABSA` aspect rows and at least one aspect with `≥ MIN_ASPECT_MENTIONS` mentions, or generation is skipped.

## Model / Architecture

Local instruction-tuned LLM (`Qwen/Qwen3-30B-A3B-MLX-4bit` by default) via an OpenAI-compatible endpoint (`OPENAI_BASE_URL`, MLX server) — used purely via prompting, no fine-tuning. Two-stage pipeline (`SummarizationService`):

1. **Per-aspect mini-summary**: for each of the top-K aspects, sample evidence sentences (proportionally by sentiment) and prompt for a 1-sentence summary + sentiment + confidence, JSON-schema-constrained (`AspectMiniSummary`, Pydantic-validated).
2. **Final synthesis**: feed all mini-summaries into a second prompt that writes the 2–3 sentence "Customers say" paragraph (`FinalGameSummary`, Pydantic-validated), with explicit instructions against inventing information or absolute claims.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::SummarizationConfig` / `RANDOM_SEED`; LLM endpoint config in `backend/app/core/config.py::Settings`.

| Param | Value |
|---|---|
| `MIN_REVIEWS_FOR_ABSA` | 15 |
| `MIN_ASPECT_MENTIONS` | 5 |
| `TOP_K_ASPECTS` | 5 |
| `MAX_REVIEWS_PER_ASPECT` (evidence sample cap) | 100 |
| `TEMPERATURE` | 0.0 |
| `MAX_TOKENS` | 2,048 |
| `RANDOM_SEED` (evidence-sampling shuffle) | 42 |
| `LLM_MODEL_NAME` | `Qwen/Qwen3-30B-A3B-MLX-4bit` |

The per-aspect evidence sample (`_sample_reviews`) was previously an unseeded `random.shuffle()` — fixed in this session to use a seeded `random.Random(RANDOM_SEED)` instance, so the same aspect's evidence sample (and thus the same LLM input) is reproducible across offline `generate_summaries.py` runs.

## Training

None — pure prompting against a pretrained, instruction-tuned LLM.

- Script: `scripts/generate_summaries.py` — **hardcodes a single game, "Brass: Birmingham"**; there is no batch/loop-over-all-eligible-games invocation anywhere in this repo. Not fixed in this pass (a real, disclosed limitation, not a bug).
- Command: `uv run --project backend python scripts/generate_summaries.py`
- MLflow experiment: `llm/review_summarization` (run name `generate`) — logs the game id/name, LLM model, temperature, every `SummarizationConfig` threshold, and a `generated` 0/1 metric.
- **LLM-specific tracking** (this is a prompted feature, not a trained model — there's no fit config to log, so what's tracked instead is the thing that actually determines behavior: the prompt and the model's response characteristics). `SummarizationService` records one entry per LLM call (`llm_calls`: schema name, a 12-char prompt SHA-256 hash, wall-clock latency in seconds); `generate_summaries.py` aggregates these into `llm_call_count`/`total_llm_latency_seconds`/`avg_llm_latency_seconds`/`max_llm_latency_seconds` metrics, logs one `prompt_hash_<schema>` param per distinct prompt shape used (one for `AspectMiniSummary`, one for `FinalGameSummary`), and attaches the full raw call log as an MLflow text artifact (`llm_calls.json`).

## Artifact

None — the LLM is called live via the local server, nothing is saved except the resulting text (written to `game_summaries.summary`).

## Evaluation

**Status: does not exist.** No human-rated quality score, no automated faithfulness/hallucination check beyond the prompt's own instructions ("do not invent information," "do not make absolute claims"). This is a real, disclosed gap.

## Known limitations

- Only ever run for one hardcoded game — the catalog-wide rollout this would need doesn't exist.
- Temperature 0.0 is intended to make output deterministic, but LLM determinism at temp=0 isn't guaranteed by all inference servers, and this isn't independently verified anywhere in this repo.
