# Roadmap

Everything on this page is either an explicit code artifact (a stub, an empty directory, a disabled UI element, a TODO-shaped comment) or a precompute/serving gap documented elsewhere in this doc set. Nothing here is aspirational — if it's listed, there's a concrete pointer to where the work would start.

## Planned but unimplemented

| Item | Evidence | Where the work would start |
|---|---|---|
| Multi-turn assistant memory | `conversation_id` accepted by the API and declared in the frontend type, never read or set anywhere; `AssistantDrawer.tsx:44` comment: `// In the future, pass conversation_id here` | Thread `conversation_id` through `AssistantOrchestrator.execute()`, decide on a memory representation (rolling buffer vs. summarized history) |
| `get_reviews` / `get_aspects` assistant intents | Both exist in `IntentEnum` and are selectable by the LLM, but `assistant_orchestrator.py:40-42` falls back to `_handle_get_game()` with the comment "Not fully implemented in services yet" | Add real handlers that call `ReviewService`/`AspectService` and shape a dedicated response type |
| "Hybrid" recommendation tab | `RECSYS_TYPES` in `GameDetail.tsx` includes `{ id: 'Hybrid', available: false }`, rendered with a "Soon" badge and no models filed under it | Decide whether this becomes a true ensemble UI, or is removed since a `hybrid` model id already exists under Content-Based Filtering (see [docs/ml/recommenders.md](ml/recommenders.md#known-issue-four-model-ids-silently-serve-embedding-results)) |
| CI/CD pipeline | No `.github/workflows/` or equivalent exists anywhere in the repo | Start with the manual test scripts in [docs/engineering/testing.md](engineering/testing.md) — converting them to real pytest assertions is a prerequisite for a meaningful CI job |

## Precompute-to-serving gaps (built, not wired up)

These aren't "planned" in the sense of not-yet-started — the offline computation is real and complete. What's missing is the online serving path.

- **`metadata`, `tfidf`, `hybrid` recommendation model IDs** are computed and written to `game_recommendations` by `scripts/precompute_content_recommendations.py`, but `RecommendationService` routes all three (plus `embedding`) to the same live pgvector query instead of reading those rows. See [docs/ml/recommenders.md](ml/recommenders.md#known-issue-four-model-ids-silently-serve-embedding-results).
- **Evaluation results are computed but never saved.** All three evaluation scripts (`evaluate_search.py`, `evaluate_recommenders.py`, `cf_split.py`) print their metrics and discard them. Adding a results-file write is a small change with an outsized credibility payoff — see [docs/ml/evaluation.md](ml/evaluation.md#highest-value-next-step).

## Coverage gaps (would need more compute/data, not more code)

- **ABSA** currently covers the top 100 ranked games / 10,000 sampled reviews, not the ~4.2M-review corpus. Extending coverage means running `absa_extract_hf.py` against a larger or full sample — the pipeline already supports it, it just hasn't been run at that scale.
- **LLM summarization** (`game_summaries`) has only been generated for whichever games `generate_summaries.py` was manually pointed at (the script itself hardcodes a single example game, "Brass: Birmingham"). A batch/loop-over-all-eligible-games version doesn't exist yet.

## Not on this list

Anything not backed by a stub, a disabled UI element, an explicit comment, or a documented precompute/serving gap is intentionally left off this page rather than speculated about.
