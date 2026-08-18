from pydantic import BaseModel, Field
from typing import Optional, List

class GameFilter(BaseModel):
    subdomains: Optional[List[str]] = Field(None, description="List of subdomains to filter by (BGG's rank/leaderboard classification, e.g. 'Strategy', 'Family').")
    categories: Optional[List[str]] = Field(None, description="List of categories to filter by.")
    themes: Optional[List[str]] = Field(None, description="List of themes to filter by.")
    families: Optional[List[str]] = Field(None, description="List of family tags to filter by (full 'Group: Value' form, e.g. 'Animals: Bears').")
    mechanics: Optional[List[str]] = Field(None, description="List of mechanics to filter by.")
    exact_players: Optional[int] = Field(None, description="Exact number of players supported.")
    min_players: Optional[int] = Field(None, description="Minimum number of players supported.")
    max_players: Optional[int] = Field(None, description="Maximum number of players supported.")
    min_weight: Optional[float] = Field(None, description="Minimum complexity weight (1.0 to 5.0).")
    max_weight: Optional[float] = Field(None, description="Maximum complexity weight (1.0 to 5.0).")
    min_playtime: Optional[int] = Field(None, description="Minimum manufacturer-stated playtime in minutes.")
    max_playtime: Optional[int] = Field(None, description="Maximum manufacturer-stated playtime in minutes.")
    min_year: Optional[int] = Field(None, description="Minimum year published.")
    max_year: Optional[int] = Field(None, description="Maximum year published.")
