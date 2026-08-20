import time

import httpx

from app.services.assistant_service import AssistantService


def wait_for_server():
    print("Waiting for MLX server to boot on localhost:8080...")
    while True:
        try:
            res = httpx.get("http://localhost:8080/v1/models", timeout=2)
            if res.status_code == 200:
                print("Server is UP!")
                break
        except httpx.RequestError:
            pass
        time.sleep(5)

def run_test():
    service = AssistantService()
    query = "Find medium complexity economic games for 2-4 players"
    print(f"Testing Query: {query}")
    try:
        res = service.parse_query(query)
        print("\nSuccess! Parsed Intent:")
        print(res.model_dump_json(indent=2))
    except Exception as e:
        print("Failed to parse:", e)

if __name__ == "__main__":
    run_test()
