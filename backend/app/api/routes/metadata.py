from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.schemas.game import ThemeMetadata, FamilyGroupMetadata, SubdomainMetadata
from app.services.metadata_service import MetadataService

router = APIRouter(tags=["metadata"])

@router.get("/subdomains", response_model=List[SubdomainMetadata], summary="Get Subdomains", description="Retrieve BGG's rank/leaderboard classifications (Strategy, Family, Party, etc.) — not content categories, see /categories for those — along with how many ranked games fall under each.")
def get_subdomains(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_subdomains(search=search, limit=limit)

@router.get("/categories", response_model=List[str], summary="Get Categories", description="Retrieve BGG's real Category tags (e.g. Economic, Fantasy, Card Game).")
def get_categories(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_categories(search=search, limit=limit)

@router.get("/themes", response_model=List[ThemeMetadata], summary="Get Themes", description="Retrieve BGG Family 'Theme:' tags (narrow setting/franchise tags, distinct from Category) along with their usage counts.")
def get_themes(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_themes(search=search, limit=limit)

@router.get("/families", response_model=List[FamilyGroupMetadata], summary="Get Families", description="Retrieve BGG Family tags (boardgamefamily, all 72 namespaces — e.g. Animals, Mechanism, Theme, Crowdfunding), grouped by namespace with per-value usage counts.")
def get_families(search: str = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_families(search=search)

@router.get("/mechanics", response_model=List[str], summary="Get Mechanics", description="Retrieve all game mechanics.")
def get_mechanics(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_mechanics(search=search, limit=limit)

@router.get("/designers", response_model=List[str], summary="Get Designers", description="Retrieve all game designers.")
def get_designers(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_designers(search=search, limit=limit)

@router.get("/publishers", response_model=List[str], summary="Get Publishers", description="Retrieve all game publishers.")
def get_publishers(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_publishers(search=search, limit=limit)

@router.get("/artists", response_model=List[str], summary="Get Artists", description="Retrieve all game artists.")
def get_artists(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_artists(search=search, limit=limit)
