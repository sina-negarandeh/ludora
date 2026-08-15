import sys
import os
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_distances

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import GameRecommendation, Game
from app.core.config import settings

def main():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    models = ['metadata', 'tfidf', 'embedding', 'hybrid', 'graph_jaccard', 'node2vec', 'cf_item_cosine', 'cf_svd', 'cf_als']
    
    print("Loading game embeddings for diversity calculation...")
    games = session.query(Game.bgg_id, Game.embedding).filter(Game.embedding.isnot(None)).all()
    embeddings_map = {g.bgg_id: np.array(g.embedding) for g in games}
    total_games = session.query(Game).count()

    print("Evaluating models...")
    for model in models:
        # 1. Catalog Coverage
        unique_recs = session.query(GameRecommendation.recommended_game_id).filter(
            GameRecommendation.model == model
        ).distinct().count()
        
        coverage = unique_recs / total_games if total_games > 0 else 0
        
        # 2. Intra-List Diversity (ILD@10)
        recs = session.query(GameRecommendation.game_id, GameRecommendation.recommended_game_id).filter(
            GameRecommendation.model == model
        ).all()
        
        recs_dict = defaultdict(list)
        for r in recs:
            recs_dict[r.game_id].append(r.recommended_game_id)
            
        ild_scores = []
        for gid, recommended_ids in recs_dict.items():
            if len(recommended_ids) < 2:
                continue
            
            # Fetch embeddings for the recommended items
            list_embs = []
            for rid in recommended_ids:
                if rid in embeddings_map:
                    list_embs.append(embeddings_map[rid])
            
            if len(list_embs) < 2:
                continue
                
            list_embs = np.array(list_embs)
            distances = cosine_distances(list_embs)
            
            N = len(list_embs)
            sum_dist = np.sum(distances) / 2
            ild = sum_dist / (N * (N - 1) / 2)
            ild_scores.append(ild)
            
        mean_ild = np.mean(ild_scores) if ild_scores else 0
        
        print(f"[{model.upper()}] Catalog Coverage: {coverage:.2%} | ILD@10: {mean_ild:.4f}")

if __name__ == "__main__":
    main()
