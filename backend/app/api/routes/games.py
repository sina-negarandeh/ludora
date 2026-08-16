from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel

from app.database.session import get_db
from app.database.models import Game, Review
from app.schemas.game import GameResponse, PaginatedGames, ThemeMetadata, PaginatedReviews
from app.services.game_query_service import GameQueryService

router = APIRouter()

@router.get("/", response_model=PaginatedGames)
def get_games(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("rank"),
    order: str = Query("asc"),
    query: Optional[str] = None,
    categories: Optional[List[str]] = Query(None),
    themes: Optional[List[str]] = Query(None),
    mechanics: Optional[List[str]] = Query(None),
    exact_players: Optional[int] = None,
    min_players: Optional[int] = None,
    max_players: Optional[int] = None,
    min_weight: Optional[float] = None,
    max_weight: Optional[float] = None,
    db: Session = Depends(get_db)
):
    service = GameQueryService(db)
    total, games = service.get_games(
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        order=order,
        query_str=query,
        categories=categories,
        themes=themes,
        mechanics=mechanics,
        exact_players=exact_players,
        min_players=min_players,
        max_players=max_players,
        min_weight=min_weight,
        max_weight=max_weight
    )
    return PaginatedGames(total=total, items=games)

@router.get("/categories", response_model=List[str])
def get_categories(db: Session = Depends(get_db)):
    return GameQueryService(db).get_categories()

@router.get("/themes", response_model=List[ThemeMetadata])
def get_themes(db: Session = Depends(get_db)):
    return GameQueryService(db).get_themes()

@router.get("/mechanics", response_model=List[str])
def get_mechanics(db: Session = Depends(get_db)):
    return GameQueryService(db).get_mechanics()

@router.get("/designers", response_model=List[str])
def get_designers(db: Session = Depends(get_db)):
    return GameQueryService(db).get_designers()

@router.get("/publishers", response_model=List[str])
def get_publishers(db: Session = Depends(get_db)):
    return GameQueryService(db).get_publishers()

@router.get("/{bgg_id}", response_model=GameResponse)
def get_game(bgg_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.bgg_id == bgg_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@router.get("/{bgg_id}/reviews", response_model=PaginatedReviews)
def get_game_reviews(
    bgg_id: int, 
    page: int = Query(1, ge=1), 
    page_size: int = Query(10, ge=1, le=50),
    min_rating: Optional[float] = Query(None),
    max_rating: Optional[float] = Query(None),
    language: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    
    query = db.query(Review).filter(Review.game_id == bgg_id)
    if min_rating is not None:
        query = query.filter(Review.rating >= min_rating)
    if max_rating is not None:
        query = query.filter(Review.rating <= max_rating)
    if language is not None:
        query = query.filter(Review.language == language)
        
    total = query.count()
    
    # We want to show comments first if possible, or order by newest, or rating?
    # Let's order by those with comments first, then by date descending.
    reviews = query.order_by(
        Review.comment.is_(None), 
        Review.created_at.desc().nullslast(), 
        Review.rating.desc().nullslast(), 
        Review.id.desc()
    ).offset(skip).limit(page_size).all()
        
    items = []
    for r in reviews:
        items.append({
            "id": r.id,
            "user": r.user.external_user_id if r.user else "Anonymous",
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at
        })
        
    # Calculate language breakdown across ALL reviews for this game
    all_reviews_count = db.query(Review).filter(Review.game_id == bgg_id).count()
    language_breakdown = {}
    rating_breakdown = {"positive": 0.0, "mixed": 0.0, "negative": 0.0}
    
    if all_reviews_count > 0:
        lang_counts = db.query(
            Review.language, func.count(Review.id)
        ).filter(Review.game_id == bgg_id).group_by(Review.language).all()
        
        for lang, count in lang_counts:
            if lang and lang != 'unknown':
                pct = round((count / all_reviews_count) * 100, 1)
                language_breakdown[lang] = pct
                
        positive_count = db.query(Review).filter(Review.game_id == bgg_id, Review.rating >= 7).count()
        mixed_count = db.query(Review).filter(Review.game_id == bgg_id, Review.rating >= 4, Review.rating < 7).count()
        negative_count = db.query(Review).filter(Review.game_id == bgg_id, Review.rating < 4).count()
        
        rating_breakdown["positive"] = round((positive_count / all_reviews_count) * 100, 1)
        rating_breakdown["mixed"] = round((mixed_count / all_reviews_count) * 100, 1)
        rating_breakdown["negative"] = round((negative_count / all_reviews_count) * 100, 1)
        
    return {
        "total": total, 
        "language_breakdown": language_breakdown, 
        "rating_breakdown": rating_breakdown,
        "items": items
    }

class AspectAggregateResponse(BaseModel):
    aspect: str
    positive_count: int
    negative_count: int
    mixed_count: int
    neutral_count: int
    total_mentions: int
    mean_sentiment: float
    evidence_samples: List[str]

@router.get("/{game_id}/aspects", response_model=List[AspectAggregateResponse])
def get_game_aspects(game_id: int, db: Session = Depends(get_db)):
    from app.database.models import GameAspectAggregate, ReviewAspect
    
    # Get aggregates
    aggregates = db.query(GameAspectAggregate).filter(
        GameAspectAggregate.game_id == game_id,
        GameAspectAggregate.total_mentions >= 1 # Only return if there's data
    ).order_by(GameAspectAggregate.total_mentions.desc()).all()
    
    result = []
    for agg in aggregates:
        # Get top 3 most confident evidence quotes for this aspect
        evidence_records = db.query(ReviewAspect).filter(
            ReviewAspect.game_id == game_id,
            ReviewAspect.aspect == agg.aspect,
            ReviewAspect.evidence.isnot(None)
        ).order_by(ReviewAspect.confidence.desc()).limit(3).all()
        
        samples = [r.evidence for r in evidence_records if r.evidence.strip()]
        
        result.append(AspectAggregateResponse(
            aspect=agg.aspect,
            positive_count=agg.positive_count,
            negative_count=agg.negative_count,
            mixed_count=agg.mixed_count,
            neutral_count=agg.neutral_count,
            total_mentions=agg.total_mentions,
            mean_sentiment=agg.mean_sentiment or 0.0,
            evidence_samples=samples
        ))
        
    return result
