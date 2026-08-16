from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database.session import get_db
from app.schemas.game import GameResponse, PaginatedGames, PaginatedReviews
from app.services.game_service import GameService
from app.services.review_service import ReviewService
from app.services.aspect_service import AspectService, AspectAggregateResponse

router = APIRouter()

@router.get("/", response_model=PaginatedGames)
def get_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("rank"),
    order: str = Query("asc"),
    query: Optional[str] = None,
    categories: Optional[List[str]] = Query(None),
    themes: Optional[List[str]] = Query(None),
    mechanics: Optional[List[str]] = Query(None),
    exact_players: Optional[int] = None,
    min_players: Optional[int] = None,
    max_players: Optional[int] = None,
    min_weight: Optional[float] = None,
    max_weight: Optional[float] = None,
    db: Session = Depends(get_db)
):
    service = GameService(db)
    total, games = service.get_games(
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        order=order,
        query_str=query,
        categories=categories,
        themes=themes,
        mechanics=mechanics,
        exact_players=exact_players,
        min_players=min_players,
        max_players=max_players,
        min_weight=min_weight,
        max_weight=max_weight
    )
    return PaginatedGames(total=total, items=games)

class CompareRequest(BaseModel):
    game_ids: List[int]

@router.post("/compare", response_model=List[GameResponse])
def compare_games(request: CompareRequest, db: Session = Depends(get_db)):
    service = GameService(db)
    return service.compare_games(request.game_ids)

@router.get("/{bgg_id}", response_model=GameResponse)
def get_game(bgg_id: int, db: Session = Depends(get_db)):
    game = GameService(db).get_game(bgg_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@router.get("/{bgg_id}/reviews", response_model=PaginatedReviews)
def get_game_reviews(
    bgg_id: int, 
    page: int = Query(1, ge=1), 
    page_size: int = Query(10, ge=1, le=50),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
    language: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    service = ReviewService(db)
    total, items = service.get_game_reviews(
        bgg_id, page, page_size, min_rating, max_rating, language
    )
    language_breakdown, rating_breakdown = service.get_game_review_stats(bgg_id)
    
    return {
        "total": total, 
        "language_breakdown": language_breakdown, 
        "rating_breakdown": rating_breakdown,
        "items": items
    }

class AspectAggregateResponse(BaseModel):
    aspect: str
    positive_count: int
    negative_count: int
    mixed_count: int
    neutral_count: int
    total_mentions: int
    mean_sentiment: float
    evidence_samples: List[str]

@router.get("/{game_id}/aspects", response_model=List[AspectAggregateResponse])
def get_game_aspects(game_id: int, db: Session = Depends(get_db)):
    return AspectService(db).get_game_aspects(game_id)
