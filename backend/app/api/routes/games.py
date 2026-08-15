from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database.session import get_db
from app.database.models import Game
from app.schemas.game import GameResponse, PaginatedGames

router = APIRouter()

@router.get("/", response_model=PaginatedGames)
def get_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    total = db.query(func.count(Game.bgg_id)).scalar()
    games = db.query(Game).offset(skip).limit(limit).all()
    
    return PaginatedGames(total=total, items=games)

@router.get("/{bgg_id}", response_model=GameResponse)
def get_game(bgg_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.bgg_id == bgg_id).first()
    return game
