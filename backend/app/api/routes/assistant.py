from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
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

@router.post("/parse", response_model=ParsedIntent, summary="Parse Natural Language Intent", description="Uses a local MLX LLM to parse a natural language query into structured JSON intent (e.g., 'search', 'compare', 'recommend').")
def parse_intent(request: ParseRequest):
    service = AssistantService()
    try:
        parsed = service.parse_query(request.message)
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=AssistantResponse, summary="Execute Assistant Chat", description="Parses the user intent and automatically routes it to the correct backend service (e.g. executing a semantic search, fetching recommendations, or comparing games). Returns a UI-ready response.")
def chat_endpoint(request: ParseRequest, db: Session = Depends(get_db)):
    service = AssistantService()
    orchestrator = AssistantOrchestrator(db)
    
    try:
        # 1. Parse intent
        parsed = service.parse_query(request.message)
        
        # 2. Execute intent
        response = orchestrator.execute(parsed)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
