from pydantic import BaseModel, Field
from typing import List, Literal, Optional

IntentEnum = Literal[
    "browse",
    "search",
    "compare",
    "recommend",
    "get_game",
    "get_reviews",
    "get_aspects"
]

SearchMode = Literal["lexical", "semantic", "hybrid"]
RecommendationFamily = Literal["content", "collaborative", "hybrid"]
SortDirection = Literal["asc", "desc"]
SortField = Literal["rank", "rating", "year_published", "complexity", "name"]

class SortSpec(BaseModel):
    field: SortField
    direction: SortDirection

class GameFilters(BaseModel):
    themes: Optional[List[str]] = Field(default=None, description="Game themes like 'Economic', 'Trains', 'Science Fiction'.")
    mechanics: Optional[List[str]] = Field(default=None, description="Game mechanics like 'Worker Placement', 'Deck Building'.")
    categories: Optional[List[str]] = Field(default=None, description="Game categories like 'Card Game', 'Miniatures'.")
    min_players: Optional[int] = Field(default=None, description="Minimum player count.")
    max_players: Optional[int] = Field(default=None, description="Maximum player count.")
    exact_players: Optional[int] = Field(default=None, description="Exact player count if specifically requested.")
    min_complexity: Optional[float] = Field(default=None, description="Minimum weight/complexity (1.0 to 5.0).")
    max_complexity: Optional[float] = Field(default=None, description="Maximum weight/complexity (1.0 to 5.0).")
    min_year: Optional[int] = Field(default=None, description="Published after this year.")
    max_year: Optional[int] = Field(default=None, description="Published before this year.")

class ParsedIntent(BaseModel):
    intent: IntentEnum = Field(description="The primary intent of the user.")
    
    needs_clarification: bool = Field(default=False, description="Set to true if the user's request is too ambiguous or missing required context.")
    clarification_question: Optional[str] = Field(default=None, description="If needs_clarification is true, the question to ask the user.")
    
    query: Optional[str] = Field(default=None, description="The natural language query string, primarily used for 'search' intent.")
    
    game_name: Optional[str] = Field(default=None, description="A specific game name mentioned by the user (e.g. for get_game, recommend).")
    game_names: Optional[List[str]] = Field(default=None, description="A list of game names (e.g. for compare).")
    
    search_mode: Optional[SearchMode] = Field(default=None, description="The search mode to use if intent is search.")
    
    filters: Optional[GameFilters] = Field(default=None, description="Filters to apply to the query.")
    
    sort: Optional[SortSpec] = Field(default=None, description="Sorting instructions.")
    
    recommendation_family: Optional[RecommendationFamily] = Field(default=None, description="The family of recommendation algorithm to use.")
    recommendation_model: Optional[str] = Field(default=None, description="Specific recommendation model name if requested (e.g. 'cf_als', 'embedding').")
    limit: Optional[int] = Field(default=None, description="The number of results requested.")

class AssistantResponse(BaseModel):
    message: str = Field(description="Deterministic natural language message for the user.")
    type: str = Field(description="The UI presentation type: search_results, recommendations, comparison, clarification, game_detail, error")
    parsed_intent: ParsedIntent
    data: Optional[dict] = Field(default=None, description="The resulting data from the executed intent.")
