import sys
import os
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_distances

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import GameRecommendation, Game, GameEmbedding
from app.core.config import settings
from app.core.ml_config import SearchConfig
from app.core.mlflow_utils import tracked_run, write_results_json
import mlflow

def main():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # "embedding" and "hybrid" are deliberately excluded: both are served
    # live (RecommendationService.get_recommendations), never written to
    # game_recommendations, so a coverage/ILD query against this table would
    # always read zero rows for them -- there's nothing here for those two
    # to evaluate.
    models = ['metadata', 'tfidf', 'graph_jaccard', 'deepwalk', 'cf_item_cosine', 'cf_als']
    # Technique-family grouping, matching the precompute/training-side experiments —
    # so a model's eval run lands in the same MLflow experiment as its training run.
    MODEL_EXPERIMENT = {
        'metadata': 'recommender/content_based', 'tfidf': 'recommender/content_based',
        'graph_jaccard': 'recommender/graph', 'deepwalk': 'recommender/graph',
        'cf_item_cosine': 'recommender/collaborative', 'cf_als': 'recommender/collaborative',
    }

    print("Loading game embeddings for diversity calculation...")
    rows = session.query(GameEmbedding.game_id, GameEmbedding.embedding).filter(
        GameEmbedding.model == SearchConfig.EMBEDDING_MODEL
    ).all()
    embeddings_map = {r.game_id: np.array(r.embedding) for r in rows}
    total_games = session.query(Game).count()

    print("Evaluating models...")
    all_results = {}
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
            
        mean_ild = float(np.mean(ild_scores)) if ild_scores else 0.0

        print(f"[{model.upper()}] Catalog Coverage: {coverage:.2%} | ILD@10: {mean_ild:.4f}")

        with tracked_run(MODEL_EXPERIMENT[model], run_name=f"{model}_eval_coverage_ild"):
            mlflow.log_metrics({"catalog_coverage": float(coverage), "ild_at_10": mean_ild})

        all_results[model] = {"catalog_coverage": float(coverage), "ild_at_10": mean_ild}

    write_results_json("recommenders_coverage_ild", all_results)

if __name__ == "__main__":
    main()
