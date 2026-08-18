# ML Evaluation

This page separates what is **measured and reproducible** from what is **displayed but not traceable to a file** from what is **not evaluated at all**. All three categories exist in this repository simultaneously — read the status column carefully.

## Search evaluation

**Script**: `backend/evaluation/evaluate_search.py`. **Metrics**: MRR@10, NDCG@10 (binary relevance), Recall@100. **Test set**: `backend/evaluation/search_queries.json` — 5 hand-written queries, each with a small list of expected relevant BGG IDs (e.g. `"space exploration" → [182028, 169786, 11]`).

**Status: code exists and runs; results are not persisted anywhere.** The script only `print()`s its output — no results file exists in the repository. **No numeric score can be reported here.** To reproduce:

```bash
cd backend
uv run python evaluation/evaluate_search.py
```

5 queries is far too small a set to generalize from even if results had been captured — treat this as a smoke-test harness, not a benchmark.

## Recommender diversity evaluation (Coverage, ILD@10)

**Script**: `backend/evaluation/evaluate_recommenders.py`. **Metrics**: Catalog Coverage (share of the catalog that appears in any top-10 list for a model) and Intra-List Diversity @10 (mean pairwise cosine distance among a game's own recommended list, using `game_embeddings` for the currently-configured model). **Models evaluated**: `metadata, tfidf, graph_jaccard, deepwalk, cf_item_cosine, cf_als` — 6 of the 9 UI model IDs. `popularity` is excluded since a fixed popularity ranking has no natural per-game "list" to compute diversity over; `embedding` and `hybrid` are excluded because both are computed live and never written to `game_recommendations`, so a coverage/ILD query for either would always read 0 rows.

**Status: code exists and runs; results are not persisted to a file.** Like the search evaluator, this script only prints.

### Where these numbers live

The UI no longer shows Coverage/ILD at all. `frontend/src/pages/GameDetail.tsx` used to hardcode a `MODELS` array with its own fabricated Coverage/ILD figures; it now fetches the model list live from `GET /api/recommendation-models` (`RecommendationService.get_recommendation_models()`, backed by `RECOMMENDATION_MODELS` in `backend/app/core/ml_config.py`), which returns id/name/paradigm/description only — no diversity metrics. Coverage/ILD numbers exist only as the printed output of a manual run of `evaluate_recommenders.py`.

**These numbers cannot be traced to a committed artifact.** `evaluate_recommenders.py` has no file-write call anywhere in its source, and a repository-wide search for a matching results file (`*eval*result*`, `*results*.json`, `*results*.csv`) found nothing. If you want numbers, rerun the script yourself — its output would be **Observed** (consistent with a real run of this exact code) rather than **Measured** (independently reproducible from a committed result):

```bash
cd backend
uv run python evaluation/evaluate_recommenders.py
```

## Collaborative filtering evaluation (Precision, Recall, NDCG)

**Script**: `backend/evaluation/cf_split.py`. **Metrics**: Precision@10, Recall@10, NDCG@10 (binary relevance, `rating ≥ 8.0` = "liked"). **Models**: `cf_item_cosine`, `cf_als` only.

**Split**: per-user 80/20 (`sklearn.model_selection.train_test_split(group, test_size=0.2, random_state=42)`, grouped by user), evaluated on 1,000 users sampled (`np.random.seed(42)`) from those with 10-100 ratings. Users outside that range, or not sampled, are entirely in the training set.

**Status: code exists and runs; results are not persisted to a file.** Same situation as the two scripts above — no output file, no numbers to report. Reproduce:

```bash
cd backend
uv run python evaluation/cf_split.py
```

## ABSA evaluation

**Status: does not exist.** There is no ground-truth aspect-sentiment annotation set anywhere in the repository, so no classification accuracy (precision/recall/F1) can be computed or reported. Coverage of the ABSA pipeline itself (which games, how many reviews) is documented in [docs/ml/absa.md](absa.md) — that is coverage, not accuracy.

## LLM summarization evaluation

**Status: does not exist.** No human-rated quality score, no automated faithfulness/hallucination check beyond the prompt's own instructions to the model. See [docs/ml/absa.md](absa.md#downstream-llm-summarization-community-consensus-paragraph).

## Assistant intent-parsing evaluation

**Status: does not exist as a benchmark.** `backend/test_orchestrator.py` runs 3 hardcoded natural-language queries through the live parse→orchestrate pipeline and prints the result — no assertions, no expected-output comparison, no aggregate accuracy metric. See [docs/engineering/testing.md](../engineering/testing.md).

## Summary table

| System | Metric(s) defined in code | Results file committed | Numbers reportable here |
|---|---|---|---|
| Search | MRR@10, NDCG@10, Recall@100 | ❌ | None |
| Recommenders — diversity | Coverage, ILD@10 | ❌ | 6 values obtainable by rerunning the script; not shown in the UI, labeled "Observed" not "Measured" |
| Recommenders — CF ranking quality | Precision@10, Recall@10, NDCG@10 | ❌ | None |
| ABSA | — (no ground truth exists) | — | None |
| LLM summarization | — (no rubric exists) | — | None |
| Assistant parsing | — (no benchmark exists) | — | None |

## Highest-value next step

Every evaluation script in this repository already computes the right metrics — the missing piece in all three cases is a single line writing the result to a JSON file under version control. That is a low-effort, high-credibility fix: it would convert six "Observed" numbers into "Measured" numbers, and produce the first-ever committed evidence for search and CF ranking quality.
