from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.database.models import GameRecommendation, Game
from app.schemas.game import GameResponse
from typing import List, Optional
from pydantic import BaseModel

from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["recommendations"])

class RecommendationItemSchema(BaseModel):
    game: GameResponse
    score: float
    reason: List[str]

class RecommendationResponseSchema(BaseModel):
    source_game: GameResponse
    model: str
    recommendations: List[RecommendationItemSchema]

class RecommendationModelSchema(BaseModel):
    id: str
    family: str
    name: str
    description: str

class ModelsResponseSchema(BaseModel):
    models: List[RecommendationModelSchema]

@router.get("/recommendation-models", response_model=ModelsResponseSchema)
def get_models(db: Session = Depends(get_db)):
    service = RecommendationService(db)
    return {"models": service.get_recommendation_models()}

@router.get("/games/{game_id}/recommendations", response_model=RecommendationResponseSchema)
def get_recommendations(
    game_id: int, 
    model: str = Query("hybrid", description="Recommendation model to use"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    service = RecommendationService(db)
    source_game, recs = service.get_recommendations(game_id, model, limit)
    
    if not source_game:
        raise HTTPException(status_code=404, detail="Game not found")

    return RecommendationResponseSchema(
        source_game=source_game,
        model=model,
        recommendations=recs
    )
