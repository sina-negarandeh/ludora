from pydantic import BaseModel
from typing import Literal, Optional
from enum import Enum
from app.schemas.game_query import GameFilter
from app.schemas.game import GameResponse

class SearchMode(str, Enum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"

class SearchQuery(BaseModel):
    q: str
    mode: SearchMode = SearchMode.HYBRID
    filters: Optional[GameFilter] = None

class SearchDebug(BaseModel):
    lexical_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    rrf_score: float

class SearchResult(BaseModel):
    game: GameResponse
    score: float
    debug: SearchDebug

class PaginatedSearchResults(BaseModel):
    total: int
    items: list[SearchResult]
