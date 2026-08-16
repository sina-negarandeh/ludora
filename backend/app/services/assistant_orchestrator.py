from sqlalchemy.orm import Session
from app.schemas.assistant import ParsedIntent, AssistantResponse
from app.schemas.game_query import GameFilter
from app.schemas.search import SearchQuery, SearchMode
from app.schemas.game import GameResponse
from app.services.game_service import GameService
from app.services.search_service import SearchService
from app.services.recommendation_service import RecommendationService
from app.services.entity_resolver import EntityResolver, AmbiguousEntityError, EntityNotFoundError

class AssistantOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.game_service = GameService(db)
        self.search_service = SearchService(db)
        self.rec_service = RecommendationService(db)
        self.resolver = EntityResolver(db)

    def execute(self, intent: ParsedIntent) -> AssistantResponse:
        # If LLM already knows it needs clarification
        if intent.needs_clarification:
            return AssistantResponse(
                message=intent.clarification_question or "Could you clarify your request?",
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        try:
            if intent.intent == "browse":
                return self._handle_browse(intent)
            elif intent.intent == "search":
                return self._handle_search(intent)
            elif intent.intent == "compare":
                return self._handle_compare(intent)
            elif intent.intent == "recommend":
                return self._handle_recommend(intent)
            elif intent.intent == "get_game":
                return self._handle_get_game(intent)
            elif intent.intent in ["get_reviews", "get_aspects"]:
                # Not fully implemented in services yet, but we map it
                return self._handle_get_game(intent) # fallback for now
            else:
                return AssistantResponse(
                    message="I'm not sure how to handle that intent.",
                    type="error",
                    parsed_intent=intent,
                    data={}
                )

        except AmbiguousEntityError as e:
            # We intercept ambiguity and morph it into a clarification response!
            intent.needs_clarification = True
            intent.clarification_question = f"Did you mean one of these for '{e.query}'?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={"ambiguous_matches": e.matches}
            )
        except EntityNotFoundError as e:
            intent.needs_clarification = True
            intent.clarification_question = f"I couldn't find any game matching '{e.query}'. Could you check the spelling?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="error",
                parsed_intent=intent,
                data={}
            )
            
    def _map_filters(self, assistant_filters) -> GameFilter:
        if not assistant_filters:
            return GameFilter()
        
        base_filters = GameFilter(
            categories=assistant_filters.categories,
            themes=assistant_filters.themes,
            mechanics=assistant_filters.mechanics,
            exact_players=assistant_filters.exact_players,
            min_players=assistant_filters.min_players,
            max_players=assistant_filters.max_players,
            min_weight=assistant_filters.min_complexity,
            max_weight=assistant_filters.max_complexity,
            min_year=assistant_filters.min_year,
            max_year=assistant_filters.max_year
        )
        
        return self.resolver.resolve_filters(base_filters)

    def _handle_browse(self, intent: ParsedIntent) -> AssistantResponse:
        db_filters = self._map_filters(intent.filters)
        
        sort_by = intent.sort.field if intent.sort else "rank"
        order = intent.sort.direction if intent.sort else "asc"
        limit = intent.limit or 20

        total, games = self.game_service.get_games(
            skip=0,
            limit=limit,
            sort_by=sort_by,
            order=order,
            categories=db_filters.categories,
            themes=db_filters.themes,
            mechanics=db_filters.mechanics,
            exact_players=db_filters.exact_players,
            min_players=db_filters.min_players,
            max_players=db_filters.max_players,
            min_weight=db_filters.min_weight,
            max_weight=db_filters.max_weight,
            min_year=db_filters.min_year,
            max_year=db_filters.max_year
        )
        
        return AssistantResponse(
            message=f"I found {total} games matching your preferences.",
            type="search_results",
            parsed_intent=intent,
            data={"total": total, "games": [GameResponse.model_validate(g).model_dump() for g in games]}
        )

    def _handle_search(self, intent: ParsedIntent) -> AssistantResponse:
        db_filters = self._map_filters(intent.filters)
        
        mode = SearchMode.HYBRID
        if intent.search_mode == "lexical":
            mode = SearchMode.LEXICAL
        elif intent.search_mode == "semantic":
            mode = SearchMode.SEMANTIC
            
        sq = SearchQuery(q=intent.query or "", mode=mode, filters=db_filters)
        results = self.search_service.search(sq, skip=0, limit=intent.limit or 20)
        
        # Serialize the paginated search results
        return AssistantResponse(
            message=f"I found {results.total} games matching '{intent.query}'.",
            type="search_results",
            parsed_intent=intent,
            data={"total": results.total, "results": [{"game": GameResponse.model_validate(item.game).model_dump(), "score": item.score} for item in results.items]}
        )

    def _handle_compare(self, intent: ParsedIntent) -> AssistantResponse:
        if not intent.game_names or len(intent.game_names) < 2:
            intent.needs_clarification = True
            intent.clarification_question = "Which games do you want to compare? Please provide at least two."
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        # Resolve all strings to IDs
        bgg_ids = self.resolver.resolve_games(intent.game_names)
        
        games = self.game_service.compare_games(bgg_ids)
        return AssistantResponse(
            message=f"Here is a comparison of the {len(games)} games you asked for.",
            type="comparison",
            parsed_intent=intent,
            data={"games": [GameResponse.model_validate(g).model_dump() for g in games]}
        )

    def _handle_recommend(self, intent: ParsedIntent) -> AssistantResponse:
        if not intent.game_name:
            intent.needs_clarification = True
            intent.clarification_question = "Which game do you want recommendations for?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        bgg_id = self.resolver.resolve_game(intent.game_name)
        
        # Default to hybrid if not specified
        model_name = intent.recommendation_model or "hybrid"
        
        source_game, recs = self.rec_service.get_recommendations(game_id=bgg_id, model=model_name, limit=intent.limit or 10)
        
        return AssistantResponse(
            message=f"Here are {len(recs)} games similar to {source_game.name}." if source_game else "I couldn't find recommendations.",
            type="recommendations",
            parsed_intent=intent,
            data={
                "source_game": GameResponse.model_validate(source_game).model_dump() if source_game else None,
                "recommendations": [{"game": GameResponse.model_validate(r["game"]).model_dump(), "score": r["score"], "reason": r["reason"]} for r in recs]
            }
        )

    def _handle_get_game(self, intent: ParsedIntent) -> AssistantResponse:
        if not intent.game_name:
            intent.needs_clarification = True
            intent.clarification_question = "Which game are you looking for?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        bgg_id = self.resolver.resolve_game(intent.game_name)
        game = self.game_service.get_game(bgg_id)
        
        return AssistantResponse(
            message=f"Here is the information for {game.name}." if game else "I couldn't find that game.",
            type="game_detail",
            parsed_intent=intent,
            data={"game": GameResponse.model_validate(game).model_dump() if game else None}
        )
