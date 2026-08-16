from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.database.session import get_db
from app.database.models import Game, Review
from app.schemas.game import GameResponse, PaginatedGames, ThemeMetadata, PaginatedReviews
from app.services.game_query_service import GameQueryService

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
    service = GameQueryService(db)
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

@router.get("/categories", response_model=List[str])
def get_categories(db: Session = Depends(get_db)):
    return GameQueryService(db).get_categories()

@router.get("/themes", response_model=List[ThemeMetadata])
def get_themes(db: Session = Depends(get_db)):
    return GameQueryService(db).get_themes()

@router.get("/mechanics", response_model=List[str])
def get_mechanics(db: Session = Depends(get_db)):
    return GameQueryService(db).get_mechanics()

@router.get("/designers", response_model=List[str])
def get_designers(db: Session = Depends(get_db)):
    return GameQueryService(db).get_designers()

@router.get("/publishers", response_model=List[str])
def get_publishers(db: Session = Depends(get_db)):
    return GameQueryService(db).get_publishers()

@router.get("/{bgg_id}", response_model=GameResponse)
def get_game(bgg_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.bgg_id == bgg_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@router.get("/{bgg_id}/reviews", response_model=PaginatedReviews)
def get_game_reviews(
    bgg_id: int, 
    page: int = Query(1, ge=1), 
    page_size: int = Query(10, ge=1, le=50), 
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    total = db.query(func.count(Review.id)).filter(Review.game_id == bgg_id).scalar()
    
    # We want to show comments first if possible, or order by newest, or rating?
    # Let's order by those with comments first, then by date descending.
    reviews = db.query(Review).filter(Review.game_id == bgg_id)\
        .order_by(Review.comment.is_(None), Review.created_at.desc().nullslast(), Review.rating.desc().nullslast(), Review.id.desc())\
        .offset(skip).limit(page_size).all()
        
    items = []
    for r in reviews:
        items.append({
            "id": r.id,
            "user": r.user.external_user_id if r.user else "Anonymous",
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at
        })
        
    return {"total": total, "items": items}
