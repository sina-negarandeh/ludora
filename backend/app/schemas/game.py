from pydantic import BaseModel
from typing import Optional, List

class GameBase(BaseModel):
    name: str
    description: Optional[str] = None
    year_published: Optional[int] = None
    game_weight: Optional[float] = None
    avg_rating: Optional[float] = None
    min_players: Optional[int] = None
    max_players: Optional[int] = None
    mfg_playtime: Optional[int] = None
    min_age: Optional[int] = None
    image_path: Optional[str] = None
    rank: Optional[int] = None
    categories: Optional[str] = None

class GameCreate(GameBase):
    bgg_id: int

class GameResponse(GameBase):
    bgg_id: int

    class Config:
        from_attributes = True

class PaginatedGames(BaseModel):
    total: int
    items: List[GameResponse]
