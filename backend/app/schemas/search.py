from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from app.schemas.game_query import GameFilter
from app.schemas.game import GameResponse

class SearchMode(str, Enum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"

class SearchQuery(BaseModel):
    q: str = Field(..., description="The search string provided by the user.")
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="The search mode to execute: 'lexical', 'semantic', or 'hybrid'.")
    filters: Optional[GameFilter] = Field(default=None, description="Optional filters (categories, themes, players) to restrict the search space.")

class SearchDebug(BaseModel):
    lexical_rank: Optional[int] = Field(None, description="The rank of this item in the lexical TF-IDF results.")
    semantic_rank: Optional[int] = Field(None, description="The rank of this item in the semantic embedding results.")
    rrf_score: float = Field(..., description="The combined Reciprocal Rank Fusion score.")

class SearchResult(BaseModel):
    game: GameResponse = Field(..., description="The retrieved game metadata.")
    score: float = Field(..., description="The final relevance score.")
    debug: SearchDebug = Field(..., description="Debugging metadata explaining the rank fusion.")

class PaginatedSearchResults(BaseModel):
    total: int = Field(..., description="Total number of matched results.")
    items: list[SearchResult] = Field(..., description="The paginated list of search results.")
