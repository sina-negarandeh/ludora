import sys
import os
import json
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append('/app')

import mlflow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.mlflow_utils import tracked_run, write_results_json
from app.services.search_service import SearchService
from app.schemas.search import SearchQuery, SearchMode

def mrr_at_k(results, expected_ids, k=10):
    for i, res in enumerate(results[:k]):
        if res.game.bgg_id in expected_ids:
            return 1.0 / (i + 1)
    return 0.0

def ndcg_at_k(results, expected_ids, k=10):
    dcg = 0.0
    idcg = 0.0
    for i in range(min(len(expected_ids), k)):
        idcg += 1.0 / math.log2(i + 2)
        
    for i, res in enumerate(results[:k]):
        if res.game.bgg_id in expected_ids:
            dcg += 1.0 / math.log2(i + 2)
            
    return dcg / idcg if idcg > 0 else 0.0

def recall_at_k(results, expected_ids, k=100):
    found = sum(1 for res in results[:k] if res.game.bgg_id in expected_ids)
    return found / len(expected_ids) if expected_ids else 0.0

def evaluate_mode(service, queries, mode):
    print(f"\nEvaluating mode: {mode}")
    total_mrr = 0.0
    total_ndcg = 0.0
    total_recall = 0.0

    for item in queries:
        q = item["query"]
        expected = item["expected_bgg_ids"]

        search_q = SearchQuery(q=q, mode=SearchMode(mode))
        results_page = service.search(search_q, skip=0, limit=100)
        results = results_page.items

        mrr = mrr_at_k(results, expected, 10)
        ndcg = ndcg_at_k(results, expected, 10)
        recall = recall_at_k(results, expected, 100)

        total_mrr += mrr
        total_ndcg += ndcg
        total_recall += recall

    n = len(queries)
    metrics = {
        "mrr_at_10": total_mrr / n,
        "ndcg_at_10": total_ndcg / n,
        "recall_at_100": total_recall / n,
    }
    print(f"MRR@10: {metrics['mrr_at_10']:.4f}")
    print(f"NDCG@10: {metrics['ndcg_at_10']:.4f}")
    print(f"Recall@100: {metrics['recall_at_100']:.4f}")

    with tracked_run("search/retrieval_eval", run_name=mode):
        mlflow.log_params({"mode": mode, "n_queries": n})
        mlflow.log_metrics(metrics)
    write_results_json(f"search_{mode}", {"mode": mode, "n_queries": n, **metrics})

def top_ids(service, q, mode, k):
    page = service.search(SearchQuery(q=q, mode=SearchMode(mode)), skip=0, limit=k)
    return [r.game.bgg_id for r in page.items]

def evaluate_case_invariance(service, queries, mode, k=10):
    """Does capitalizing or padding a query change what comes back?

    Kept out of `search_queries.json` on purpose. `evaluate_mode` averages
    over every query in that file and writes only the aggregate, so adding a
    sixth entry would move all three quality metrics and silently make the
    committed baseline in `results/` non-comparable. This asks a different
    question anyway: not "how good are the results" but "are they the same
    results", which is the property query normalization is supposed to
    guarantee and the only one the existing five queries cannot test, since
    all five are already lowercase.
    """
    print(f"\nCase invariance ({mode}):")
    identical = 0

    for item in queries:
        q = item["query"]
        baseline = top_ids(service, q, mode, k)
        variants = [q.upper(), q.title(), f"  {q}  "]

        if all(top_ids(service, v, mode, k) == baseline for v in variants):
            identical += 1
        else:
            print(f"  DIFFERS: {q!r}")

    rate = identical / len(queries) if queries else 0.0
    print(f"  identical top-{k} for every variant: {identical}/{len(queries)}")

    # Its own file, so the three quality baselines stay byte-comparable.
    write_results_json(
        f"search_case_invariance_{mode}",
        {"mode": mode, "n_queries": len(queries), f"invariant_at_{k}": rate},
    )

def main():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    service = SearchService(session)
    
    with open(os.path.join(os.path.dirname(__file__), 'search_queries.json')) as f:
        queries = json.load(f)
        
    for mode in ("lexical", "semantic", "hybrid"):
        evaluate_mode(service, queries, mode)
        evaluate_case_invariance(service, queries, mode)

if __name__ == "__main__":
    main()
