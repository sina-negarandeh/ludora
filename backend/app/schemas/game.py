from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Dict

class ThemeMetadata(BaseModel):
    id: int
    name: str
    game_count: int

class SubdomainMetadata(BaseModel):
    id: int
    name: str
    game_count: int

class SubfamilyMetadata(BaseModel):
    id: int
    value: str
    name: str
    game_count: int

class FamilyGroupMetadata(BaseModel):
    group: str
    values: List[SubfamilyMetadata]

class GameBase(BaseModel):
    name: str = Field(..., description="The official title of the board game.")
    description: Optional[str] = Field(None, description="Rich HTML description of the game, provided by BoardGameGeek.")
    year_published: Optional[int] = Field(None, description="The year the game was originally published.")
    game_weight: Optional[float] = Field(None, description="Complexity rating on a scale of 1.0 (light) to 5.0 (heavy).")
    avg_rating: Optional[float] = Field(None, description="Average community rating on a scale of 1.0 to 10.0.")
    bayes_avg_rating: Optional[float] = Field(None, description="BGG's Bayesian-weighted average rating — the value BGG itself uses for ranking.")
    stddev_rating: Optional[float] = Field(None, description="Standard deviation of community ratings.")
    num_weight_votes: Optional[int] = Field(None, description="Number of users who voted on this game's complexity weight.")
    min_players: Optional[int] = Field(None, description="Minimum number of players supported.")
    max_players: Optional[int] = Field(None, description="Maximum number of players supported.")
    mfg_playtime: Optional[int] = Field(None, description="Manufacturer's estimated playtime in minutes.")
    min_playtime: Optional[int] = Field(None, description="Community-reported minimum playtime in minutes.")
    max_playtime: Optional[int] = Field(None, description="Community-reported maximum playtime in minutes.")
    min_age: Optional[int] = Field(None, description="Minimum recommended age.")
    image_path: Optional[str] = Field(None, description="URL or relative path to the game's box art image.")
    thumbnail_url: Optional[str] = Field(None, description="URL to a smaller thumbnail variant of the box art.")
    kickstarted: Optional[bool] = Field(None, description="Whether this game originated as a Kickstarter project.")
    is_reimplementation: Optional[bool] = Field(None, description="Whether this game is a reimplementation of an earlier game.")
    rank: Optional[int] = Field(None, description="The overall BoardGameGeek ranking of the game.")
    num_ratings: Optional[int] = Field(None, description="Total number of users who have rated this game.")
    num_comments: Optional[int] = Field(None, description="Total number of users who have left a text review/comment for this game.")
    rating_distribution: Optional[List[int]] = Field(None, description="Array of 10 integers representing the count of ratings from 1 to 10.")
    subdomain_ranks: Optional[dict[str, int]] = Field(None, description="Dictionary mapping subdomain names (e.g., 'Strategy') to this game's rank within that subdomain.")
    suggested_num_players: Optional[List[Dict[str, Any]]] = Field(None, description="Raw BGG community poll: Best/Recommended/Not Recommended vote counts per player count.")
    suggested_playerage: Optional[List[Dict[str, Any]]] = Field(None, description="Raw BGG community poll: recommended-age vote counts.")
    suggested_language_dependence: Optional[List[Dict[str, Any]]] = Field(None, description="Raw BGG community poll: language-dependence vote counts.")

    @field_validator("suggested_num_players", "suggested_playerage", "suggested_language_dependence", mode="before")
    @classmethod
    def _normalize_single_poll_entry(cls, v):
        # BGG's raw XML-to-JSON poll data collapses a single-entry poll list
        # down to a bare object instead of a one-item list (an xmltodict-style
        # single-child quirk from ingestion) — wrap it back into a list rather
        # than reject or drop it.
        if isinstance(v, dict):
            return [v]
        return v
    subdomains: list[str] = Field(default_factory=list, description="BGG's rank/leaderboard classification (e.g., 'Strategy', 'Family') — not a content tag.")
    categories: list[str] = Field(default_factory=list, description="BGG's real Category tags (e.g., 'Economic', 'Fantasy').")
    themes: list[str] = Field(default_factory=list, description="BGG Family 'Theme:' tags — narrow setting/franchise tags (e.g., 'Cthulhu Mythos'), distinct from Category.")
    families: list[str] = Field(default_factory=list, description="BGG Family tags across all 72 namespaces (e.g., 'Animals: Bears', 'Mechanism: 4X'), shown as 'Group: Value'.")
    mechanics: list[str] = Field(default_factory=list, description="List of mechanics (e.g., 'Worker Placement', 'Deck Building').")
    designers: list[str] = Field(default_factory=list, description="List of game designers.")
    publishers: list[str] = Field(default_factory=list, description="List of game publishers.")
    artists: list[str] = Field(default_factory=list, description="List of artists who contributed to the game's visuals.")

class GameCreate(GameBase):
    bgg_id: int = Field(..., description="The unique BoardGameGeek identifier.")

class GameResponse(GameBase):
    bgg_id: int = Field(..., description="The unique BoardGameGeek identifier.")
    customer_summary: Optional[str] = Field(None, description="LLM-generated text summarizing the community's overall sentiment based on reviews.")

    @field_validator('subdomains', 'categories', 'themes', 'families', 'mechanics', 'designers', 'publishers', 'artists', mode='before')
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

class PaginatedReviews(BaseModel):
    total: int
    language_breakdown: Optional[Dict[str, float]] = None
    rating_breakdown: Optional[Dict[str, float]] = None
    items: List[ReviewResponse]
