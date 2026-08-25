
from sqlalchemy.orm import Session

from app.core.ml_config import ABSAConfig
from app.schemas.assistant import AssistantResponse, ParsedIntent, ParsedPlan
from app.schemas.game import GameResponse
from app.schemas.game_query import GameFilter
from app.schemas.search import SearchMode, SearchQuery
from app.services.aspect_service import AspectAggregateResponse, AspectService
from app.services.entity_resolver import AmbiguousEntityError, EntityNotFoundError, EntityResolver
from app.services.game_service import GameService
from app.services.plan_executor import run_plan
from app.services.plan_graph import PlanValidationError, compile_plan
from app.services.plan_resolution import MAX_COMPARE_GAMES, extract_chainable_values
from app.services.recommendation_service import RecommendationService
from app.services.review_service import ReviewService
from app.services.search_service import SearchService


class AssistantOrchestrator:

    def __init__(self, db: Session):
        self.db = db
        self.game_service = GameService(db)
        self.search_service = SearchService(db)
        self.rec_service = RecommendationService(db)
        self.aspect_service = AspectService(db)
        self.review_service = ReviewService(db)
        self.resolver = EntityResolver(db)

    def execute(self, intent: ParsedIntent, known_bgg_ids: dict[str, int] | None = None) -> AssistantResponse:
        """Runs one already-resolved intent.

        `known_bgg_ids` carries names a plan step already resolved to an
        exact id, so a title lifted straight off an earlier step's result
        skips the fuzzy EntityResolver -- which can spuriously raise
        AmbiguousEntityError on an exact title (measured: "Witch Hunt").
        Passed in rather than held as instance state: it belongs to one
        plan execution, and the walk that owns that execution keeps it.
        """
        known = known_bgg_ids or {}

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
                return self._handle_browse(intent, known)
            elif intent.intent == "search":
                return self._handle_search(intent, known)
            elif intent.intent == "recommend":
                return self._handle_recommend(intent, known)
            elif intent.intent == "compare":
                return self._handle_compare(intent, known)
            elif intent.intent == "get_game":
                return self._handle_get_game(intent, known)
            elif intent.intent == "get_aspects":
                return self._handle_get_aspects(intent, known)
            elif intent.intent == "get_reviews":
                return self._handle_get_reviews(intent, known)
            elif intent.intent == "unsupported":
                return self._handle_unsupported(intent, known)
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

    def execute_plan(self, plan: ParsedPlan) -> AssistantResponse:
        """Runs a ParsedPlan's steps in order, substituting any earlier
        step's resolved game(s) into a later step's placeholder(s) before
        running it. The overwhelming majority of plans are one step, in
        which case this is identical to calling execute() directly.

        The plan is compiled into a validated PlanGraph before anything
        runs (see plan_graph.compile_plan) -- every "$stepN" reference is
        checked to point at an earlier, existing step up front, so the
        walk never has to handle an out-of-range or forward reference
        itself; if compile_plan doesn't raise, every dependency lookup
        during execution is guaranteed safe.

        The walk itself lives in plan_executor as a LangGraph state
        machine, not inline here. It still visits steps in position
        order, but it can also loop back and retry a step with looser
        constraints -- a cycle the compiled plan deliberately cannot
        express, since compile_plan makes references point strictly
        backward. This method keeps only what happens around that walk:
        the single-step shortcut, and composing the final message.
        """
        if not plan.steps:
            return AssistantResponse(
                message="I couldn't understand that request. Could you rephrase it?",
                type="error",
                parsed_intent=ParsedIntent(intent="unsupported"),
                data={}
            )

        try:
            graph = compile_plan(plan)
        except PlanValidationError:
            # A structurally invalid plan (self-reference, forward
            # reference, reference to a step that doesn't exist) --
            # this is a bug in the LLM's output shape, not something a
            # user-facing "which game?" clarification could fix, so it's
            # reported the same way any other upstream parse failure is.
            return AssistantResponse(
                message="I couldn't put together a valid plan for that request. Could you rephrase it?",
                type="error",
                parsed_intent=plan.steps[0],
                data={}
            )

        if len(graph.steps) == 1:
            return self.execute(graph.steps[0].intent)

        # Execution proper lives in a LangGraph state machine (see
        # plan_executor): the same position-order walk this did inline,
        # plus one recovery cycle -- a step that matches nothing, and that
        # a later step depends on, gets its model-invented numeric bounds
        # dropped and is retried once. That cycle is why this isn't still
        # a plain loop: compile_plan's acyclic-by-construction guarantee
        # means the plan itself cannot express "try again, looser".
        state = run_plan(self, graph)
        results: dict[int, AssistantResponse] = state["results"]
        final = state["final"]

        if len(results) > 1 and final is not None and final.type not in ("error", "clarification"):
            # "Based on X: ..." only makes sense when exactly one earlier
            # step fed everything downstream of it. With two or more
            # independent sources merging into one step (e.g. two browse
            # steps into one compare), there's no single "based on" to
            # name -- and the response's own data (the comparison table)
            # already makes the sources obvious, so the prefix is skipped.
            sources = {p for node in graph.steps for p in node.depends_on}
            if len(sources) == 1:
                source = next(iter(sources))
                chained_names = [name for name, _ in extract_chainable_values(results[source])]
                if len(chained_names) == 1:
                    final = final.model_copy(update={"message": f"Based on {chained_names[0]}: {final.message}"})
                elif len(chained_names) > 1:
                    final = final.model_copy(update={"message": f"Based on {len(chained_names)} suggestions ({', '.join(chained_names)}): {final.message}"})

        if state["relaxed_filters"] and final is not None and final.type not in ("error", "clarification"):
            # Applied last, so the caveat frames the whole answer rather
            # than getting buried inside the "Based on X" prefix above.
            # Never silently answer a different question than the one
            # asked: if a constraint had to be dropped to find anything,
            # the response says so.
            #
            # Attributed per step rather than pooled: with more than one
            # step relaxed, a flat list reads as though a single query
            # carried every dropped bound, and the user can't tell which
            # part of their request was loosened.
            per_step = [
                f"{', '.join(sorted(dropped))} on step {position}"
                for position, dropped in sorted(state["relaxed_filters"].items())
                if dropped
            ]
            if len(per_step) == 1:
                # One relaxed step is the overwhelmingly common case, and
                # naming a step number there is noise, not precision.
                only = sorted(next(iter(state["relaxed_filters"].values())))
                what = ", ".join(only)
            else:
                what = "; ".join(per_step)
            final = final.model_copy(update={
                "message": f"Nothing matched every constraint, so I relaxed {what}. {final.message}"
            })

        # The walk always runs at least one step (the single-step case
        # returned above), and every path through plan_executor sets final.
        assert final is not None
        return final

    def _resolve_bgg_id(self, name: str, known_bgg_ids: dict[str, int]) -> int:
        """Resolves a game name to its bgg_id, preferring an already-known
        exact id (populated by resolve_step for every name substituted
        from an earlier step's result) over the fuzzy EntityResolver.
        Skipping the resolver for an already-exact name matters because
        re-running it through EntityResolver.resolve_game() -- built for
        fuzzy, typed-in user text -- can still spuriously raise
        AmbiguousEntityError on it (measured: "Witch Hunt" did this).
        """
        return known_bgg_ids.get(name) or self.resolver.resolve_game(name)

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
            max_year=assistant_filters.max_year,
            min_playtime=assistant_filters.min_playtime,
            max_playtime=assistant_filters.max_playtime
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

    def _handle_browse(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
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
            results = self.search_service.search(SearchQuery(q=query, mode=SearchMode.HYBRID, sort=intent.sort), skip=0, limit=intent.limit or 20)
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
            max_year=db_filters.max_year,
            min_playtime=db_filters.min_playtime,
            max_playtime=db_filters.max_playtime
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

    def _handle_search(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
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
            
        sq = SearchQuery(q=intent.query or "", mode=mode, filters=db_filters, sort=intent.sort)
        results = self.search_service.search(sq, skip=0, limit=intent.limit or 20)
        
        # Serialize the paginated search results
        return AssistantResponse(
            message=f"I found {results.total} games matching '{intent.query}'.",
            type="search_results",
            parsed_intent=intent,
            data={"total": results.total, "results": [{"game": GameResponse.model_validate(item.game).model_dump(), "score": item.score} for item in results.items]}
        )

    def _handle_recommend(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
        if not intent.game_name:
            intent.needs_clarification = True
            intent.clarification_question = "Which game do you want recommendations for?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        bgg_id = self._resolve_bgg_id(intent.game_name, known_bgg_ids)
        
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

    def _handle_compare(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
        if not intent.game_names or len(intent.game_names) < 2:
            intent.needs_clarification = True
            intent.clarification_question = "Which games do you want to compare? Please name at least two."
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        names = intent.game_names[:MAX_COMPARE_GAMES]
        bgg_ids = [self._resolve_bgg_id(name, known_bgg_ids) for name in names]
        games = [self.game_service.get_game(bgg_id) for bgg_id in bgg_ids]
        games = [g for g in games if g is not None]

        if len(games) < 2:
            return AssistantResponse(
                message="I could only find one of those games, so there's nothing to compare.",
                type="error",
                parsed_intent=intent,
                data={"games": [GameResponse.model_validate(g).model_dump() for g in games]}
            )

        return AssistantResponse(
            message=f"Here's a comparison of {len(games)} games.",
            type="comparison",
            parsed_intent=intent,
            data={"games": [GameResponse.model_validate(g).model_dump() for g in games]}
        )

    def _handle_get_game(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
        if not intent.game_name:
            intent.needs_clarification = True
            intent.clarification_question = "Which game are you looking for?"
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        bgg_id = self._resolve_bgg_id(intent.game_name, known_bgg_ids)
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

    def _handle_get_aspects(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
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

        bgg_id = self._resolve_bgg_id(intent.game_name, known_bgg_ids)
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

    def _handle_get_reviews(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
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

        bgg_id = self._resolve_bgg_id(intent.game_name, known_bgg_ids)
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

    def _handle_unsupported(self, intent: ParsedIntent, known_bgg_ids: dict[str, int]) -> AssistantResponse:
        """A request with nothing to do with board games (small talk,
        general knowledge, questions about the assistant itself). The
        message is fixed here rather than left to the LLM's phrasing --
        the small model has shown it can't be trusted to word a graceful
        decline consistently (e.g. answering "tell me a joke" with a
        clarifying question about what *type* of joke instead of declining).
        """
        return AssistantResponse(
            message=(
                "I can only help with board games -- browsing and searching the catalog, "
                "recommendations, comparing games, game details (rank, rating, complexity, "
                "players, age, playtime), and what reviewers think. What would you like to "
                "know about a game?"
            ),
            type="unsupported",
            parsed_intent=intent,
            data={}
        )
