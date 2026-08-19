# ML Evaluation

This page separates what's measured and reproducible from what's observed but not traceable to a committed file from what isn't evaluated at all. All three categories exist in this repository at once; read the status column carefully.

## Search evaluation

**Script**: `backend/evaluation/evaluate_search.py`. **Metrics**: MRR@10, NDCG@10 (binary relevance), Recall@100. **Test set**: `backend/evaluation/search_queries.json`, 5 hand-written queries, each with a small list of expected relevant BGG IDs (for example `"space exploration" → [182028, 169786, 11]`).

**Status: Measured.** Results are logged to MLflow and committed at `backend/evaluation/results/search_{mode}_latest.json` for all three modes:

| Mode | MRR@10 | NDCG@10 | Recall@100 |
|---|---|---|---|
| Lexical | 0.300 | 0.263 | 0.533 |
| Semantic | 0.467 | 0.370 | 0.433 |
| Hybrid | 0.500 | 0.379 | 0.433 |

Hybrid leads on MRR@10 and NDCG@10, the two rank-sensitive metrics; lexical leads on Recall@100, which only asks whether a relevant result showed up anywhere in the top 100, not where. That's the expected shape for a fusion method: RRF is pulling the best-ranked result from either signal to the top, at the cost of occasionally missing something lexical alone would eventually surface deeper in the list. To reproduce:

```bash
cd backend
uv run python evaluation/evaluate_search.py
```

5 queries is far too small a set to generalize from. Treat this as a smoke-test harness with real, reproducible numbers, not a benchmark.

## Recommender diversity evaluation (Coverage, ILD@10)

**Script**: `backend/evaluation/evaluate_recommenders.py`. **Metrics**: Catalog Coverage (share of the catalog that appears in any top-10 list for a model) and Intra-List Diversity @10 (mean pairwise cosine distance among a game's own recommended list, using `game_embeddings` for the currently-configured model). **Models evaluated**: `metadata`, `tfidf`, `graph_jaccard`, `deepwalk`, `cf_item_cosine`, `cf_als`, 6 of the 9 UI model IDs. `popularity` is excluded since a fixed popularity ranking has no natural per-game list to compute diversity over; `embedding` and `hybrid` are excluded because both are computed live and never written to `game_recommendations`, so a coverage/ILD query for either would always read 0 rows.

**Status: Observed, not yet Measured.** The script logs to MLflow and writes a results file (`write_results_json("recommenders_coverage_ild", ...)`) the same way the search evaluator does, but hasn't been run since that capability was added, so there's no committed `recommenders_coverage_ild_latest.json` yet.

### Where these numbers live

The UI doesn't show Coverage/ILD at all. `frontend/src/pages/GameDetail.tsx` fetches the model list live from `GET /api/recommendation-models` (`RecommendationService.get_recommendation_models()`, backed by `RECOMMENDATION_MODELS` in `backend/app/core/ml_config.py`), which returns id, name, paradigm, and description only, no diversity metrics. Run the script yourself to get numbers:

```bash
cd backend
uv run python evaluation/evaluate_recommenders.py
```

## Collaborative filtering evaluation (Precision, Recall, NDCG)

**Script**: `backend/evaluation/cf_split.py`. **Metrics**: Precision@10, Recall@10, NDCG@10 (binary relevance, `rating >= 8.0` counts as "liked"). **Models**: `cf_item_cosine`, `cf_als` only.

**Split**: per-user 80/20 (`sklearn.model_selection.train_test_split(group, test_size=0.2, random_state=42)`, grouped by user), evaluated on 1,000 users sampled (`np.random.seed(42)`) from those with 10 to 100 ratings. Users outside that range, or not sampled, are entirely in the training set.

**Status: Observed, not yet Measured.** Same capability as the recommender diversity script: it can log to MLflow and write a results file, but hasn't been run to produce a committed one. Reproduce:

```bash
cd backend
uv run python evaluation/cf_split.py
```

## ABSA evaluation

**Status: does not exist.** There's no ground-truth aspect-sentiment annotation set anywhere in the repository, so no classification accuracy (precision, recall, F1) can be computed or reported. Coverage of the ABSA pipeline itself (which games, how many reviews) is documented in [docs/ml/absa.md](absa.md); that's coverage, not accuracy.

## LLM summarization evaluation

**Status: does not exist.** No human-rated quality score, no automated faithfulness or hallucination check beyond the prompt's own instructions to the model. See [docs/ml/absa.md](absa.md#downstream-llm-summarization-community-consensus-paragraph).

## Assistant intent-parsing evaluation

**Status: does not exist as a benchmark.** `backend/test_orchestrator.py` runs a handful of hardcoded natural-language queries through the live parse-and-orchestrate pipeline and prints the result. No assertions, no expected-output comparison, no aggregate accuracy metric. See [docs/engineering/testing.md](../engineering/testing.md).

## Summary table

| System | Metric(s) defined in code | Results file committed | Numbers reportable here |
|---|---|---|---|
| Search | MRR@10, NDCG@10, Recall@100 | Yes, all 3 modes | See table above |
| Recommenders, diversity | Coverage, ILD@10 | Not yet | 6 values obtainable by rerunning the script; not shown in the UI, labeled Observed once run |
| Recommenders, CF ranking quality | Precision@10, Recall@10, NDCG@10 | Not yet | Obtainable by rerunning the script |
| ABSA | None; no ground truth exists | N/A | None |
| LLM summarization | None; no rubric exists | N/A | None |
| Assistant parsing | None; no benchmark exists | N/A | None |

## Highest-value next step

Search evaluation is the model for the rest: run `evaluate_recommenders.py` and `cf_split.py` once each and commit their results files the same way search's were committed, converting six more Observed numbers into Measured ones. After that, the next real gap is a ground-truth set for ABSA classification accuracy, since none of the three NLP/LLM systems (ABSA, summarization, assistant parsing) have any evaluation at all today, only coverage and reliability numbers.
