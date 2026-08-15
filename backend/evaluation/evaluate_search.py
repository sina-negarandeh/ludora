import sys
import os
import json
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
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
    print(f"MRR@10: {total_mrr / n:.4f}")
    print(f"NDCG@10: {total_ndcg / n:.4f}")
    print(f"Recall@100: {total_recall / n:.4f}")

def main():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    service = SearchService(session)
    
    with open(os.path.join(os.path.dirname(__file__), 'search_queries.json')) as f:
        queries = json.load(f)
        
    evaluate_mode(service, queries, "lexical")
    evaluate_mode(service, queries, "semantic")
    evaluate_mode(service, queries, "hybrid")

if __name__ == "__main__":
    main()
