from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Shared sort vocabulary for both the plain browse endpoint
# (GameService.get_games' sort_by/order params) and search (SearchQuery.sort
# below) -- "year", not "year_published", to match the literal string the
# frontend's GamesList.tsx sort dropdown has always sent as sort_by.
SortField = Literal["rank", "rating", "year", "complexity", "name", "playtime"]
SortDirection = Literal["asc", "desc"]

# Single source of truth for which Game column each SortField maps to --
# shared by GameService.get_games (SQL ORDER BY) and SearchService.search
# (Python-side sort over already-fetched Game objects) so the two can't
# drift apart on what "sort by rating" means.
SORT_FIELD_TO_COLUMN = {
    "rank": "rank",
    "rating": "avg_rating",
    "year": "year_published",
    "complexity": "game_weight",
    "name": "name",
    "playtime": "mfg_playtime",
}

class SortSpec(BaseModel):
    field: SortField
    direction: SortDirection

class GameFilter(BaseModel):
    subdomains: Optional[List[str]] = Field(None, description="List of subdomains to filter by (BGG's rank/leaderboard classification, e.g. 'Strategy', 'Family').")
    categories: Optional[List[str]] = Field(None, description="List of categories to filter by.")
    themes: Optional[List[str]] = Field(None, description="List of themes to filter by.")
    families: Optional[List[str]] = Field(None, description="List of family tags to filter by (full 'Group: Value' form, e.g. 'Animals: Bears').")
    mechanics: Optional[List[str]] = Field(None, description="List of mechanics to filter by.")
    designers: Optional[List[str]] = Field(None, description="List of designers to filter by.")
    artists: Optional[List[str]] = Field(None, description="List of artists to filter by.")
    publishers: Optional[List[str]] = Field(None, description="List of publishers to filter by.")
    exact_players: Optional[int] = Field(None, description="Exact number of players supported.")
    min_players: Optional[int] = Field(None, description="Minimum number of players supported.")
    max_players: Optional[int] = Field(None, description="Maximum number of players supported.")
    min_weight: Optional[float] = Field(None, description="Minimum complexity weight (1.0 to 5.0).")
    max_weight: Optional[float] = Field(None, description="Maximum complexity weight (1.0 to 5.0).")
    min_playtime: Optional[int] = Field(None, description="Minimum manufacturer-stated playtime in minutes.")
    max_playtime: Optional[int] = Field(None, description="Maximum manufacturer-stated playtime in minutes.")
    min_year: Optional[int] = Field(None, description="Minimum year published.")
    max_year: Optional[int] = Field(None, description="Maximum year published.")
