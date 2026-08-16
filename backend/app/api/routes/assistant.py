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

@router.post("/parse", response_model=ParsedIntent)
def parse_intent(request: ParseRequest):
    service = AssistantService()
    try:
        parsed = service.parse_query(request.message)
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=AssistantResponse)
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
