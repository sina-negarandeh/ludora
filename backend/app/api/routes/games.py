from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.schemas.game import GameResponse, PaginatedGames, PaginatedReviews
from app.services.game_service import GameService
from app.services.review_service import ReviewService
from app.services.aspect_service import AspectService, AspectAggregateResponse

router = APIRouter()

@router.get("/", response_model=PaginatedGames, summary="Search and Filter Games", description="Retrieve a paginated list of board games. Supports lexical search via the 'query' parameter, filtering by subdomains, categories, mechanics, themes, families, designers, artists, publishers, player counts, weight, playtime, and year published. Allows sorting by rank, rating, and other metrics.")
def get_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("rank"),
    order: str = Query("asc"),
    query: Optional[str] = None,
    subdomains: Optional[List[str]] = Query(None),
    categories: Optional[List[str]] = Query(None),
    themes: Optional[List[str]] = Query(None),
    families: Optional[List[str]] = Query(None),
    mechanics: Optional[List[str]] = Query(None),
    designers: Optional[List[str]] = Query(None),
    artists: Optional[List[str]] = Query(None),
    publishers: Optional[List[str]] = Query(None),
    exact_players: Optional[int] = None,
    min_players: Optional[int] = None,
    max_players: Optional[int] = None,
    min_weight: Optional[float] = None,
    max_weight: Optional[float] = None,
    min_playtime: Optional[int] = None,
    max_playtime: Optional[int] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    service = GameService(db)
    total, games = service.get_games(
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        order=order,
        query_str=query,
        subdomains=subdomains,
        categories=categories,
        themes=themes,
        families=families,
        mechanics=mechanics,
        designers=designers,
        artists=artists,
        publishers=publishers,
        exact_players=exact_players,
        min_players=min_players,
        max_players=max_players,
        min_weight=min_weight,
        max_weight=max_weight,
        min_playtime=min_playtime,
        max_playtime=max_playtime,
        min_year=min_year,
        max_year=max_year
    )
    return PaginatedGames(total=total, items=games)

@router.get("/{bgg_id}", response_model=GameResponse, summary="Get Game Details", description="Fetch comprehensive metadata, including LLM-generated community consensus summaries, for a single board game by its BoardGameGeek ID.")
def get_game(bgg_id: int, db: Session = Depends(get_db)):
    game = GameService(db).get_game(bgg_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@router.get("/{bgg_id}/reviews", response_model=PaginatedReviews, summary="Get Game Reviews", description="Fetch paginated user reviews for a specific game. Includes breakdown statistics for languages and star ratings.")
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

@router.get("/{game_id}/aspects", response_model=List[AspectAggregateResponse], summary="Get Aspect-Based Sentiment Analysis", description="Retrieve the aggregated positive/negative community sentiment towards specific game aspects (e.g., 'Rulebook', 'Downtime') extracted via zero-shot DeBERTa classification.")
def get_game_aspects(game_id: int, db: Session = Depends(get_db)):
    return AspectService(db).get_game_aspects(game_id)
