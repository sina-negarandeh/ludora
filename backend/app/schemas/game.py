from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any

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
    categories: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)
    designers: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    artists: list[str] = Field(default_factory=list)

class GameCreate(GameBase):
    bgg_id: int

class GameResponse(GameBase):
    bgg_id: int

    @field_validator('categories', 'mechanics', 'designers', 'publishers', 'artists', mode='before')
    @classmethod
    def extract_names(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], str):
            return v
        return [item.name for item in v if hasattr(item, 'name')]

    class Config:
        from_attributes = True

class PaginatedGames(BaseModel):
    total: int
    items: List[GameResponse]
