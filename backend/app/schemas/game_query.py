from pydantic import BaseModel
from typing import Optional, List

class GameFilter(BaseModel):
    categories: Optional[List[str]] = None
    themes: Optional[List[str]] = None
    mechanics: Optional[List[str]] = None
    exact_players: Optional[int] = None
    min_players: Optional[int] = None
    max_players: Optional[int] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
