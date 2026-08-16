from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.database.models import GameRecommendation, Game
from app.schemas.game import GameResponse
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/games", tags=["recommendations"])

class RecommendationItemSchema(BaseModel):
    game: GameResponse
    score: float
    reason: List[str]

class RecommendationResponseSchema(BaseModel):
    source_game: GameResponse
    model: str
    recommendations: List[RecommendationItemSchema]

@router.get("/{game_id}/recommendations", response_model=RecommendationResponseSchema)
def get_recommendations(
    game_id: int, 
    model: str = Query("hybrid", description="Recommendation model to use"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    source_game = db.query(Game).filter(Game.bgg_id == game_id).first()
    if not source_game:
        raise HTTPException(status_code=404, detail="Game not found")

    if model == "popularity":
        # Popularity is global
        top_games = db.query(Game).order_by(Game.rank.asc()).filter(Game.rank.isnot(None), Game.bgg_id != game_id).limit(limit).all()
        recs = []
        for g in top_games:
            recs.append(RecommendationItemSchema(
                game=g,
                score=1.0,
                reason=["Highly ranked universally popular game"]
            ))
        return RecommendationResponseSchema(
            source_game=source_game,
            model="popularity",
            recommendations=recs
        )

    # Alias frontend dummy content-based models to our new semantic embedding model
    if model in ["embedding", "metadata", "tfidf", "hybrid"]:
        # Semantic search on the fly via pgvector
        if source_game.embedding is None:
            return RecommendationResponseSchema(source_game=source_game, model="embedding", recommendations=[])
            
        similar_games = db.query(Game).filter(
            Game.bgg_id != game_id,
            Game.embedding.isnot(None)
        ).order_by(Game.embedding.cosine_distance(source_game.embedding)).limit(limit).all()
        
        recs = []
        for g in similar_games:
            recs.append(RecommendationItemSchema(
                game=g,
                score=1.0, # Could compute 1 - dist but pgvector handles the ordering
                reason=["Semantically similar based on rich metadata"]
            ))
            
        return RecommendationResponseSchema(
            source_game=source_game,
            model="embedding",
            recommendations=recs
        )

    # Fetch from precomputed table
    db_recs = db.query(GameRecommendation).filter(
        GameRecommendation.game_id == game_id,
        GameRecommendation.model == model
    ).order_by(GameRecommendation.score.desc()).limit(limit).all()

    items = []
    for r in db_recs:
        rg = r.recommended_game
        # Just in case the game is missing
        if not rg: continue
        items.append(RecommendationItemSchema(
            game=rg,
            score=round(r.score, 4),
            reason=r.reasons or []
        ))

    return RecommendationResponseSchema(
        source_game=source_game,
        model=model,
        recommendations=items
    )
