from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat():
    queries = [
        "Compare Brass Birmingham and Terraforming Mars",
        "Compare Catan with the 1995 edition", # Should trigger ambiguity
        "Show me economic games for 2-4 players"
    ]
    
    for q in queries:
        print(f"\n--- Testing Query: {q} ---")
        response = client.post("/api/assistant/chat", json={"message": q})
        if response.status_code == 200:
            data = response.json()
            intent = data.get("parsed_intent", {})
            print(f"Intent: {intent.get('intent')}")
            if intent.get("needs_clarification"):
                print(f"CLARIFICATION REQUIRED: {intent.get('clarification_question')}")
                if "ambiguous_matches" in data.get("data", {}):
                    print("Matches provided for user selection:")
                    for m in data["data"]["ambiguous_matches"]:
                        print(f" - [{m['id']}] {m['name']} ({m['year']})")
            else:
                print("Data Keys returned:", list(data.get("data", {}).keys()))
                # Try to print some game names if available
                if "games" in data.get("data", {}):
                    print("Games:", [g.get("name") for g in data["data"]["games"]][:3])
                if "results" in data.get("data", {}):
                    print("Results:", [r.get("game", {}).get("name") for r in data["data"]["results"]][:3])
        else:
            print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_chat()
