import json
from typing import Optional
from openai import OpenAI
from pydantic import ValidationError
from app.core.config import settings
from app.core.ml_config import AssistantConfig
from app.schemas.assistant import ParsedIntent

class AssistantService:
    def __init__(self):
        # Local MLX / OpenAI-compatible server, or real OpenAI if configured.
        self.client = OpenAI(base_url=settings.OPENAI_BASE_URL, api_key=settings.OPENAI_API_KEY)
        # MLX server expects the exact HuggingFace repo ID.
        self.model = settings.LLM_MODEL_NAME

    def _build_system_prompt(self) -> str:
        """The full, static system prompt — independent of any user message,
        so callers (e.g. an eval harness computing a prompt-version hash)
        can reconstruct exactly what was sent without duplicating it.

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
1. "intent" MUST be one of the enums (browse, search, recommend, get_game, get_reviews, get_aspects).
2. Understand the strict differences between these tag types -- do not mix them up:
   - Categories: BGG's broad subject/format classification, e.g. Card Game, Wargame, Fantasy, Economic, Trains.
   - Subdomains: BGG's 8 coarse rank/leaderboard types. Valid Subdomains are EXACTLY: Abstract, CGS, Childrens, Family, Party, Strategy, Thematic, War.
   - Themes: Narrow setting/franchise tags, e.g. Zombies, Cthulhu Mythos, Alchemy, Anime / Manga.
   - Mechanics: Gameplay mechanisms, e.g. Worker Placement, Deck Building, Area Control, Dice Rolling.
   - Families: BGG's `family` tag system -- specific, narrow series/groupings, stored as "Group: Value" strings (e.g. "Series: ...", "Crowdfunding: Kickstarter"). Extremely numerous and inconsistently formatted -- only set this if the user names a specific series/family explicitly and you're confident of the exact stored wording; when unsure, leave it unset and prefer categories/subdomains/themes/mechanics instead.
   - Designers / Artists / Publishers: real people or company names credited on the game. Only set these when the user explicitly names a specific person or company -- never guess a name from a genre or vibe.
3. Here are examples of correct parsing:
   - "strategy games" -> subdomains=["Strategy"]
   - "party games" -> subdomains=["Party"]
   - "card games" -> categories=["Card Game"]
   - "games with worker placement" -> mechanics=["Worker Placement"]
   - "zombie games" -> themes=["Zombies"]
   - "games designed by Uwe Rosenberg" -> designers=["Uwe Rosenberg"]
   - "anything published by Days of Wonder" -> publishers=["Days of Wonder"]
4. If the user's request is too ambiguous or missing context, set "needs_clarification" to true and ask a "clarification_question".
5. If "intent" is "get_game" or "recommend" for a specific game, provide "game_name".
6. For "recommend", "recommendation_family" is one of popularity, content, collaborative, or hybrid -- default to hybrid if the user doesn't specify one.
7. Output ONLY valid JSON matching the schema. No markdown wrapping.
"""

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
                temperature=AssistantConfig.TEMPERATURE,
                max_tokens=AssistantConfig.MAX_TOKENS
            )

            raw_content = response.choices[0].message.content or "{}"

            # Strip potential markdown formatting
            raw_content = raw_content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            elif raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()

            try:
                return ParsedIntent.model_validate_json(raw_content)
            except ValidationError as e:
                last_error = e
                continue

        raise last_error
