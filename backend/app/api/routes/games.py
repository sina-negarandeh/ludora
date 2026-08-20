
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.game import GameResponse, PaginatedGames, PaginatedReviews
from app.services.aspect_service import AspectAggregateResponse, AspectService
from app.services.game_service import GameService
from app.services.review_service import ReviewService

router = APIRouter()

@router.get("/", response_model=PaginatedGames, summary="Search and Filter Games", description="Retrieve a paginated list of board games. Supports lexical search via the 'query' parameter, filtering by subdomains, categories, mechanics, themes, families, designers, artists, publishers, player counts, weight, playtime, and year published. Allows sorting by rank, rating, and other metrics.")
def get_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("rank"),
    order: str = Query("asc"),
    query: str | None = None,
    subdomains: list[str] | None = Query(None),
    categories: list[str] | None = Query(None),
    themes: list[str] | None = Query(None),
    families: list[str] | None = Query(None),
    mechanics: list[str] | None = Query(None),
    designers: list[str] | None = Query(None),
    artists: list[str] | None = Query(None),
    publishers: list[str] | None = Query(None),
    exact_players: int | None = None,
    min_players: int | None = None,
    max_players: int | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    min_playtime: int | None = None,
    max_playtime: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
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
    # games is list[Game] (ORM objects), not list[GameResponse] -- Pydantic
    # coerces them via GameResponse's from_attributes=True at validation
    # time, which pyright's static types can't see through.
    return PaginatedGames(total=total, items=games)  # pyright: ignore[reportArgumentType]

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
    min_rating: float | None = Query(None),
    max_rating: float | None = Query(None),
    language: str | None = Query(None),
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

@router.get("/{game_id}/aspects", response_model=list[AspectAggregateResponse], summary="Get Aspect-Based Sentiment Analysis", description="Retrieve the aggregated positive/negative community sentiment towards specific game aspects (e.g., 'Rulebook', 'Downtime') extracted via zero-shot DeBERTa classification.")
def get_game_aspects(game_id: int, db: Session = Depends(get_db)):
    return AspectService(db).get_game_aspects(game_id)
