from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.session import get_db
from app.database.models import Game
from app.schemas.game import GameResponse, PaginatedGames
from app.services.game_query_service import GameQueryService

router = APIRouter()

@router.get("/", response_model=PaginatedGames)
def get_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("rank"),
    order: str = Query("asc"),
    query: Optional[str] = None,
    category: Optional[str] = None,
    mechanic: Optional[str] = None,
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
        category=category,
        mechanic=mechanic,
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
