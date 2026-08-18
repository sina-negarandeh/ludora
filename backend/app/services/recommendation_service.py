from sqlalchemy.orm import Session, joinedload
from app.database.models import GameRecommendation, Game, GameEmbedding
from app.core.ml_config import SearchConfig
from typing import List, Dict

class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def get_recommendation_models(self) -> List[Dict]:
        return [
            {
                "id": "embedding",
                "family": "content",
                "name": "Semantic Embedding",
                "description": "Recommends games with semantically similar descriptions and metadata using local pgvector search."
            },
            {
                "id": "hybrid",
                "family": "content",
                "name": "Content Hybrid",
                "description": "Combines semantic embeddings, TF-IDF, metadata, and quality signals."
            },
            {
                "id": "popularity",
                "family": "baseline",
                "name": "Global Popularity",
                "description": "Returns universally popular and highly ranked games."
            }
        ]

    def get_recommendations(self, game_id: int, model: str, limit: int = 10):
        source_game = self.db.query(Game).filter(Game.bgg_id == game_id).first()
        if not source_game:
            return None, []

        if model == "popularity":
            top_games = self.db.query(Game).order_by(Game.rank.asc()).filter(Game.rank.isnot(None), Game.bgg_id != game_id).limit(limit).all()
            recs = [{"game": g, "score": 1.0, "reason": ["Highly ranked universally popular game"]} for g in top_games]
            return source_game, recs

        if model in ["embedding", "metadata", "tfidf", "hybrid"]:
            source_embedding = self.db.query(GameEmbedding).filter(
                GameEmbedding.game_id == game_id,
                GameEmbedding.model == SearchConfig.EMBEDDING_MODEL,
            ).first()
            if source_embedding is None:
                return source_game, []

            similar = (
                self.db.query(GameEmbedding)
                .options(joinedload(GameEmbedding.game))
                .filter(
                    GameEmbedding.game_id != game_id,
                    GameEmbedding.model == SearchConfig.EMBEDDING_MODEL,
                )
                .order_by(GameEmbedding.embedding.cosine_distance(source_embedding.embedding))
                .limit(limit)
                .all()
            )

            recs = [{"game": e.game, "score": 1.0, "reason": ["Semantically similar based on rich metadata"]} for e in similar]
            return source_game, recs

        # Precomputed collaborative models (ALS, Node2Vec, etc.)
        db_recs = self.db.query(GameRecommendation).filter(
            GameRecommendation.game_id == game_id,
            GameRecommendation.model == model
        ).order_by(GameRecommendation.score.desc()).limit(limit).all()

        recs = []
        for r in db_recs:
            if not r.recommended_game: continue
            recs.append({
                "game": r.recommended_game,
                "score": round(r.score, 4),
                "reason": r.reasons or []
            })

        return source_game, recs
