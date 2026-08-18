import hashlib
import time

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.ml_config import AssistantConfig
from app.core.mlflow_utils import tracked_run, write_results_json
from app.services.assistant_service import AssistantService
import mlflow

client = TestClient(app)

# Bump this whenever TEST_CASES changes meaningfully (new/changed queries or
# expectations) — an LLM-prompted feature's "eval dataset" is this fixed set
# of cases, and its version should move independently of the code version.
EVAL_DATASET_VERSION = "smoke_v1"

# Each case's "expect" is a minimal, honest check — not a semantic-quality
# benchmark. It confirms the pipeline routes to the right intent (and, for
# the ambiguity case, actually asks for clarification) so a regression in
# intent parsing shows up as a metric drop over time instead of silently
# passing whatever the LLM happens to return.
TEST_CASES = [
    {"query": "Compare Brass Birmingham and Terraforming Mars", "expect_intent": "compare", "expect_clarification": False},
    {"query": "Compare Catan with the 1995 edition", "expect_intent": None, "expect_clarification": True},
    {"query": "Show me economic games for 2-4 players", "expect_intent": None, "expect_clarification": False},
]

def test_chat():
    # The system prompt is static regardless of user message (see
    # AssistantService._build_system_prompt) — hash it once here rather than
    # re-deriving it per request, since this is what actually determines
    # behavior for an LLM-prompted feature (there's no trained model/weights
    # to version, the prompt *is* the thing being versioned).
    prompt_hash = hashlib.sha256(AssistantService()._build_system_prompt().encode()).hexdigest()[:12]

    results = []

    for case in TEST_CASES:
        q = case["query"]
        print(f"\n--- Testing Query: {q} ---")
        start = time.time()
        response = client.post("/api/assistant/chat", json={"message": q})
        latency_seconds = time.time() - start

        passed = False
        intent = None
        needs_clarification = None

        if response.status_code == 200:
            data = response.json()
            parsed_intent = data.get("parsed_intent", {})
            intent = parsed_intent.get("intent")
            needs_clarification = bool(parsed_intent.get("needs_clarification"))

            intent_ok = case["expect_intent"] is None or intent == case["expect_intent"]
            clarification_ok = needs_clarification == case["expect_clarification"]
            passed = intent_ok and clarification_ok

            print(f"Intent: {intent}")
            if needs_clarification:
                print(f"CLARIFICATION REQUIRED: {parsed_intent.get('clarification_question')}")
                if "ambiguous_matches" in data.get("data", {}):
                    print("Matches provided for user selection:")
                    for m in data["data"]["ambiguous_matches"]:
                        print(f" - [{m['id']}] {m['name']} ({m['year']})")
            else:
                print("Data Keys returned:", list(data.get("data", {}).keys()))
                if "games" in data.get("data", {}):
                    print("Games:", [g.get("name") for g in data["data"]["games"]][:3])
                if "results" in data.get("data", {}):
                    print("Results:", [r.get("game", {}).get("name") for r in data["data"]["results"]][:3])
        else:
            print(f"Error: {response.status_code} - {response.text}")

        print(f"PASS: {passed} (latency: {latency_seconds:.2f}s)")
        results.append({
            "query": q,
            "passed": passed,
            "intent": intent,
            "needs_clarification": needs_clarification,
            "status_code": response.status_code,
            "latency_seconds": round(latency_seconds, 3),
        })

    pass_rate = sum(r["passed"] for r in results) / len(results)
    latencies = [r["latency_seconds"] for r in results]
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2]
    p95_idx = min(len(latencies_sorted) - 1, int(len(latencies_sorted) * 0.95))
    p95 = latencies_sorted[p95_idx]
    print(f"\n--- Pass rate: {pass_rate:.2%} ({sum(r['passed'] for r in results)}/{len(results)}) ---")

    with tracked_run("llm/intent_parsing", run_name="smoke_test"):
        mlflow.log_params({
            "n_queries": len(TEST_CASES),
            "eval_dataset_version": EVAL_DATASET_VERSION,
            "llm_model": settings.LLM_MODEL_NAME,
            "temperature": AssistantConfig.TEMPERATURE,
            "prompt_hash": prompt_hash,
        })
        mlflow.log_metrics({
            "pass_rate": pass_rate,
            "latency_p50_seconds": round(p50, 3),
            "latency_p95_seconds": round(p95, 3),
            **{f"query_{i}_passed": int(r["passed"]) for i, r in enumerate(results)},
        })
    write_results_json("assistant_intent_eval", {
        "eval_dataset_version": EVAL_DATASET_VERSION,
        "prompt_hash": prompt_hash,
        "pass_rate": pass_rate,
        "results": results,
    })

    return results

if __name__ == "__main__":
    test_chat()
