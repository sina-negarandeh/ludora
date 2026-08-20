from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.game_query import SortSpec

IntentEnum = Literal[
    "browse",
    "search",
    "recommend",
    "compare",
    "get_game",
    "get_reviews",
    "get_aspects",
    "unsupported"
]

SearchMode = Literal["lexical", "semantic", "hybrid"]
RecommendationFamily = Literal["popularity", "content", "collaborative", "hybrid"]
# Official (manufacturer-stated / BGG-computed single-value) facts about one
# game -- deliberately not the "Community" percentile/poll stats shown
# alongside these on the game detail page (e.g. suggested_num_players,
# "better than X% of Strategy Games"), which have no single answer to state.
GameFactEnum = Literal["rank", "rating", "complexity", "player_count", "age", "playtime"]

class GameFilters(BaseModel):
    themes: list[str] | None = Field(default=None, description="Narrow setting/franchise tags, e.g. 'Zombies', 'Cthulhu Mythos', 'Science Fiction'.")
    mechanics: list[str] | None = Field(default=None, description="Gameplay mechanisms, e.g. 'Worker Placement', 'Deck Building', 'Area Control'.")
    categories: list[str] | None = Field(default=None, description="Broad subject/format classification, e.g. 'Card Game', 'Wargame', 'Fantasy'.")
    subdomains: list[str] | None = Field(default=None, description="BGG's 8 coarse rank/leaderboard types, exactly: Abstract, CGS, Childrens, Family, Party, Strategy, Thematic, War.")
    families: list[str] | None = Field(default=None, description="Specific named series/groupings, e.g. 'Bears', 'Kickstarter' -- looser and much larger than categories/themes, only use when the user names one explicitly.")
    designers: list[str] | None = Field(default=None, description="Specific game designer names, e.g. 'Uwe Rosenberg', 'Martin Wallace'. Only set when the user names a person explicitly.")
    artists: list[str] | None = Field(default=None, description="Specific illustrator/artist names. Only set when the user names a person explicitly.")
    publishers: list[str] | None = Field(default=None, description="Specific publisher/company names, e.g. 'Days of Wonder', 'Fantasy Flight Games'. Only set when the user names a company explicitly.")
    min_players: int | None = Field(default=None, description="Minimum player count.")
    max_players: int | None = Field(default=None, description="Maximum player count.")
    exact_players: int | None = Field(default=None, description="Exact player count if specifically requested.")
    min_complexity: float | None = Field(default=None, description="Minimum weight/complexity (1.0 to 5.0).")
    max_complexity: float | None = Field(default=None, description="Maximum weight/complexity (1.0 to 5.0).")
    min_year: int | None = Field(default=None, description="Published after this year.")
    max_year: int | None = Field(default=None, description="Published before this year.")
    min_playtime: int | None = Field(default=None, description="Minimum manufacturer-stated playtime in minutes.")
    max_playtime: int | None = Field(default=None, description="Maximum manufacturer-stated playtime in minutes.")

class ParsedIntent(BaseModel):
    intent: IntentEnum = Field(description="The primary intent of the user.")
    
    needs_clarification: bool = Field(default=False, description="Set to true if the user's request is too ambiguous or missing required context.")
    clarification_question: str | None = Field(default=None, description="If needs_clarification is true, the question to ask the user.")
    
    query: str | None = Field(default=None, description="The natural language query string, primarily used for 'search' intent.")
    
    game_name: str | None = Field(default=None, description="A specific game name mentioned by the user (e.g. for get_game, recommend).")
    game_names: list[str] | None = Field(default=None, description="Two or more game names, ONLY for 'compare' -- e.g. 'compare Catan and Terraforming Mars' -> game_names=['Catan', 'Terraforming Mars'].")

    requested_facts: list[GameFactEnum] | None = Field(default=None, description="Only set when intent is 'get_game' AND the user asked about one or more specific official facts (e.g. 'how heavy is X', 'what rank is X') rather than general info. Leave unset for a general 'tell me about X' request -- it changes the response message from a full summary to a direct, pointed answer.")

    search_mode: SearchMode | None = Field(default=None, description="The search mode to use if intent is search.")
    
    filters: GameFilters | None = Field(default=None, description="Filters to apply to the query.")
    
    sort: SortSpec | None = Field(default=None, description="Sorting instructions.")
    
    recommendation_family: RecommendationFamily | None = Field(default=None, description="The family of recommendation algorithm to use.")
    recommendation_model: str | None = Field(default=None, description="Specific recommendation model name if requested (e.g. 'cf_als', 'embedding').")
    limit: int | None = Field(default=None, description="The number of results requested.")

    # Multi-step plan fields. Unused (defaults only) for the overwhelming
    # majority of requests, which are a single independent intent -- see
    # ParsedPlan below. Kept on ParsedIntent itself, not a separate
    # subclass, so a bare single-step ParsedIntent (e.g. from the /parse
    # debug endpoint) is still exactly today's shape with two inert extra
    # fields, not a breaking change.
    step_id: int = Field(default=0, description="0-based position of this step within its plan, in execution order. Always 0 for a single-step plan.")
    depends_on_step: int | None = Field(default=None, description="The step_id of an earlier step this one needs completed first, or null if independent. Only set when this step's game_name/game_names references that earlier step's result via a '$stepN' placeholder (see ParsedPlan).")

class ParsedPlan(BaseModel):
    steps: list[ParsedIntent] = Field(description="One or more steps to execute in order. Most requests need exactly one step -- only decompose into more when a later step genuinely cannot be filled in without an earlier step's result.")

class AssistantResponse(BaseModel):
    message: str = Field(description="Deterministic natural language message for the user.")
    type: str = Field(description="The UI presentation type: search_results, recommendations, clarification, game_detail, community_consensus, reviews, comparison, unsupported, error")
    parsed_intent: ParsedIntent
    data: dict | None = Field(default=None, description="The resulting data from the executed intent.")
