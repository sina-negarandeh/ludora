# Roadmap

Everything on this page is either an explicit code artifact (a stub, an empty directory, a disabled UI element, a TODO-shaped comment) or a precompute/serving gap documented elsewhere in this doc set. Nothing here is aspirational; if it's listed, there's a concrete pointer to where the work would start.

## Planned but unimplemented

| Item | Evidence | Where the work would start |
|---|---|---|
| Multi-turn assistant memory | `conversation_id` accepted by the API and declared in the frontend type, never read or set anywhere; `AssistantDrawer.tsx`'s one call site only ever sends `{ message: text }` | Thread `conversation_id` through `AssistantOrchestrator.execute()`, decide on a memory representation (rolling buffer vs. summarized history) |
| Assistant compare for franchise/series references | `compare` needs two or more explicitly named titles today; a query like "compare the Brass games" either under-extracts to one name or has the LLM invent a title that isn't in the catalog | Reuse the same text-search fallback `browse`/`search` already use when a filter value doesn't resolve, capped to a small number of results, so a franchise mention degrades to a real comparison instead of failing |
| CI/CD pipeline | No `.github/workflows/` or equivalent exists anywhere in the repo | Start with the manual test scripts in [docs/engineering/testing.md](engineering/testing.md); converting them to real pytest assertions is a prerequisite for a meaningful CI job |
| Search reranking stage | Diagnosed via real query testing, not a code stub: semantic search has no relevance floor. `search_semantic()` always returns its nearest 100 candidates by cosine distance no matter how weak the actual match is, and RRF fusion has no way to tell a confidently-wrong nearest-neighbor from a genuinely relevant one. Querying "Gavan Brown" (Brass: Birmingham's designer) surfaces "Goblins," "Goblin Vaults," and "Northern Branch: Firm With Brownies" from the semantic leg, zero relation to the query. See [search-semantic.md](ml/model-cards/search-semantic.md#known-limitations) and [search-lexical.md](ml/model-cards/search-lexical.md#known-limitations). | Add a reranking stage applied after retrieval, uniformly across all three modes (lexical, semantic, and hybrid post-RRF): a cross-encoder that scores `(query, candidate)` pairs directly can judge actual relevance instead of just vector proximity or rank position. Suggested model: Qwen3-Reranker-0.6B. Selection shouldn't be a fixed top-K: keep a maximum K, but apply a score-gap cutoff on top of it, so scores like `0.94/0.92/0.91/0.90/0.89` then a cliff to `0.41/0.39/0.37` cut at 5, while a smooth decline like `0.83/0.81/.../0.69` isn't truncated just because K was reached. Also needs a richer reranking document than the embedding one, since the embedding document deliberately excludes designers/artists/publishers, so a reranker scoring against that same text would be exactly as blind to "who designed this" as the embedding is. `mlx-embeddings` (already used for the embedding model) doesn't support this, confirmed by inspecting its source, not assumed: it has no reranker architecture for plain text, and its `qwen3` loader explicitly drops the LM head Qwen3-Reranker's yes/no-logit scoring needs. A real MLX path exists via the separate `mlx-lm` package (pre-converted checkpoints exist under `mlx-community`), but requires hand-implementing Qwen's official prompt template and yes/no-token-logit scoring protocol against `mlx-lm`'s low-level API, no ready-made library call, unlike the embedding model swap. |

## Precompute-to-serving gaps (built, not wired up)

These aren't "planned" in the sense of not-yet-started; the offline computation is real and complete. What's missing is running the script once and committing the result.

- **Recommender diversity and CF ranking-quality evaluation results aren't committed yet.** Both `evaluate_recommenders.py` and `cf_split.py` can log to MLflow and write a results file the same way `evaluate_search.py` does, but neither has been run since that capability was added. Search evaluation is the model to follow: run each script once, commit the output. See [docs/ml/evaluation.md](ml/evaluation.md#highest-value-next-step).

## Coverage gaps (would need more compute/data, not more code)

- **ABSA classification** covers the full eligible corpus by design (267,950 reviews, computed over the entire ~4.2M-review corpus with no per-game cap), but the DeBERTa classifier has only worked through 39,484 of those so far, run in resumable, time-boxed chunks. Extending coverage means running `absa_extract_hf.py` for more chunks; nothing about the pipeline itself needs to change.
- **LLM summarization** (`game_summaries`) has only been generated for whichever games `generate_summaries.py` was manually pointed at; the script itself hardcodes a single example game, "Brass: Birmingham." A batch or loop-over-all-eligible-games version doesn't exist yet.

## Not on this list

Anything not backed by a stub, a disabled UI element, an explicit comment, or a documented precompute/serving gap is intentionally left off this page rather than speculated about.
