from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pydantic_ai.exceptions import AgentRunError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.assistant import AssistantResponse, ParsedIntent
from app.services.assistant_orchestrator import AssistantOrchestrator
from app.services.assistant_service import AssistantService

router = APIRouter()

class ParseRequest(BaseModel):
    message: str
    conversation_id: str | None = None

# 502, not 500, for AgentRunError specifically: it is PydanticAI's base
# class for every way the model itself can fail us -- output that still
# didn't match the schema after retries (UnexpectedModelBehavior), or
# the LLM server being unreachable or erroring (ModelHTTPError) -- all
# of which are an upstream dependency's fault, distinct from a bug in
# this app's own code. Catching the base class rather than the leaves
# means a new PydanticAI failure mode lands on 502 too, instead of
# silently falling through to the 500 below. Neither branch leaks
# str(e) to the client -- a raw model error or SQLAlchemy message isn't
# something an API consumer should see.
_LLM_PARSE_FAILURE_MESSAGE = "The assistant returned a response that couldn't be parsed. Please try rephrasing your request."
_UNEXPECTED_ERROR_MESSAGE = "Something went wrong while processing your request."

@router.post("/parse", response_model=ParsedIntent, summary="Parse Natural Language Intent", description="Uses a local MLX LLM to parse a natural language query into structured JSON intent (e.g., 'search', 'recommend').")
def parse_intent(request: ParseRequest):
    service = AssistantService()
    try:
        return service.parse_query(request.message)
    except AgentRunError:
        raise HTTPException(status_code=502, detail=_LLM_PARSE_FAILURE_MESSAGE) from None
    except Exception:
        raise HTTPException(status_code=500, detail=_UNEXPECTED_ERROR_MESSAGE) from None

@router.post("/chat", response_model=AssistantResponse, summary="Execute Assistant Chat", description="Parses the user request into one or more steps (most requests are a single step) and automatically routes each to the correct backend service (e.g. executing a semantic search, fetching recommendations, or looking up a game), chaining a step's result into a later dependent step when needed. Returns a UI-ready response.")
def chat_endpoint(request: ParseRequest, db: Session = Depends(get_db)):
    service = AssistantService()
    orchestrator = AssistantOrchestrator(db)

    try:
        plan = service.parse_plan(request.message)
        return orchestrator.execute_plan(plan)
    except AgentRunError:
        raise HTTPException(status_code=502, detail=_LLM_PARSE_FAILURE_MESSAGE) from None
    except Exception:
        raise HTTPException(status_code=500, detail=_UNEXPECTED_ERROR_MESSAGE) from None
