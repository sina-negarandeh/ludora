# LLM summarization: "Customers say" paragraph

**Category:** Reviews NLP · **Status:** Implemented, verified against multiple games, still single-game-at-a-time

## Data

- Source: `game_aspect_aggregates` (per-aspect sentiment rollups) and `review_aspects` (per-review evidence sentences), both produced by [absa-deberta.md](absa-deberta.md); this stage has no independent data of its own, it summarizes ABSA's output.
- Eligibility gate: a game needs at least `MIN_REVIEWS_FOR_ABSA` reviews with usable ABSA signal and at least one aspect with `>= MIN_ASPECT_MENTIONS` mentions, or generation is skipped. The review count is a distinct `review_id` count, confidence-filtered, not a raw `review_aspects` row count, which would overstate it since one review can produce several aspect rows (Brass: Birmingham measured 175 rows from only 112 distinct reviews).
- Evidence sampling (`_sample_reviews`) is filtered to `sentiment IN ('positive','negative','neutral')` and `confidence >= ABSAConfig.WINNER_PROB_THRESHOLD`, the same bar `absa_aggregate.py` applies, so the evidence the LLM sees is exactly what's being counted, not a superset. Verified against Brass's real data: 26/26, 22/22, 20/20, 16/16 evidence-versus-`total_mentions` across its top aspects, no discrepancy.

## Model / Architecture

Local instruction-tuned LLM (`Qwen/Qwen3-4B-MLX-4bit` by default) via an OpenAI-compatible endpoint, used purely via prompting, no fine-tuning. Config is fully separate from the AI Assistant's, not just a different model name (`SUMMARIZATION_OPENAI_BASE_URL`/`SUMMARIZATION_OPENAI_API_KEY`/`SUMMARIZATION_MODEL_NAME` versus the assistant's `OPENAI_BASE_URL`/`OPENAI_API_KEY`/`LLM_MODEL_NAME`, `backend/app/core/config.py::Settings`). Summarization is an offline precompute job, the assistant serves live requests, and the two shouldn't need to agree on a server instance even though both currently point at the same model.

Two-stage pipeline (`SummarizationService`):

1. **Per-aspect mini-summary.** For each of the top-K aspects, sample evidence sentences (proportionally by sentiment, confidence-filtered) and prompt for a 1-sentence summary, sentiment, and confidence, JSON-schema-constrained (`AspectMiniSummary`, Pydantic-validated). The prompt includes a computed overall verdict (Positive, Negative, or Mixed-Neutral, via the exact same `CARD_DOMINANCE_THRESHOLD` rule the aspect cards use, `_classify_outcome()`) as ground truth, and the LLM's own `sentiment` field is overwritten with that computed value after the call, so the mini-summary's sentiment label can never drift from what the UI card for that same aspect shows.
2. **Final synthesis.** Feed all mini-summaries into a second prompt that writes the 2-3 sentence "Customers say" paragraph (`FinalGameSummary`, Pydantic-validated), with explicit instructions against inventing information or absolute claims.

### Reliability: a real, measured failure mode and its fix

