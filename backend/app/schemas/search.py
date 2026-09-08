from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.core.query_text import normalize_query
from app.schemas.game import GameResponse
from app.schemas.game_query import GameFilter, SortSpec


class SearchMode(str, Enum):
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"

class SearchQuery(BaseModel):
    # Normalized on the way in rather than by each retrieval leg. Every
    # caller builds one of these -- the route, the assistant, the entity
    # resolver, the evaluation harness -- so folding here covers all of them
    # by construction instead of by each one remembering. It also puts the
    # guarantee in the OpenAPI contract. Folds to "" for blank input; see
    # `SearchService.search`, which treats that as "no query".
    q: Annotated[str, AfterValidator(normalize_query)] = Field(
        ..., description="The search string provided by the user. Whitespace-collapsed and case-folded before retrieval."
    )
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="The search mode to execute: 'lexical', 'semantic', or 'hybrid'.")
    filters: GameFilter | None = Field(default=None, description="Optional filters (categories, themes, players) to restrict the search space.")
    sort: SortSpec | None = Field(default=None, description="Optional override for result ordering. Unset (default) ranks by fused relevance (RRF) score, matching text-match quality. When set, results are ordered by this field/direction instead -- relevance still determines which candidates are considered, sort only reorders among them.")

class SearchDebug(BaseModel):
    lexical_rank: int | None = Field(None, description="The rank of this item in the lexical TF-IDF results.")
    semantic_rank: int | None = Field(None, description="The rank of this item in the semantic embedding results.")
    rrf_score: float = Field(..., description="The combined Reciprocal Rank Fusion score.")

class SearchResult(BaseModel):
    game: GameResponse = Field(..., description="The retrieved game metadata.")
    score: float = Field(..., description="The final relevance score.")
    debug: SearchDebug = Field(..., description="Debugging metadata explaining the rank fusion.")

class PaginatedSearchResults(BaseModel):
    total: int = Field(..., description="Total number of matched results.")
    items: list[SearchResult] = Field(..., description="The paginated list of search results.")
