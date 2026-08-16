import json
from app.schemas.assistant import ParsedIntent
from app.services.assistant_service import AssistantService
import traceback

def test_schema_dump():
    schema = ParsedIntent.model_json_schema()
    print("Schema dumped successfully. First 500 chars:", json.dumps(schema)[:500])

def test_parsing():
    service = AssistantService()
    try:
        res = service.parse_query("Find medium complexity economic games for 2-4 players")
        print("Success! Parsed Intent:")
        print(res.model_dump_json(indent=2))
    except Exception as e:
        print("Failed to call LLM (expected if no local server running):", e)
        traceback.print_exc()

if __name__ == "__main__":
    test_schema_dump()
    print("-" * 40)
    test_parsing()
