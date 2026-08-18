from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.game import GameResponse
from typing import List
from pydantic import BaseModel

from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["recommendations"])

from pydantic import Field

class RecommendationItemSchema(BaseModel):
    game: GameResponse = Field(..., description="The recommended game.")
    score: float = Field(..., description="The recommendation score.")
    reason: List[str] = Field(..., description="Reasons for this recommendation.")

class RecommendationResponseSchema(BaseModel):
    source_game: GameResponse = Field(..., description="The game the recommendations are based on.")
    model: str = Field(..., description="The ID of the model used.")
    recommendations: List[RecommendationItemSchema] = Field(..., description="List of recommended games.")

class RecommendationModelSchema(BaseModel):
    id: str = Field(..., description="The internal ID of the model.")
    family: str = Field(..., description="The algorithmic family (e.g. 'collaborative', 'content').")
    name: str = Field(..., description="Human-readable name of the model.")
    description: str = Field(..., description="Detailed description of how the model works.")

class ModelsResponseSchema(BaseModel):
    models: List[RecommendationModelSchema] = Field(..., description="List of available recommendation models.")

@router.get("/recommendation-models", response_model=ModelsResponseSchema, summary="Get Recommendation Models", description="Retrieve a list of all available recommendation models and algorithms.")
def get_models(db: Session = Depends(get_db)):
    service = RecommendationService(db)
    return {"models": service.get_recommendation_models()}

@router.get("/games/{game_id}/recommendations", response_model=RecommendationResponseSchema, summary="Get Game Recommendations", description="Fetch personalized recommendations for a specific game based on the selected algorithmic model.")
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
