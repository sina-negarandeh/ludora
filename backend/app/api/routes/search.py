from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.search import SearchQuery, PaginatedSearchResults
from app.services.search_service import SearchService

router = APIRouter()

@router.post("/", response_model=PaginatedSearchResults, summary="Execute Hybrid Search", description="Performs a lexical, semantic, or hybrid search using pgvector and full-text search against the board games dataset.")
def perform_search(
    query: SearchQuery,
    skip: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db)
):
    service = SearchService(db)
    return service.search(query, skip, limit)
