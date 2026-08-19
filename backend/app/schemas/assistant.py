from pydantic import BaseModel, Field
from typing import List, Literal, Optional

IntentEnum = Literal[
    "browse",
    "search",
    "recommend",
    "compare",
    "get_game",
    "get_reviews",
    "get_aspects"
]

SearchMode = Literal["lexical", "semantic", "hybrid"]
RecommendationFamily = Literal["popularity", "content", "collaborative", "hybrid"]
SortDirection = Literal["asc", "desc"]
SortField = Literal["rank", "rating", "year_published", "complexity", "name"]
# Official (manufacturer-stated / BGG-computed single-value) facts about one
# game -- deliberately not the "Community" percentile/poll stats shown
# alongside these on the game detail page (e.g. suggested_num_players,
# "better than X% of Strategy Games"), which have no single answer to state.
GameFactEnum = Literal["rank", "rating", "complexity", "player_count", "age", "playtime"]

class SortSpec(BaseModel):
    field: SortField
    direction: SortDirection

class GameFilters(BaseModel):
    themes: Optional[List[str]] = Field(default=None, description="Narrow setting/franchise tags, e.g. 'Zombies', 'Cthulhu Mythos', 'Science Fiction'.")
    mechanics: Optional[List[str]] = Field(default=None, description="Gameplay mechanisms, e.g. 'Worker Placement', 'Deck Building', 'Area Control'.")
    categories: Optional[List[str]] = Field(default=None, description="Broad subject/format classification, e.g. 'Card Game', 'Wargame', 'Fantasy'.")
    subdomains: Optional[List[str]] = Field(default=None, description="BGG's 8 coarse rank/leaderboard types, exactly: Abstract, CGS, Childrens, Family, Party, Strategy, Thematic, War.")
    families: Optional[List[str]] = Field(default=None, description="Specific named series/groupings, e.g. 'Bears', 'Kickstarter' -- looser and much larger than categories/themes, only use when the user names one explicitly.")
    designers: Optional[List[str]] = Field(default=None, description="Specific game designer names, e.g. 'Uwe Rosenberg', 'Martin Wallace'. Only set when the user names a person explicitly.")
    artists: Optional[List[str]] = Field(default=None, description="Specific illustrator/artist names. Only set when the user names a person explicitly.")
    publishers: Optional[List[str]] = Field(default=None, description="Specific publisher/company names, e.g. 'Days of Wonder', 'Fantasy Flight Games'. Only set when the user names a company explicitly.")
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
    game_names: Optional[List[str]] = Field(default=None, description="Two or more game names, ONLY for 'compare' -- e.g. 'compare Catan and Terraforming Mars' -> game_names=['Catan', 'Terraforming Mars'].")

    requested_facts: Optional[List[GameFactEnum]] = Field(default=None, description="Only set when intent is 'get_game' AND the user asked about one or more specific official facts (e.g. 'how heavy is X', 'what rank is X') rather than general info. Leave unset for a general 'tell me about X' request -- it changes the response message from a full summary to a direct, pointed answer.")

    search_mode: Optional[SearchMode] = Field(default=None, description="The search mode to use if intent is search.")
    
    filters: Optional[GameFilters] = Field(default=None, description="Filters to apply to the query.")
    
    sort: Optional[SortSpec] = Field(default=None, description="Sorting instructions.")
    
    recommendation_family: Optional[RecommendationFamily] = Field(default=None, description="The family of recommendation algorithm to use.")
    recommendation_model: Optional[str] = Field(default=None, description="Specific recommendation model name if requested (e.g. 'cf_als', 'embedding').")
    limit: Optional[int] = Field(default=None, description="The number of results requested.")

class AssistantResponse(BaseModel):
    message: str = Field(description="Deterministic natural language message for the user.")
    type: str = Field(description="The UI presentation type: search_results, recommendations, clarification, game_detail, community_consensus, reviews, comparison, error")
    parsed_intent: ParsedIntent
    data: Optional[dict] = Field(default=None, description="The resulting data from the executed intent.")
