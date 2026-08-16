from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime

class ThemeMetadata(BaseModel):
    id: int
    name: str
    game_count: int

class GameBase(BaseModel):
    name: str = Field(..., description="The official title of the board game.")
    description: Optional[str] = Field(None, description="Rich HTML description of the game, provided by BoardGameGeek.")
    year_published: Optional[int] = Field(None, description="The year the game was originally published.")
    game_weight: Optional[float] = Field(None, description="Complexity rating on a scale of 1.0 (light) to 5.0 (heavy).")
    avg_rating: Optional[float] = Field(None, description="Average community rating on a scale of 1.0 to 10.0.")
    min_players: Optional[int] = Field(None, description="Minimum number of players supported.")
    max_players: Optional[int] = Field(None, description="Maximum number of players supported.")
    mfg_playtime: Optional[int] = Field(None, description="Manufacturer's estimated playtime in minutes.")
    min_age: Optional[int] = Field(None, description="Minimum recommended age.")
    image_path: Optional[str] = Field(None, description="URL or relative path to the game's box art image.")
    rank: Optional[int] = Field(None, description="The overall BoardGameGeek ranking of the game.")
    num_ratings: Optional[int] = Field(None, description="Total number of users who have rated this game.")
    rating_distribution: Optional[List[int]] = Field(None, description="Array of 10 integers representing the count of ratings from 1 to 10.")
    category_ranks: Optional[dict[str, int]] = Field(None, description="Dictionary mapping subcategory names (e.g., 'Strategy Game') to their rank.")
    categories: list[str] = Field(default_factory=list, description="List of category tags (e.g., 'Economic', 'Fantasy').")
    themes: list[str] = Field(default_factory=list, description="List of thematic tags.")
    mechanics: list[str] = Field(default_factory=list, description="List of mechanics (e.g., 'Worker Placement', 'Deck Building').")
    designers: list[str] = Field(default_factory=list, description="List of game designers.")
    publishers: list[str] = Field(default_factory=list, description="List of game publishers.")
    artists: list[str] = Field(default_factory=list, description="List of artists who contributed to the game's visuals.")

class GameCreate(GameBase):
    bgg_id: int = Field(..., description="The unique BoardGameGeek identifier.")

class GameResponse(GameBase):
    bgg_id: int = Field(..., description="The unique BoardGameGeek identifier.")
    customer_summary: Optional[str] = Field(None, description="LLM-generated text summarizing the community's overall sentiment based on reviews.")

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
