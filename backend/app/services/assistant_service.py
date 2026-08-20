import json
import re
from typing import Optional
from openai import OpenAI
from pydantic import ValidationError
from app.core.config import settings
from app.core.ml_config import AssistantConfig
from app.schemas.assistant import ParsedIntent, ParsedPlan

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

class AssistantService:
    def __init__(self):
        # Local MLX / OpenAI-compatible server, or real OpenAI if configured.
        self.client = OpenAI(base_url=settings.OPENAI_BASE_URL, api_key=settings.OPENAI_API_KEY)
        # MLX server expects the exact HuggingFace repo ID.
        self.model = settings.LLM_MODEL_NAME
        # Separate, larger model for parse_plan() -- see PLAN_MODEL_NAME
        # in app.core.config for why this isn't the same as self.model.
        self.plan_model = settings.PLAN_MODEL_NAME

    def _intent_rules_text(self) -> str:
        """The per-step parsing rules, shared verbatim by the single-intent
        prompt and the plan prompt below -- these govern how to fill in
        one intent's fields regardless of whether it's the only step or
        one of several. Kept as its own method so the two prompt builders
        can't drift out of sync on what a valid step looks like.
        """
        return """1. "intent" MUST be one of the enums (browse, search, recommend, compare, get_game, get_reviews, get_aspects, unsupported).
2. Understand the strict differences between these tag types -- do not mix them up:
   - Categories: BGG's broad subject/format classification, e.g. Card Game, Wargame, Fantasy, Economic, Trains.
   - Subdomains: BGG's 8 coarse rank/leaderboard types. Valid Subdomains are EXACTLY: Abstract, CGS, Childrens, Family, Party, Strategy, Thematic, War.
   - Themes: Narrow setting/franchise tags, e.g. Zombies, Cthulhu Mythos, Alchemy, Anime / Manga.
   - Mechanics: Gameplay mechanisms, e.g. Worker Placement, Deck Building, Area Control, Dice Rolling.
   - Families: BGG's `family` tag system -- specific, narrow series/groupings, stored as "Group: Value" strings (e.g. "Series: ...", "Crowdfunding: Kickstarter"). Extremely numerous and inconsistently formatted -- only set this if the user names a specific series/family explicitly and you're confident of the exact stored wording; when unsure, leave it unset and prefer categories/subdomains/themes/mechanics instead.
   - Designers / Artists / Publishers: real people or company names credited on the game. Only set these when the user explicitly names a specific person or company -- never guess a name from a genre or vibe.
3. Here are examples of correct tag parsing:
   - "strategy games" -> subdomains=["Strategy"]
   - "party games" -> subdomains=["Party"]
   - "card games" -> categories=["Card Game"]
   - "games with worker placement" -> mechanics=["Worker Placement"]
   - "zombie games" -> themes=["Zombies"]
   - "games designed by Uwe Rosenberg" -> designers=["Uwe Rosenberg"]
   - "anything published by Days of Wonder" -> publishers=["Days of Wonder"]
   - "tell me about Catan" / "what is Catan" / "info on Catan" -> intent="get_game", game_name="Catan" (a request naming ONE specific game, asking about it in general, is get_game -- NOT browse or search, even without the word "game" in it).
4. If the user's request is too ambiguous or missing context, set "needs_clarification" to true and ask a "clarification_question".
5. If "intent" is "get_game" or "recommend" for a specific game, provide "game_name" -- ALWAYS extract the actual game name out of phrases like "like X", "similar to X", "recommend X", even when the word "game" or "games" also appears in the sentence. "game_name" is ONLY the title itself, never the whole sentence and never left empty when a title is present. Examples:
   - "recommend games like Brass Birmingham" -> recommend, game_name="Brass Birmingham"
   - "similar games to Catan" -> recommend, game_name="Catan"
   - "games like Wingspan" -> recommend, game_name="Wingspan" (NOT browse -- "like X" naming one game is always recommend)
   - "suggest something similar to Gloomhaven" -> recommend, game_name="Gloomhaven"
6. For "recommend", "recommendation_family" is one of popularity, content, collaborative, or hybrid -- default to hybrid if the user doesn't specify one.
7. "compare" needs "game_names" (a list, NOT "game_name") with the actual titles -- ALWAYS extract two or more real game names, never leave it empty when names are present. Examples:
   - "compare Catan and Terraforming Mars" -> compare, game_names=["Catan", "Terraforming Mars"]
   - "how does Brass Birmingham compare to Brass Lancashire" -> compare, game_names=["Brass Birmingham", "Brass Lancashire"]
   - "Wingspan vs Everdell vs Photosynthesis" -> compare, game_names=["Wingspan", "Everdell", "Photosynthesis"]
   If only one game is named, that's not a comparison -- use "get_game" instead and set "needs_clarification" only if the request is genuinely ambiguous about which second game to compare against.
8. If "intent" is "get_game" and the user is asking about one or more SPECIFIC official facts rather than general info, set "requested_facts" to the relevant subset of [rank, rating, complexity, player_count, age, playtime]. Examples:
   - "what rank is Catan" -> get_game, game_name="Catan", requested_facts=["rank"]
   - "what's the rating of Brass Birmingham" -> get_game, game_name="Brass Birmingham", requested_facts=["rating"]
   - "how heavy is Brass Birmingham" -> get_game, game_name="Brass Birmingham", requested_facts=["complexity"]
   - "is Wingspan good for kids" -> get_game, game_name="Wingspan", requested_facts=["age"]
   - "how long does Gloomhaven take to play" -> get_game, game_name="Gloomhaven", requested_facts=["playtime"]
   - "how many people can play Terraforming Mars, and how long does it take" -> get_game, game_name="Terraforming Mars", requested_facts=["player_count", "playtime"]
   Leave "requested_facts" unset for a general request like "tell me about Catan".
9. "get_game" and "requested_facts" (rule 8) are ONLY for a request that already NAMES a specific game. A request that asks to FIND or IDENTIFY a game by some criterion, with no game named yet, is "browse" instead -- use "sort" (and "limit" if only the single best match is wanted). This is also how every superlative ("the X-est game") is expressed, for any sortable field (rule 13's player counts have no superlative form; rank/rating/complexity/year/playtime all do) -- never invent a "game_name" out of a criterion word like "rank" or "heaviest". Examples:
   - "what game is ranked 1st overall" -> browse, sort={{"field":"rank", "direction":"asc"}}, limit=1 (NOT get_game, NOT game_name="rank")
   - "what's the heaviest game" -> browse, sort={{"field":"complexity", "direction":"desc"}}, limit=1
   - "what's the highest rated strategy game" -> browse, subdomains=["Strategy"], sort={{"field":"rating", "direction":"desc"}}, limit=1
   - "what's the longest game to play" -> browse, sort={{"field":"playtime", "direction":"desc"}}, limit=1
   - "the newest strategy game", "the most recent release" -> browse, sort={{"field":"year", "direction":"desc"}}, limit=1 (a recency word with no actual year named is this same sort pattern, NOT a guessed "min_year" -- see rule 15)
10. "browse" filters (categories/subdomains/themes/mechanics/families) ONLY accept values from the real, fixed BGG taxonomy -- never invent a value for a franchise, character, brand, or fictional universe. These are NOT real category/theme values and filtering on them will fail. If the request is about a franchise/character/brand or any other concept that doesn't map onto the taxonomy in rule 2, use "search" instead with that text as "query" -- free-text search over game names and descriptions can find these, filters can't. "search" supports "sort" and "limit" exactly like "browse" does (rule 9) -- always set them when the request asks for the best/top/highest/lowest by some criterion, not just when it asks for everything matching. Examples (the franchise/brand itself is never a real tag value -- the specific name below doesn't matter, the pattern does):
   - "marvel games with spiderman in them" -> search, query="marvel spiderman" (NOT browse with themes=["Marvel","Spiderman"] -- these aren't real theme values)
   - "star wars themed games" -> search, query="star wars"
   - "games about pirates" -> search, query="pirates" (unless "Pirates" is a real category/theme you're confident exists)
   - "highest rated harry potter game" -> search, query="harry potter", sort={{"field":"rating","direction":"desc"}}, limit=1 (a criterion word like "highest rated" is a sort, never part of "query")
11. "get_aspects" and "get_reviews" both need "game_name" and answer different questions -- do not confuse them:
   - "get_aspects": a general opinion/sentiment question -- "what do people think of X", "is the theme good", "users' thoughts on X", "how are the reviews". Returns a community consensus summary plus a per-aspect sentiment breakdown, NOT raw review text.
   - "get_reviews": the user explicitly wants to read actual written reviews -- "show me some reviews of X", "what did people write about X".
   Examples:
   - "what do people think of Wingspan" -> get_aspects, game_name="Wingspan"
   - "is the theme in Ark Nova any good" -> get_aspects, game_name="Ark Nova"
   - "show me some reviews of Gloomhaven" -> get_reviews, game_name="Gloomhaven"
12. If the request has nothing to do with board games or this assistant's capabilities (browse/search/recommend/compare/get_game/get_reviews/get_aspects), set intent="unsupported" -- do NOT force it into another intent, do NOT invent a "game_name" out of it, and do NOT set "needs_clarification" (there's nothing to clarify -- the request is simply out of scope). This covers: questions about the assistant itself (its age, name, feelings, how it works), general knowledge unrelated to board games, jokes, small talk, math, or requests for any other kind of help. Examples:
   - "how old are you?" -> unsupported
   - "what's your name?" -> unsupported
   - "what is the capital of France?" -> unsupported
   - "tell me a joke" -> unsupported
   - "what's 2+2?" -> unsupported
   If the request is AT LEAST plausibly about board games (even if oddly phrased or missing details), it is NOT unsupported -- use "needs_clarification" on the appropriate intent instead.
13. Player count filters ("exact_players"/"min_players"/"max_players", on "browse" or "search"): "exact_players" means "playable by a group of exactly N" -- use it for "a group of N people", "for N players", "we're N of us". This is NOT the same as setting "min_players" AND "max_players" to that same N together, which instead means "a game whose full supported range is ONLY N to N" -- far stricter, and almost never what's actually meant. Only use "min_players"/"max_players" for a genuine range or one-sided bound the user actually stated. Examples:
   - "a group of 5 people", "for 5 players", "we're 5 of us" -> exact_players=5
   - "for 2-4 players" -> min_players=2, max_players=4
   - "games for at least 6 players" -> min_players=6
   - "games for no more than 3 players" -> max_players=3
14. Complexity filters ("min_complexity"/"max_complexity", 1.0-5.0 BGG weight scale) are for a RANGE the user wants -- separate from rule 9's sort-based "the heaviest/lightest game" (a single best match, not a range). Always use the user's own number when they give one. Absent a number, these are reasonable defaults for common phrasing:
   - "games under 2.5 complexity", "weight below 3" -> use the user's exact number as max_complexity
   - "beginner-friendly", "light", "easy to learn" games (no number given) -> max_complexity=2.0
   - "heavy", "complex", "meaty" games (no number given) -> min_complexity=3.5
15. Year filters ("min_year"/"max_year") are for an explicit year or range the user actually names. A vague recency word with no year ("recent", "new", "latest", "newest") is rule 9's sort pattern instead, not a filter -- there's no fixed "recent" cutoff to guess. Examples:
   - "games published after 2015" -> min_year=2015
   - "games from before 2000" -> max_year=2000
   - "games from the 2010s" -> min_year=2010, max_year=2019
   - "recent strategy games", "the newest releases" -> that's rule 9: browse, sort={{"field":"year","direction":"desc"}} (NOT a guessed min_year)
16. Playtime filters ("min_playtime"/"max_playtime", minutes) work the same way as complexity (rule 14) -- the user's own number always wins; these are reasonable defaults without one. A superlative ("the longest game") is rule 9's sort pattern instead, not a filter. Examples:
   - "games under an hour", "less than 60 minutes" -> use the user's exact number as max_playtime
   - "quick games", "short games" (no number given) -> max_playtime=30
   - "long games", "epic games" (no number given) -> min_playtime=90
17. "search_mode" (lexical, semantic, or hybrid) almost always stays unset -- the default hybrid blends exact-text and thematic matching, right for nearly every request. Only set it when the user explicitly asks for one kind specifically: "lexical" for an exact-title/keyword lookup, "semantic" for a purely thematic/vibe-based ask unrelated to exact wording."""

    def _build_system_prompt(self) -> str:
        """The full, static single-step system prompt — independent of any
        user message, so callers (e.g. an eval harness computing a
        prompt-version hash) can reconstruct exactly what was sent without
        duplicating it.

        /no_think: LLM_MODEL_NAME is Qwen3-4B, the same "thinking"-capable
        model family SummarizationService's prompts already prefix with
        /no_think — single-shot JSON classification doesn't need or want
        extended reasoning, and unsuppressed thinking output would land
        before the JSON and break model_validate_json().
        """
        schema_json = ParsedIntent.model_json_schema()
        return f"""/no_think
You are the Ludora Assistant, an expert in board games.
Your job is to parse the user's natural language request into a strictly structured JSON intent object.
DO NOT answer the user's question. Just output the JSON.

Here is the JSON Schema you MUST follow:
{json.dumps(schema_json, indent=2)}

Important Rules:
{self._intent_rules_text()}
18. Output ONLY valid JSON matching the schema. No markdown wrapping.
"""

    def _build_plan_system_prompt(self, allow_thinking: bool = False) -> str:
        """The plan-based system prompt used by parse_plan(). Reuses the
        same per-step rules as the single-step prompt above (via
        _intent_rules_text()), then adds decomposition-specific rules on
        top -- most requests should still come back as a one-step plan;
        the model only needs to reach for a second step when a later
        step's input genuinely can't be filled in without an earlier
        step's result.

        allow_thinking defaults to False (sends /no_think) because most
        chat messages go through this same prompt regardless of whether
        they end up single- or multi-step, and /no_think has never
        caused a problem on the single-step case -- paying thinking-mode
        latency on every message just to cover the harder minority would
        be the wrong tradeoff. parse_plan() only passes True on a retry,
        after a first /no_think attempt already failed to parse.

        Measured directly against this server: with /no_think, Qwen3-4B
        reliably emitted a structurally invalid JSON plan (one extra
        closing brace) on a query needing real decomposition --
        byte-identical across temperatures 0.0 and 0.3, so not a
        sampling fluke; allowing thinking mode fixed it in the same test
        (valid JSON, correctly structured) at roughly 8x the latency
        (2.3s -> 17.9s for that query).
        """
        schema_json = ParsedPlan.model_json_schema()
        thinking_directive = "" if allow_thinking else "/no_think\n"
        return f"""{thinking_directive}You are the Ludora Assistant, an expert in board games.
Your job is to parse the user's natural language request into a strictly structured JSON plan: a list of one or more steps.
DO NOT answer the user's question. Just output the JSON.

Here is the JSON Schema you MUST follow:
{json.dumps(schema_json, indent=2)}

Each step in "steps" follows these rules:
{self._intent_rules_text()}

Planning rules (how many steps, and how they connect):
19. Almost every request is ONE step. Only emit more than one step when a later step's "game_name" or an entry in its "game_names" genuinely cannot be filled in without first resolving an earlier step's answer -- for example the request names a game only by a criterion ("the highest-rated strategy game"), not by title, and then asks a second, different question about that game.
20. Each step needs a "step_id" starting at 0 and counting up in the order the steps must run. A step that depends on an earlier one sets "depends_on_step" to that earlier step's "step_id" AND sets the referencing field ("game_name", or one entry of "game_names") to the literal placeholder string "$stepN" (where N is that step_id) instead of guessing a real title -- the actual title isn't known until step N has actually run. Never invent a game name to avoid using a placeholder.
21. A step with no "depends_on_step" set (the default: null) is independent and needs no placeholder.
22. A "compare" step's "game_names" can hold "$stepN" placeholders in two different shapes -- tell them apart by how many DISTINCT step numbers appear, not by counting entries:
   - ONE distinct placeholder, standing for MULTIPLE games at once (e.g. game_names=["$step0"]) -- use this when the request wants to compare several suggested/found games against each other, not chain one resolved game into a second lookup. Set that earlier step's "limit" to how many games you want compared (2 to 5) -- do not also invent extra literal titles alongside it that the user never named.
   - TWO OR MORE distinct placeholders, each from its OWN independent earlier step (e.g. game_names=["$step0", "$step1"]) -- use this when the request names two SEPARATE, unrelated criteria to find independently and then compare, not one group of suggestions. Neither earlier step depends on the other; only the compare step depends on both, and "depends_on_step" on it only needs to name one of them for reference. Each of those two (or more) earlier steps is an ordinary, independent step and STILL needs its own "sort" + "limit"=1 exactly as rule 9 already requires for any single superlative -- decomposing into more steps never relaxes that.
23. When a step's game is a "$stepN" placeholder instead of a real title, every rule above STILL applies exactly the same way -- being chained changes nothing about which intent or fields are correct, and this includes every step that feeds a later comparison, not only the ones a single question is asked about directly. In particular: rule 8's get_game + "requested_facts" (rank, rating, complexity, player_count, age, OR playtime -- all six, not only whichever one appears in an example below) is the right choice any time the question asks for one specific official number or spec about that game, even when phrased indirectly ("is it good for kids" means requested_facts=["age"]; "how long does it take" means requested_facts=["playtime"]). Only use get_aspects when the question is actually about subjective opinion ("what do people think", "is it fun", "is the theme good"), never merely because the game is a placeholder.
24. Keep the criterion that FINDS a step's game separate from the fact being ASKED about it in a later step -- they are not the same thing and must not be merged into one step's filters. "The top ranked game" is a sort with no filters (there's no genre restriction stated); "is it good for kids" is a separate question about that specific game (requested_facts=["age"] on the next step), not a filter for finding it. Do not fold a later step's question into an earlier step's filters just because they appear in the same sentence.
25. Worked examples:
   - "recommend games like the highest rated strategy game" -> two steps: step_id=0, intent="browse", filters={{"subdomains":["Strategy"]}}, sort={{"field":"rating","direction":"desc"}}, limit=1; step_id=1, intent="recommend", game_name="$step0", depends_on_step=0.
   - "what do people think of the most complex game in the catalog" -> step_id=0, intent="browse", sort={{"field":"complexity","direction":"desc"}}, limit=1; step_id=1, intent="get_aspects", game_name="$step0", depends_on_step=0. (Opinion question -> get_aspects.)
   - "what's the rating of the most complex game in strategy games" -> step_id=0, intent="browse", filters={{"subdomains":["Strategy"]}}, sort={{"field":"complexity","direction":"desc"}}, limit=1; step_id=1, intent="get_game", game_name="$step0", requested_facts=["rating"], depends_on_step=0. (One specific official number -> get_game + requested_facts, NOT get_aspects, per rule 23.)
   - "is the top ranked game good for kids" -> step_id=0, intent="browse", sort={{"field":"rank","direction":"asc"}}, limit=1 (NO filters -- "top ranked" names no genre, per rule 24); step_id=1, intent="get_game", game_name="$step0", requested_facts=["age"], depends_on_step=0 (an age-appropriateness question is the "age" official fact, NOT get_aspects, and NOT a filters.subdomains=["Childrens"] on step 0).
   - "show me some reviews of the top ranked party game" -> step_id=0, intent="browse", filters={{"subdomains":["Party"]}}, sort={{"field":"rank","direction":"asc"}}, limit=1; step_id=1, intent="get_reviews", game_name="$step0", depends_on_step=0. (Explicitly wants written reviews -> get_reviews, chained exactly like the other intents above -- do not collapse this into a single get_reviews step with the criterion phrase as a literal game_name.)
   - "compare the heaviest game to Brass Birmingham" -> step_id=0, intent="browse", sort={{"field":"complexity","direction":"desc"}}, limit=1; step_id=1, intent="compare", game_names=["$step0", "Brass Birmingham"], depends_on_step=0. (Exactly one game resolved from step 0, paired with one literal name -- ordinary single-value substitution, per rule 22's first shape.)
   - "we're 5 people looking for something fun and not too heavy tonight, maybe a party game, any suggestions? can you compare them" -> step_id=0, intent="browse", filters={{"subdomains":["Party"]}}, exact_players=5, max_complexity=2.5, sort={{"field":"rating","direction":"desc"}}, limit=3; step_id=1, intent="compare", game_names=["$step0"], depends_on_step=0. (The request wants several suggestions compared against each other, not one game chained into a second lookup -- per rule 22's first shape, one placeholder stands for all of step 0's results; do not add a second literal title alongside it.)
   - "find games with pokemon in it and compare the top 3 in terms of rating" -> step_id=0, intent="search", query="pokemon", sort={{"field":"rating","direction":"desc"}}, limit=3 (per rule 10, "pokemon" is a franchise, not real taxonomy -- search, not browse; "top 3 in terms of rating" is that step's own sort+limit, same as rule 22's browse case, NOT left unset just because the prerequisite step is search instead of browse); step_id=1, intent="compare", game_names=["$step0"], depends_on_step=0. (Without an explicit limit here, expansion falls back to comparing however many matches exist, capped at 5 -- which answers "compare them" for every match, not the "top 3" the user actually asked for.)
   - "tell me about Catan" -> ONE step only: step_id=0, intent="get_game", game_name="Catan". Do not invent a second step when the first already answers the whole request.
   - "put the most complex strategy game up against the top ranked party game" -> THREE steps: step_id=0, intent="browse", filters={{"subdomains":["Strategy"]}}, sort={{"field":"complexity","direction":"desc"}}, limit=1; step_id=1, intent="browse", filters={{"subdomains":["Party"]}}, sort={{"field":"rank","direction":"asc"}}, limit=1 (independent of step 0 -- its own separate criterion, not chained from the first); step_id=2, intent="compare", game_names=["$step0", "$step1"], depends_on_step=0. (Per rule 22's second shape: two distinct placeholders, each from its own independent step -- and per rule 23, each of those two steps STILL needs its own sort+limit=1 exactly like any single superlative browse, same as every example above it. Do NOT chain step 1 off of step 0's result, since the two criteria don't depend on each other.)
26. Output ONLY valid JSON matching the schema. No markdown wrapping.
"""

    @staticmethod
    def _strip_markdown_json(raw_content: str) -> str:
        # Thinking mode (the plan prompt allows it; the single-step
        # prompt suppresses it via /no_think but this is harmless either
        # way) can prefix the real content with a <think>...</think>
        # block -- drop it before anything else.
        raw_content = _THINK_BLOCK_RE.sub("", raw_content, count=1)
        raw_content = raw_content.strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        elif raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        return raw_content.strip()

    @staticmethod
    def _parse_leading_json(raw_content: str) -> dict:
        """Parses the first complete JSON value in raw_content and
        ignores anything after it, instead of the strict all-or-nothing
        parsing model_validate_json() does.

        Measured directly against this server on the deeper-nested
        ParsedPlan schema: the model reliably appends exactly one extra
        closing brace after an otherwise fully valid, complete JSON
        object -- reproduced byte-identically across both temperature 0
        and 0.3, so this isn't a sampling fluke a retry can dodge. The
        leading document is already the complete, correct answer; only
        the trailing noise needs to be tolerated.
        """
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw_content)
        return obj

    @staticmethod
    def _temperature_for_attempt(attempt: int) -> float:
        """The first attempt runs at AssistantConfig.TEMPERATURE (0.0) for
        reproducible primary behavior. Retries (attempt > 0) switch to
        RETRY_TEMPERATURE so a retry isn't guaranteed to replay an
        identical completion. This helps with genuinely stochastic
        flakes (an empty completion), but measured directly against this
        server it is NOT reliable against a structural bug: one specific
        JSON malformation on the plan schema reproduced byte-identically
        across both 0.0 and 0.3 over multiple attempts. That class of
        error needs _parse_leading_json() below, not a different
        temperature -- this helper is kept for the flake case it was
        actually built for, not as a general-purpose retry strategy.
        """
        return AssistantConfig.TEMPERATURE if attempt == 0 else AssistantConfig.RETRY_TEMPERATURE

    def parse_query(self, user_message: str) -> ParsedIntent:
        system_prompt = self._build_system_prompt()

        # Retries, not just a single attempt: the same class of flake
        # SummarizationService._call_llm_json() was built to handle --
        # measured against this local server, an identical (temperature=0)
        # prompt occasionally comes back with an empty completion and
        # succeeds on a byte-identical retry. One bad call shouldn't fail
        # an entire user request.
        last_error: Optional[Exception] = None
        for attempt in range(AssistantConfig.MAX_LLM_RETRIES + 1):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature_for_attempt(attempt),
                max_tokens=AssistantConfig.MAX_TOKENS
            )

            raw_content = self._strip_markdown_json(response.choices[0].message.content or "{}")

            try:
                return ParsedIntent.model_validate(self._parse_leading_json(raw_content))
            except (ValidationError, json.JSONDecodeError) as e:
                last_error = e
                continue

        raise last_error

    def parse_plan(self, user_message: str) -> ParsedPlan:
        """Like parse_query(), but asks for a list of one or more steps
        instead of a single intent -- see _build_plan_system_prompt().
        Steps beyond AssistantConfig.MAX_PLAN_STEPS are dropped here,
        deterministically, rather than trusting the model's own restraint
        or re-prompting for a shorter plan. Sorted by step_id before
        truncating, not truncated in raw JSON-array order: a later,
        surviving step can only ever reference an earlier step_id (see
        plan_graph.compile_plan), so dropping the highest step_ids first
        guarantees truncation can never orphan a reference a kept step
        depends on -- truncating by array order instead could keep an
        arbitrary subset and silently strand a dependency.

        Runs on self.plan_model (the larger model, see PLAN_MODEL_NAME)
        with thinking mode always allowed, not gated behind a retry.
        Latency isn't a constraint for this project, so there's no
        reason to start with a faster-but-less-reliable configuration
        and only fall back after it fails -- always giving the model
        room to reason is strictly better here. The retry loop and
        temperature bump on later attempts stay as a backstop for
        genuinely stochastic flakes (an empty completion), not as the
        primary reliability mechanism anymore.
        """
        last_error: Optional[Exception] = None
        for attempt in range(AssistantConfig.MAX_LLM_RETRIES + 1):
            system_prompt = self._build_plan_system_prompt(allow_thinking=True)
            response = self.client.chat.completions.create(
                model=self.plan_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature_for_attempt(attempt),
                max_tokens=AssistantConfig.MAX_TOKENS
            )

            raw_content = self._strip_markdown_json(response.choices[0].message.content or "{}")

            try:
                plan = ParsedPlan.model_validate(self._parse_leading_json(raw_content))
                if len(plan.steps) > AssistantConfig.MAX_PLAN_STEPS:
                    plan.steps = sorted(plan.steps, key=lambda s: s.step_id)[:AssistantConfig.MAX_PLAN_STEPS]
                return plan
            except (ValidationError, json.JSONDecodeError) as e:
                last_error = e
                continue

        raise last_error
