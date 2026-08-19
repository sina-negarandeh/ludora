from sqlalchemy.orm import Session
from app.schemas.assistant import ParsedIntent, AssistantResponse
from app.schemas.game_query import GameFilter
from app.schemas.search import SearchQuery, SearchMode
from app.schemas.game import GameResponse
from app.core.ml_config import ABSAConfig
from app.services.game_service import GameService
from app.services.search_service import SearchService
from app.services.recommendation_service import RecommendationService
from app.services.aspect_service import AspectService, AspectAggregateResponse
from app.services.review_service import ReviewService
from app.services.entity_resolver import EntityResolver, AmbiguousEntityError, EntityNotFoundError

class AssistantOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.game_service = GameService(db)
        self.search_service = SearchService(db)
        self.rec_service = RecommendationService(db)
        self.aspect_service = AspectService(db)
        self.review_service = ReviewService(db)
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
            elif intent.intent == "recommend":
                return self._handle_recommend(intent)
            elif intent.intent == "get_game":
                return self._handle_get_game(intent)
            elif intent.intent == "get_aspects":
                return self._handle_get_aspects(intent)
            elif intent.intent == "get_reviews":
                return self._handle_get_reviews(intent)
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
            subdomains=assistant_filters.subdomains,
            themes=assistant_filters.themes,
            families=assistant_filters.families,
            mechanics=assistant_filters.mechanics,
            designers=assistant_filters.designers,
            artists=assistant_filters.artists,
            publishers=assistant_filters.publishers,
            exact_players=assistant_filters.exact_players,
            min_players=assistant_filters.min_players,
            max_players=assistant_filters.max_players,
            min_weight=assistant_filters.min_complexity,
            max_weight=assistant_filters.max_complexity,
            min_year=assistant_filters.min_year,
            max_year=assistant_filters.max_year
        )
        
        return self.resolver.resolve_filters(base_filters)

    def _synthesize_query_from_filters(self, filters) -> str:
        """Join every tag value the LLM tried to filter on into one string,
        for the text-search fallback below -- used when none of them
        resolved against the fixed taxonomy, so there's nothing structured
        left to filter on, but the underlying request (e.g. "marvel games
        with spiderman") is still perfectly answerable as free text.
        """
        if not filters:
            return ""
        parts = []
        for field in ("themes", "categories", "subdomains", "mechanics", "families", "designers", "artists", "publishers"):
            values = getattr(filters, field, None)
            if values:
                parts.extend(values)
        return " ".join(parts)

    def _handle_browse(self, intent: ParsedIntent) -> AssistantResponse:
        try:
            db_filters = self._map_filters(intent.filters)
        except EntityNotFoundError:
            # The LLM guessed a tag value that isn't real (a franchise,
            # character, or brand name like "Spiderman" rather than an
            # actual BGG category/theme/mechanic) -- the fixed taxonomy
            # can't express that, but a text search over game names/
            # descriptions still can. Degrading to search beats hard-failing
            # a request that's clearly still answerable.
            query = intent.query or self._synthesize_query_from_filters(intent.filters)
            if not query:
                raise
            results = self.search_service.search(SearchQuery(q=query, mode=SearchMode.HYBRID), skip=0, limit=intent.limit or 20)
            message = (
                f"I couldn't match that to our exact category list, so here's a text search for '{query}' instead."
                if results.total else f"I couldn't find anything matching '{query}'."
            )
            return AssistantResponse(
                message=message,
                type="search_results",
                parsed_intent=intent,
                data={"total": results.total, "results": [{"game": GameResponse.model_validate(item.game).model_dump(), "score": item.score} for item in results.items]}
            )

        sort_by = intent.sort.field if intent.sort else "rank"
        order = intent.sort.direction if intent.sort else "asc"
        limit = intent.limit or 20

        total, games = self.game_service.get_games(
            skip=0,
            limit=limit,
            sort_by=sort_by,
            order=order,
            categories=db_filters.categories,
            subdomains=db_filters.subdomains,
            themes=db_filters.themes,
            families=db_filters.families,
            mechanics=db_filters.mechanics,
            designers=db_filters.designers,
            artists=db_filters.artists,
            publishers=db_filters.publishers,
            exact_players=db_filters.exact_players,
            min_players=db_filters.min_players,
            max_players=db_filters.max_players,
            min_weight=db_filters.min_weight,
            max_weight=db_filters.max_weight,
            min_year=db_filters.min_year,
            max_year=db_filters.max_year
        )

        # total is the full filtered-match count, independent of `limit` --
        # for a "find the game ranked #1" style request (sort + limit=1, no
        # real filter), total is the whole catalog and "I found 28208 games
        # matching your preferences" is a nonsensical answer to what's
        # really a single-answer question. Word the message around what was
        # actually returned instead of the raw total whenever they diverge.
        if not games:
            message = "I couldn't find any games matching your preferences."
        elif limit == 1:
            message = f"The top match is {games[0].name}."
        elif total > len(games):
            message = f"I found {total} games matching your preferences -- here are the top {len(games)}."
        else:
            message = f"I found {total} games matching your preferences."

        return AssistantResponse(
            message=message,
            type="search_results",
            parsed_intent=intent,
            data={"total": total, "games": [GameResponse.model_validate(g).model_dump() for g in games]}
        )

    def _handle_search(self, intent: ParsedIntent) -> AssistantResponse:
        try:
            db_filters = self._map_filters(intent.filters)
        except EntityNotFoundError:
            # Unlike browse, search already has real free text to fall back
            # on -- just drop the filter tag(s) that don't exist in the
            # taxonomy rather than failing the whole request.
            db_filters = GameFilter()

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

        if not game:
            message = "I couldn't find that game."
        elif intent.requested_facts:
            message = self._build_fact_message(game, intent.requested_facts)
        else:
            message = f"Here is the information for {game.name}."

        return AssistantResponse(
            message=message,
            type="game_detail",
            parsed_intent=intent,
            data={"game": GameResponse.model_validate(game).model_dump() if game else None}
        )

    def _build_fact_message(self, game, facts: list) -> str:
        """A direct, pointed answer for one or more specific official facts
        about `game` -- ParsedIntent.requested_facts -- instead of the
        generic "here's the record" message. Deliberately sources the same
        "Official" fields the game detail page's Official stat cards use
        (mfg_playtime, min_age, min_players/max_players, game_weight,
        rank/subdomain_ranks, avg_rating), not the Community percentile/poll
        stats shown alongside them, which have no single value to state.
        """
        parts = []
        for fact in facts:
            if fact == "rank":
                if game.rank:
                    rank_str = f"#{game.rank} overall"
                    if game.subdomain_ranks:
                        rank_str += " (" + ", ".join(f"#{r} in {name}" for name, r in game.subdomain_ranks.items()) + ")"
                    parts.append(f"ranks {rank_str}")
                else:
                    parts.append("is unranked")
            elif fact == "rating":
                if game.avg_rating is not None:
                    parts.append(f"has an average rating of {game.avg_rating:.1f}/10")
                else:
                    parts.append("has no rating yet")
            elif fact == "complexity":
                if game.game_weight is not None:
                    parts.append(f"has a complexity of {game.game_weight:.2f}/5")
                else:
                    parts.append("has no complexity rating yet")
            elif fact == "player_count":
                if game.min_players and game.max_players:
                    if game.min_players == game.max_players:
                        parts.append(f"supports exactly {game.min_players} players")
                    else:
                        parts.append(f"supports {game.min_players}-{game.max_players} players")
                else:
                    parts.append("has no listed player count")
            elif fact == "age":
                if game.min_age:
                    parts.append(f"is recommended for ages {game.min_age}+")
                else:
                    parts.append("has no listed minimum age")
            elif fact == "playtime":
                if game.mfg_playtime:
                    parts.append(f"takes about {game.mfg_playtime} minutes to play")
                else:
                    parts.append("has no listed playtime")

        if not parts:
            return f"I don't have that information for {game.name}."
        return f"{game.name} " + "; ".join(parts) + "."

    def _handle_get_aspects(self, intent: ParsedIntent) -> AssistantResponse:
        """"What do people think of X" -- the community consensus paragraph
        plus the per-aspect sentiment breakdown, bundled together since
        they're complementary views of the same review corpus (one holistic
        summary, one structured breakdown by topic). Distinct from
        get_reviews, which returns actual written review text.
        """
        if not intent.game_name:
            intent.needs_clarification = True
            intent.clarification_question = "Which game's reviews do you want opinions on?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        bgg_id = self.resolver.resolve_game(intent.game_name)
        game = self.game_service.get_game(bgg_id)
        if not game:
            return AssistantResponse(message="I couldn't find that game.", type="error", parsed_intent=intent, data={})

        aspects = self.aspect_service.get_game_aspects(bgg_id)

        if not game.customer_summary and not aspects:
            return AssistantResponse(
                message=f"There aren't enough reviews yet to summarize opinions on {game.name}.",
                type="community_consensus",
                parsed_intent=intent,
                data={"game": GameResponse.model_validate(game).model_dump(), "summary": None, "aspects": []}
            )

        message_parts = []
        if game.customer_summary:
            message_parts.append(game.customer_summary)
        if aspects:
            message_parts.append("By aspect: " + ", ".join(self._describe_aspect(a) for a in aspects[:5]) + ".")

        return AssistantResponse(
            message=" ".join(message_parts),
            type="community_consensus",
            parsed_intent=intent,
            data={
                "game": GameResponse.model_validate(game).model_dump(),
                "summary": game.customer_summary,
                "aspects": [a.model_dump() for a in aspects]
            }
        )

    def _describe_aspect(self, a: AspectAggregateResponse) -> str:
        # Same Positive/Negative/Mixed dominance rule as the aspect cards
        # (AspectService.get_game_aspects, GameDetail.tsx) -- reusing
        # ABSAConfig.CARD_DOMINANCE_THRESHOLD instead of a new threshold
        # keeps this consistent with what the game page itself shows.
        total = max(1, a.total_mentions)
        pos_ratio = a.positive_count / total
        neg_ratio = a.negative_count / total
        if pos_ratio >= ABSAConfig.CARD_DOMINANCE_THRESHOLD:
            return f"{a.aspect} ({round(pos_ratio * 100)}% positive)"
        elif neg_ratio >= ABSAConfig.CARD_DOMINANCE_THRESHOLD:
            return f"{a.aspect} ({round(neg_ratio * 100)}% negative)"
        else:
            return f"{a.aspect} (mixed opinions)"

    def _handle_get_reviews(self, intent: ParsedIntent) -> AssistantResponse:
        """Actual written review text -- distinct from get_aspects, which
        answers a general opinion question with a summary/breakdown
        instead of verbatim reviews.
        """
        if not intent.game_name:
            intent.needs_clarification = True
            intent.clarification_question = "Which game's reviews do you want to see?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        bgg_id = self.resolver.resolve_game(intent.game_name)
        game = self.game_service.get_game(bgg_id)
        if not game:
            return AssistantResponse(message="I couldn't find that game.", type="error", parsed_intent=intent, data={})

        total, reviews = self.review_service.get_game_reviews(bgg_id, page=1, page_size=intent.limit or 5)

        message = f"Here are some reviews for {game.name}." if reviews else f"There aren't any written reviews for {game.name} yet."

        return AssistantResponse(
            message=message,
            type="reviews",
            parsed_intent=intent,
            data={"game": GameResponse.model_validate(game).model_dump(), "total": total, "reviews": reviews}
        )