Both prompts are prefixed with `/no_think`, Qwen3's documented directive to suppress its reasoning/thinking mode. This isn't precautionary; it fixes a reproduced failure. Without it, larger-evidence prompts (46 evidence lines for Ark Nova's Theme aspect) intermittently returned an empty completion (`finish_reason=stop`, well under `MAX_TOKENS`, about 30s latency) that failed JSON validation, while the exact same aspect with fewer evidence lines succeeded. The 30s latency, versus 1-3s for successful calls, points to the model spending its generation budget on hidden reasoning tokens for larger inputs, sometimes never reaching the actual JSON output. With `/no_think` added, the same previously-failing case ran 3 for 3 across 3 consecutive attempts (0.9-2.7s each, about 57 completion tokens) and, run through the full pipeline, all 5 of Ark Nova's aspects, including Theme, succeeded on the first attempt (1.4-2.8s each).

`_call_llm_json` also retries up to `SummarizationConfig.MAX_LLM_RETRIES` (2) times on a JSON-validation failure before giving up, and both call sites (`_summarize_aspect`, the final synthesis) catch an exhausted-retries failure gracefully rather than crashing: one unresolvable aspect is skipped (the game summary still generates from the rest), and a game whose final synthesis fails is skipped entirely rather than left half-written. This matters far more once this runs unattended across many games than it did for a single hardcoded one.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::SummarizationConfig` / `ABSAConfig` / `RANDOM_SEED`; LLM endpoint config in `backend/app/core/config.py::Settings`.

| Param | Value |
|---|---|
| `MIN_REVIEWS_FOR_ABSA` (distinct, confidence-filtered reviews) | 15 |
| `MIN_ASPECT_MENTIONS` | 5 |
| `TOP_K_ASPECTS` | 5 |
| `MAX_REVIEWS_PER_ASPECT` (evidence sample cap) | 100 |
| `TEMPERATURE` | 0.0 |
| `MAX_TOKENS` | 2,048 |
| `RANDOM_SEED` (evidence-sampling shuffle) | 42 |
| `ABSAConfig.WINNER_PROB_THRESHOLD` (evidence confidence bar, shared with aggregation) | 0.7 |
| `ABSAConfig.CARD_DOMINANCE_THRESHOLD` (per-aspect outcome, shared with the cards) | 0.6 |
| `MAX_LLM_RETRIES` | 2 (3 attempts total per call) |
| `SUMMARIZATION_MODEL_NAME` | `Qwen/Qwen3-4B-MLX-4bit` |

The per-aspect evidence sample (`_sample_reviews`) uses a seeded `random.Random(RANDOM_SEED)` instance, so the same aspect's evidence sample (and thus the same LLM input) is reproducible across offline `generate_summaries.py` runs.

## Training

None; pure prompting against a pretrained, instruction-tuned LLM.

- Script: `scripts/generate_summaries.py` hardcodes a single game, "Brass: Birmingham"; there's no batch or loop-over-all-eligible-games invocation anywhere in this repo. A real, disclosed limitation, not a bug.
- Command: `uv run --project backend python scripts/generate_summaries.py`
- MLflow experiment: `llm/review_summarization` (run name `generate`), logging the game id and name, LLM model, temperature, every `SummarizationConfig` threshold, and a `generated` 0/1 metric.
- **LLM-specific tracking.** This is a prompted feature, not a trained model, so there's no fit config to log; what's tracked instead is the prompt and the model's response characteristics. `SummarizationService` records one entry per LLM call (`llm_calls`: schema name, a 12-char prompt SHA-256 hash, wall-clock latency in seconds); `generate_summaries.py` aggregates these into `llm_call_count`/`total_llm_latency_seconds`/`avg_llm_latency_seconds`/`max_llm_latency_seconds` metrics, logs one `prompt_hash_<schema>` param per distinct prompt shape used (one for `AspectMiniSummary`, one for `FinalGameSummary`), and attaches the full raw call log as an MLflow text artifact (`llm_calls.json`).

## Artifact

None. The LLM is called live via the local server; nothing is saved except the resulting text (written to `game_summaries.summary`).

## Evaluation

**Status: does not exist.** No human-rated quality score, no automated faithfulness or hallucination check beyond the prompt's own instructions ("do not invent information," "do not make absolute claims"). What was checked: outcome consistency between the paragraph and the aspect cards (by construction, not sampled; see [Reliability](#reliability-a-real-measured-failure-mode-and-its-fix) above), and end-to-end runs against two real games (Brass: Birmingham, Ark Nova) spot-checked for plausibility and internal consistency with their aspect cards.

## Known limitations

- Still runs one game at a time (`scripts/generate_summaries.py` hardcodes "Brass: Birmingham"); no batch or loop-over-all-eligible-games invocation exists yet. The pipeline itself is verified reliable enough to build that on top of.
- Temperature 0.0 is intended to make output deterministic, but LLM determinism at temp=0 isn't guaranteed by all inference servers, and this isn't independently verified anywhere in this repo. The `/no_think` plus retry combination mitigates the one non-determinism failure mode actually observed (empty completions on larger prompts), not a general determinism guarantee.
- `/no_think` trades away Qwen3's reasoning mode entirely for this feature. That's a deliberate, measured tradeoff here (faster, more reliable, and the task, templated 1-sentence summaries from provided evidence, doesn't obviously benefit from extended reasoning), not a universal recommendation for every LLM-prompted feature in this repo.
