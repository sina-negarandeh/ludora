# Semantic + hybrid search: sentence embeddings + RRF

**Category:** Search · **Status:** Implemented, served live

## Data

- Source: `games` table (via SQL): `bgg_id`, `name`, `description`, `game_weight`, `mfg_playtime`, `themes[]`, `mechanics[]`, `categories[]`, `subdomains[]`, `families[]` (via `subfamilies`, already formatted as `"{family}: {value}"`). Designers, artists, and publishers are deliberately excluded from the embedding document; lexical search already covers proper-noun matches at `search_vector`'s D-tier, so including them here would only dilute thematic signal rather than add retrieval capability.
- Document construction (`scripts/update_embeddings.py::build_structured_document`): `Name: ... \n\n Description:\n... \n\n Themes:\n... \n\n Mechanics:\n... \n\n Categories:\n... \n\n Type:\n... \n\n Families:\n... \n\n Experience:\n...`, description truncated. `Type` holds subdomains ([BGG](https://boardgamegeek.com/)'s rank/leaderboard type: Thematic, Strategy, War, and so on), `Experience` holds `game_weight`/`mfg_playtime` converted to short phrases via `SearchConfig.WEIGHT_BUCKETS`/`PLAYTIME_BUCKETS` ("heavy strategy game, high complexity", "30 to 60 minute game") rather than raw numbers. Bucket ranges are kept identical, by hand, to the filter presets in `frontend/src/pages/GamesList.tsx` so a query like "heavy strategy game" uses the same vocabulary the UI's own filters do.

## Model / Architecture

`Qwen3-Embedding-0.6B` (4-bit DWQ quantization, `mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ`), served locally via the `mlx-embeddings` package (Apple MLX, GPU-accelerated), used purely for inference, not fine-tuned. Decoder-based (Qwen3 backbone), 1024-dim native output, last-token pooling with L2 normalization applied internally by `mlx_embeddings.models.qwen3`. Loading and encoding is centralized in `backend/app/core/embeddings.py` (`encode(texts, is_query=...)`), used by both this script and `SearchService.search_semantic()` so the two call sites can't drift on load args or instruction-prefix handling.

**Why 4-bit DWQ over mxfp8.** mxfp8 was tried first and measured about 0.47s per document on this hardware, which would put a full 28,208-game catalog at 3 to 4 hours. MLX's fast-matmul path is more mature for 4-bit than for mxfp8, and DWQ (dynamic-range weight quantization) specifically targets retaining near-full-precision quality despite the drop to 4-bit, unlike naive round-to-nearest quantization. Combined with the document-length and batching choices below, measured throughput comes to about 32 minutes for the full catalog.

Vectors are stored in `game_embeddings` (pgvector), one row per `(game_id, model)`, not a column on `games`, so more than one embedding model's vectors can coexist for comparison rather than a rerun silently overwriting the only copy. At query time, `SearchService.search_semantic()` encodes the query with the same model, filters to `GameEmbedding.model == SearchConfig.EMBEDDING_MODEL`, and does a pgvector cosine-distance nearest-neighbor query. Hybrid mode runs both lexical and semantic retrieval and fuses their rankings with Reciprocal Rank Fusion (RRF); no separate model, just a fusion formula (`SearchService.search()`).

**Asymmetric instruction prefix.** Qwen3-Embedding was trained for instruction-aware retrieval: the query gets `SearchConfig.QUERY_INSTRUCTION` prepended (`"Instruct: ...\nQuery: {query}"`), documents are encoded plain. `embeddings.encode(..., is_query=True)` only applies this when `SearchConfig.EMBEDDING_MODEL` is in `SearchConfig.INSTRUCTION_AWARE_MODELS`, so switching to a non-instruction-tuned model wouldn't wrongly apply it.

## Hyperparameters

Source of truth: `backend/app/core/ml_config.py::SearchConfig`.

| Param | Value |
|---|---|
| `EMBEDDING_MODEL` | `mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ` |
| `DESCRIPTION_TRUNCATE_CHARS` | 1,500. Raising it to 4,000 was tried (Qwen3 supports 32K tokens), but measured against the catalog the median document was identical either way (316 tokens, since most descriptions are already short) while 4,000 nearly tripled the tail (p99 1,146 versus 549 tokens). A long, often flavor-text-heavy description also dilutes the pooled embedding's distinctive signal rather than adding to it. |
| `EMBED_MAX_TOKENS` | 768 (tokenizer `max_length`; measured p99=549, max=553 tokens at `DESCRIPTION_TRUNCATE_CHARS=1500` on a 500-doc sample, real headroom, not an unused ceiling) |
| `EMBED_BATCH_SIZE` | 32, conservative for this decoder model over longer sequences; raise it if your hardware handles it |
| `RRF_K` (fusion constant) | 60 |
| `CANDIDATE_POOL_SIZE` (per-leg retrieval limit before fusion) | 100 |
| `WEIGHT_BUCKETS` | Light (1-2), Medium (2-3.5), Heavy (3.5-5); matches `GamesList.tsx`'s complexity filter presets |
| `PLAYTIME_BUCKETS` | Under 30, 30-60, 60-120, 120+ minutes; matches `GamesList.tsx`'s playtime filter presets |
| `QUERY_INSTRUCTION` / `INSTRUCTION_AWARE_MODELS` | Query-side instruction prefix, applied only for models in `INSTRUCTION_AWARE_MODELS` (currently just the configured Qwen3-Embedding model) |

No random seed needed; encoding is deterministic.

## Training

None. Qwen3-Embedding-0.6B is used off-the-shelf, no fine-tuning. "Training" here means encoding the whole catalog into vectors, a deterministic inference pass, not a fit step.

- Script: `scripts/update_embeddings.py`, must be rerun whenever game metadata (description, themes, mechanics, categories, subdomains, families, weight, playtime) changes; not trigger-driven. Documents are sorted by length before batching, since `batch_encode_plus` pads every item in a batch up to that batch's longest member, so pulling games in raw DB order means one long outlier inflates its entire batch's cost for no benefit. Sorting first measured about 2x faster with identical output.
- Command: `uv run --project backend python scripts/update_embeddings.py`
- MLflow experiment: `search/embedding_build` (run name `update_embeddings`), logging the embedding model name, truncation length, max tokens, batch size, and games-processed count.

## Artifact

None persisted as a file. Vectors are written into `game_embeddings` (pgvector column), upserted on `(game_id, model)`. Reruns of the same model overwrite that model's rows (no version history within a model), but a rerun for a different model leaves prior models' rows untouched, so switching or comparing embedding models doesn't destroy the old vectors. The MLX-converted weights themselves are downloaded from HuggingFace at runtime, not vendored.

## Evaluation

- Script: `backend/evaluation/evaluate_search.py`, MRR@10, NDCG@10, Recall@100 against the same 5 hand-written queries used for lexical (see [search-lexical.md](search-lexical.md)), run separately for `semantic` and `hybrid` modes.
- MLflow experiment: `search/retrieval_eval` (run names `semantic`, `hybrid`), same experiment as lexical, so all three retrieval modes are directly comparable as runs.
- Results files, both committed: `backend/evaluation/results/search_semantic_latest.json` (MRR@10 0.467, NDCG@10 0.370, Recall@100 0.433) and `backend/evaluation/results/search_hybrid_latest.json` (MRR@10 0.500, NDCG@10 0.379, Recall@100 0.433).

## Known limitations

- Only 5 evaluation queries: a smoke-level sanity check, not a statistically meaningful benchmark.
- `game_embeddings.created_at` gets overwritten on each rerun for the same model. There's no way to tell from the DB alone whether a given game's embedding reflects its current metadata or a stale prior version, short of comparing against MLflow's logged run history.
- **No relevance floor.** `search_semantic()` always returns its nearest 100 candidates by cosine distance, however weak the actual match. There's no "I don't have a good answer for this" signal, so a low-information query (a person's name, say, which has little inherent semantic content) still returns 100 confidently-ranked results with no way to tell they're all weak matches. Confirmed with a real query: "Gavan Brown" (a designer credit) surfaces "Goblins," "Goblin Vaults," and "Northern Branch: Firm With Brownies," zero relation to the query. Planned fix: a reranking stage; see [docs/roadmap.md](../../roadmap.md#planned-but-unimplemented).
