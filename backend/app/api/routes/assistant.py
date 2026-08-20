import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ValidationError
from typing import Optional
from sqlalchemy.orm import Session
from app.schemas.assistant import ParsedIntent, AssistantResponse
from app.services.assistant_service import AssistantService
from app.services.assistant_orchestrator import AssistantOrchestrator
from app.database.session import get_db

router = APIRouter()

class ParseRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

# 502, not 500, for a ValidationError or JSONDecodeError specifically:
# both mean the LLM (an upstream dependency) returned something that
# didn't match the expected schema even after retries -- distinct from a
# bug in this app's own code. Neither branch leaks str(e) to the client
# -- a raw Pydantic validation message or SQLAlchemy error isn't
# something an API consumer should see.
_LLM_PARSE_FAILURE_MESSAGE = "The assistant returned a response that couldn't be parsed. Please try rephrasing your request."
_UNEXPECTED_ERROR_MESSAGE = "Something went wrong while processing your request."

@router.post("/parse", response_model=ParsedIntent, summary="Parse Natural Language Intent", description="Uses a local MLX LLM to parse a natural language query into structured JSON intent (e.g., 'search', 'recommend').")
def parse_intent(request: ParseRequest):
    service = AssistantService()
    try:
        return service.parse_query(request.message)
    except (ValidationError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail=_LLM_PARSE_FAILURE_MESSAGE)
    except Exception:
        raise HTTPException(status_code=500, detail=_UNEXPECTED_ERROR_MESSAGE)

@router.post("/chat", response_model=AssistantResponse, summary="Execute Assistant Chat", description="Parses the user request into one or more steps (most requests are a single step) and automatically routes each to the correct backend service (e.g. executing a semantic search, fetching recommendations, or looking up a game), chaining a step's result into a later dependent step when needed. Returns a UI-ready response.")
def chat_endpoint(request: ParseRequest, db: Session = Depends(get_db)):
    service = AssistantService()
    orchestrator = AssistantOrchestrator(db)

    try:
        plan = service.parse_plan(request.message)
        return orchestrator.execute_plan(plan)
    except (ValidationError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail=_LLM_PARSE_FAILURE_MESSAGE)
    except Exception:
        raise HTTPException(status_code=500, detail=_UNEXPECTED_ERROR_MESSAGE)
