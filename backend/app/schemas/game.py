from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime

class ThemeMetadata(BaseModel):
    id: int
    name: str
    game_count: int

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
    num_ratings: Optional[int] = None
    rating_distribution: Optional[List[int]] = None
    category_ranks: Optional[dict[str, int]] = None
    categories: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)
    designers: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    artists: list[str] = Field(default_factory=list)

class GameCreate(GameBase):
    bgg_id: int

class GameResponse(GameBase):
    bgg_id: int
    customer_summary: Optional[str] = None

    @field_validator('categories', 'themes', 'mechanics', 'designers', 'publishers', 'artists', mode='before')
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

class ReviewResponse(BaseModel):
    id: int
    user: str
    rating: Optional[float] = None
    comment: Optional[str] = None
    created_at: Optional[datetime] = None

class PaginatedReviews(BaseModel):
    total: int
    language_breakdown: Optional[Dict[str, float]] = None
    rating_breakdown: Optional[Dict[str, float]] = None
    items: List[ReviewResponse]
