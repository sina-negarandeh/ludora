import json
from openai import OpenAI
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
        can reconstruct exactly what was sent without duplicating it."""
        schema_json = ParsedIntent.model_json_schema()
        return f"""You are the Ludora Assistant, an expert in board games.
Your job is to parse the user's natural language request into a strictly structured JSON intent object.
DO NOT answer the user's question. Just output the JSON.

Here is the JSON Schema you MUST follow:
{json.dumps(schema_json, indent=2)}

Important Rules:
1. "intent" MUST be one of the enums (browse, search, compare, recommend, get_game, get_reviews, get_aspects).
2. Understand the strict difference between Categories, Themes, and Mechanics:
   - Categories: Broad classifications. Valid Categories are EXACTLY: Abstract, CGS, Childrens, Family, Party, Strategy, Thematic, War.
   - Themes: Subject/topic (e.g. Economic, Trains, Science Fiction, Medieval, Industry / Manufacturing).
   - Mechanics: Gameplay mechanisms (e.g. Worker Placement, Deck Building, Area Control, Dice Rolling).
3. Here are examples of correct parsing:
   - "strategy games" -> categories=["Strategy"]
   - "economic games" -> themes=["Economic"]
   - "games with worker placement" -> mechanics=["Worker Placement"]
   - "train games" -> themes=["Trains"]
4. If the user's request is too ambiguous or missing context, set "needs_clarification" to true and ask a "clarification_question".
5. If "intent" is "compare", provide "game_names" as a list of strings.
6. If "intent" is "get_game" or "recommend" for a specific game, provide "game_name".
7. Output ONLY valid JSON matching the schema. No markdown wrapping.
"""

    def parse_query(self, user_message: str) -> ParsedIntent:
        system_prompt = self._build_system_prompt()

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
        
        raw_content = response.choices[0].message.content
        if not raw_content:
            raw_content = "{}"
            
        # Strip potential markdown formatting
        raw_content = raw_content.strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        elif raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
            
        raw_content = raw_content.strip()
        print(f"DEBUG: Raw content from LLM: {raw_content}")
        return ParsedIntent.model_validate_json(raw_content)
