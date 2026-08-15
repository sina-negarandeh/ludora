import sys
import os
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import GameRecommendation, Game
from app.core.config import settings

def dcg_at_k(r, k):
    r = np.asfarray(r)[:k]
    if r.size:
        return np.sum(r / np.log2(np.arange(2, r.size + 2)))
    return 0.

def ndcg_at_k(r, k):
    dcg_max = dcg_at_k(sorted(r, reverse=True), k)
    if not dcg_max:
        return 0.
    return dcg_at_k(r, k) / dcg_max

def main():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    models = ['metadata', 'tfidf', 'embedding', 'hybrid', 'graph_jaccard', 'node2vec']
    
    print("Evaluating models...")
    for model in models:
        # 1. Catalog Coverage
        # Percentage of total games that appear in the top 10 recommendations across ALL games
        unique_recs = session.query(GameRecommendation.recommended_game_id).filter(
            GameRecommendation.model == model
        ).distinct().count()
        
        total_games = session.query(Game).count()
        coverage = unique_recs / total_games if total_games > 0 else 0
        
        print(f"[{model.upper()}] Catalog Coverage: {coverage:.2%} ({unique_recs}/{total_games} games)")

if __name__ == "__main__":
    main()
