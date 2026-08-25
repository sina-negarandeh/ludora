
from sqlalchemy.orm import Session

from app.core.ml_config import ABSAConfig
from app.schemas.assistant import AssistantResponse, ParsedIntent, ParsedPlan
from app.schemas.game import GameResponse
from app.schemas.game_query import GameFilter
from app.schemas.search import SearchMode, SearchQuery
from app.services.aspect_service import AspectAggregateResponse, AspectService
from app.services.entity_resolver import AmbiguousEntityError, EntityNotFoundError, EntityResolver
from app.services.game_service import GameService
from app.services.plan_graph import PlanStep, PlanValidationError, compile_plan
from app.services.recommendation_service import RecommendationService
from app.services.review_service import ReviewService
from app.services.search_service import SearchService


class AssistantOrchestrator:
    # Cap on how many games a "compare" request will fetch/render -- past
    # this many, a comparison table stops being readable in the narrow
    # assistant drawer.
    MAX_COMPARE_GAMES = 5

    def __init__(self, db: Session):
        self.db = db
        # Defaults to empty so execute() alone (without going through
        # execute_plan()) is still safe -- e.g. direct use in a script.
        # execute_plan() resets this per request; see there and
        # _handle_compare() for what it's for.
        self._known_bgg_ids: dict = {}
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
            elif intent.intent == "compare":
                return self._handle_compare(intent)
            elif intent.intent == "get_game":
                return self._handle_get_game(intent)
            elif intent.intent == "get_aspects":
                return self._handle_get_aspects(intent)
            elif intent.intent == "get_reviews":
                return self._handle_get_reviews(intent)
            elif intent.intent == "unsupported":
                return self._handle_unsupported(intent)
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
        checked to point at an earlier, existing step up front, so this
        loop never has to handle an out-of-range or forward reference
        itself; if compile_plan doesn't raise, every dependency lookup
        below is guaranteed safe.

        Deliberately a plain linear walk over a graph that's acyclic by
        construction, not a scheduler: with at most
        AssistantConfig.MAX_PLAN_STEPS steps and no need for parallelism
        (the single LLM call already dominates latency), there's nothing
        to schedule.
        """
        # Request-scoped map of already-exact game names (ones that came
        # from a placeholder expansion, not user-typed text) to their
        # known bgg_id -- see _resolve_step and _handle_compare's use of it.
        self._known_bgg_ids: dict = {}

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

        results: dict[int, AssistantResponse] = {}
        final = None
        for node in graph.steps:
            step = node.intent
            if node.depends_on:
                # Safe without a None-check: compile_plan guarantees every
                # position in depends_on is < node.position, and positions
                # only enter `results` in increasing order below -- if a
                # referenced step were missing, an earlier iteration would
                # already have broken out of this loop.
                priors = [results[p] for p in node.depends_on]
                bad = next((r for r in priors if r.type in ("error", "clarification")), None)
                if bad is None:
                    # A dependency that ran cleanly but matched nothing
                    # can't feed this step either. Surface its own response
                    # for the same reason the error case above does: the
                    # step that actually ran the query already explains the
                    # outcome in the user's terms ("I couldn't find any
                    # games matching your preferences"), which beats this
                    # layer restating it as an internal-sounding failure.
                    bad = next((r for r in priors if not self._extract_chainable_values(r)), None)
                if bad is not None:
                    final = bad
                    break
                resolved_step = self._resolve_step(node, results)
                if resolved_step is None:
                    # Everything this step depends on found SOMETHING (the
                    # empty case is already handled above), so the only way
                    # to get here is a count mismatch: a slot that needs
                    # exactly one game got several, and picking one
                    # arbitrarily would be a guess at what was meant.
                    final = AssistantResponse(
                        message="That part of your request needed a single game from an earlier step, but more than one matched. Could you be more specific?",
                        type="clarification",
                        parsed_intent=step,
                        data={}
                    )
                    break
                step = resolved_step

            response = self.execute(step)
            results[node.position] = response
            final = response
            if response.type in ("error", "clarification"):
                # Failure isolation: stop the chain here rather than
                # running further steps against a state we know is bad,
                # but whatever earlier steps succeeded stays in `results`
                # even though only `final` is returned to the caller today.
                break

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
                chained_names = [name for name, _ in self._extract_chainable_values(results[source])]
                if len(chained_names) == 1:
                    final = final.model_copy(update={"message": f"Based on {chained_names[0]}: {final.message}"})
                elif len(chained_names) > 1:
                    final = final.model_copy(update={"message": f"Based on {len(chained_names)} suggestions ({', '.join(chained_names)}): {final.message}"})

        # graph.steps is non-empty here (the len == 1 case already
        # returned above), so the loop runs at least once and every
        # iteration sets final before continuing or breaking.
        assert final is not None
        return final

    def _resolve_step(self, node: PlanStep, results: dict) -> ParsedIntent | None:
        """Substitutes every "$stepN" placeholder in node.intent's
        game_name/game_names with real values drawn from `results`, per
        node.depends_on (already validated non-empty and, by
        compile_plan's guarantee, all already executed and present in
        `results`). Returns None if a referenced step's result can't
        supply what this step needs -- the caller turns that into a
        user-facing error rather than guessing forward.

        Three shapes, all handled uniformly by resolving every distinct
        referenced position once and then applying it wherever it's used:

        - "game_name" is itself a placeholder: needs exactly one game.
        - "game_names" has exactly one placeholder entry: this is the one
          case a placeholder can stand for MULTIPLE games at once (e.g.
          "suggest some games and compare them") -- if the referenced
          step resolved to more than one game, every one of them is used,
          capped at MAX_COMPARE_GAMES, replacing the whole game_names
          list rather than merging with any sibling literal entries
          (measured directly against this server: the model paired a
          many-valued placeholder with a second, fabricated literal title
          that wasn't in the user's request at all).
        - "game_names" has two or more DISTINCT placeholder entries (e.g.
          ["$step0", "$step1"] -- "compare the heaviest game to the
          highest-rated game", two independent prior steps merging into
          one compare): each referenced step must resolve to exactly one
          game. Comparing two open-ended GROUPS of suggestions against
          each other isn't well defined, so if any of them resolves to
          more than one game, that's an error rather than a guess at
          which games from which group to pair.

        known_bgg_ids is populated for every substituted name in every
        case: these names came straight off an earlier GameResponse, so
        they're already exact, and _handle_compare skips re-resolving
        them through the fuzzy EntityResolver, which can still spuriously
        raise AmbiguousEntityError on an exact title (measured: "Witch
        Hunt" did this).
        """
        step = node.intent
        resolved: dict[int, list] = {}
        for position in node.depends_on:
            values = self._extract_chainable_values(results[position])
            if not values:
                return None
            resolved[position] = values

        updates = {}

        if node.game_name_ref is not None:
            values = resolved[node.game_name_ref]
            if len(values) != 1:
                return None
            name, bgg_id = values[0]
            self._known_bgg_ids[name] = bgg_id
            updates["game_name"] = name

        if node.game_names_refs:
            # game_names_refs is only populated by compile_plan when it
            # found placeholder matches while iterating step.game_names,
            # so game_names is guaranteed non-None here.
            assert step.game_names is not None
            new_names = list(step.game_names)
            if len(node.game_names_refs) == 1:
                (idx, position), = node.game_names_refs.items()
                values = resolved[position]
                for name, bgg_id in values:
                    self._known_bgg_ids[name] = bgg_id
                if len(values) == 1:
                    new_names[idx] = values[0][0]
                else:
                    capped = values[:self.MAX_COMPARE_GAMES]
                    new_names = [name for name, _ in capped]
            else:
                for idx, position in node.game_names_refs.items():
                    values = resolved[position]
                    if len(values) != 1:
                        return None
                    name, bgg_id = values[0]
                    self._known_bgg_ids[name] = bgg_id
                    new_names[idx] = name
            updates["game_names"] = new_names

        return step.model_copy(update=updates) if updates else step

    def _extract_chainable_values(self, response: AssistantResponse) -> list:
        """Pulls every (name, bgg_id) pair out of a step's result --
        used when a dependent step needs every game an earlier step
        found (a "compare" one-to-many placeholder), or just to check
        how many games a dependency resolved to when deciding whether a
        substitution is unambiguous (see _resolve_step). The bgg_id
        travels with the name so _resolve_step can let the handlers
        below skip re-resolving a title that's already exact -- see
        _resolve_bgg_id for why that matters.
        """
        if not response.data:
            return []
        games = response.data.get("games")
        if games:
            return [(g["name"], g["bgg_id"]) for g in games if g.get("name") and g.get("bgg_id")]
        results = response.data.get("results")
        if results:
            return [(r["game"]["name"], r["game"]["bgg_id"]) for r in results if r.get("game", {}).get("name") and r.get("game", {}).get("bgg_id")]
        recommendations = response.data.get("recommendations")
        if recommendations:
            return [(r["game"]["name"], r["game"]["bgg_id"]) for r in recommendations if r.get("game", {}).get("name") and r.get("game", {}).get("bgg_id")]
        game = response.data.get("game")
        if game and game.get("name") and game.get("bgg_id"):
            return [(game["name"], game["bgg_id"])]
        return []

    def _resolve_bgg_id(self, name: str) -> int:
        """Resolves a game name to its bgg_id, preferring an already-known
        exact id (populated by _resolve_step for every name substituted
        from an earlier step's result) over the fuzzy EntityResolver.
        Skipping the resolver for an already-exact name matters because
        re-running it through EntityResolver.resolve_game() -- built for
        fuzzy, typed-in user text -- can still spuriously raise
        AmbiguousEntityError on it (measured: "Witch Hunt" did this).
        """
        return self._known_bgg_ids.get(name) or self.resolver.resolve_game(name)

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
            
        sq = SearchQuery(q=intent.query or "", mode=mode, filters=db_filters, sort=intent.sort)
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

        bgg_id = self._resolve_bgg_id(intent.game_name)
        
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

    def _handle_compare(self, intent: ParsedIntent) -> AssistantResponse:
        if not intent.game_names or len(intent.game_names) < 2:
            intent.needs_clarification = True
            intent.clarification_question = "Which games do you want to compare? Please name at least two."
            return AssistantResponse(
                message=intent.clarification_question,
                type="clarification",
                parsed_intent=intent,
                data={}
            )

        names = intent.game_names[:self.MAX_COMPARE_GAMES]
        bgg_ids = [self._resolve_bgg_id(name) for name in names]
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

        bgg_id = self._resolve_bgg_id(intent.game_name)
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

        bgg_id = self._resolve_bgg_id(intent.game_name)
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

        bgg_id = self._resolve_bgg_id(intent.game_name)
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

    def _handle_unsupported(self, intent: ParsedIntent) -> AssistantResponse:
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
