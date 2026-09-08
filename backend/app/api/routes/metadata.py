
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.distribution import MetricDistribution
from app.schemas.game import FamilyGroupMetadata, SubdomainMetadata, ThemeMetadata
from app.services.distribution_service import (
    DistributionsUnavailableError,
    load_distributions,
)
from app.services.metadata_service import MetadataService

router = APIRouter(tags=["metadata"])

@router.get("/subdomains", response_model=list[SubdomainMetadata], summary="Get Subdomains", description="Retrieve BGG's rank/leaderboard classifications (Strategy, Family, Party, etc.) — not content categories, see /categories for those — along with how many ranked games fall under each.")
def get_subdomains(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_subdomains(search=search, limit=limit)

@router.get("/categories", response_model=list[str], summary="Get Categories", description="Retrieve BGG's real Category tags (e.g. Economic, Fantasy, Card Game).")
def get_categories(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_categories(search=search, limit=limit)

@router.get("/themes", response_model=list[ThemeMetadata], summary="Get Themes", description="Retrieve BGG Family 'Theme:' tags (narrow setting/franchise tags, distinct from Category) along with their usage counts.")
def get_themes(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_themes(search=search, limit=limit)

@router.get("/families", response_model=list[FamilyGroupMetadata], summary="Get Families", description="Retrieve BGG Family tags (boardgamefamily, all 72 namespaces — e.g. Animals, Mechanism, Theme, Crowdfunding), grouped by namespace with per-value usage counts.")
def get_families(search: str = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_families(search=search)

@router.get("/mechanics", response_model=list[str], summary="Get Mechanics", description="Retrieve all game mechanics.")
def get_mechanics(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_mechanics(search=search, limit=limit)

@router.get("/designers", response_model=list[str], summary="Get Designers", description="Retrieve all game designers.")
def get_designers(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_designers(search=search, limit=limit)

@router.get("/publishers", response_model=list[str], summary="Get Publishers", description="Retrieve all game publishers.")
def get_publishers(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_publishers(search=search, limit=limit)

@router.get("/artists", response_model=list[str], summary="Get Artists", description="Retrieve all game artists.")
def get_artists(search: str = Query(None), limit: int = Query(None), db: Session = Depends(get_db)):
    return MetadataService(db).get_artists(search=search, limit=limit)

@router.get("/distributions", response_model=dict[str, dict[str, MetricDistribution]], summary="Get Metric Distributions", description="Retrieve precomputed kernel density curves for Complexity, Playtime, Players, Min Players and Min Age, keyed by subdomain plus an 'Overall' group. Produced offline by scripts/generate_distributions.py from the raw Kaggle CSV, so this reads a static artifact rather than the database.")
def get_distributions():
    try:
        # The vetted bytes, served as-is. `response_model` stays for the
        # OpenAPI schema; the shape is enforced once at read time instead of
        # re-validated on every request.
        return Response(content=load_distributions(), media_type="application/json")
    except DistributionsUnavailableError as exc:
        # A 503 rather than a 500: the API is fine, the offline artifact is
        # not, and the fix is to run the pipeline rather than to debug this.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
