"""Infra-free smoke tests: no live DB, no local LLM server. Catches a
broken import, a broken route/schema definition, or a startup-time error
without needing anything CI doesn't have. Deeper coverage (the real
gap tracked in docs/roadmap.md) needs a DB fixture and belongs in its
own test module once that exists.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_generates():
    # Exercises every route/response-model definition without a live DB --
    # a broken Pydantic schema or route signature fails this immediately.
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/games/" in schema["paths"]
    assert "/api/assistant/chat" in schema["paths"]
