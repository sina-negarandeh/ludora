from sqlalchemy.orm import Session
from typing import List
from app.database.models import GameAspectAggregate, ReviewAspect
from pydantic import BaseModel

class AspectAggregateResponse(BaseModel):
    aspect: str
    positive_count: int
    negative_count: int
    mixed_count: int
    neutral_count: int
    total_mentions: int
    mean_sentiment: float
    evidence_samples: List[str]

class AspectService:
    def __init__(self, db: Session):
        self.db = db

    def get_game_aspects(self, game_id: int) -> List[AspectAggregateResponse]:
        aggregates = self.db.query(GameAspectAggregate).filter(
            GameAspectAggregate.game_id == game_id,
            GameAspectAggregate.total_mentions >= 5
        ).order_by(GameAspectAggregate.total_mentions.desc()).all()
        
        result = []
        for agg in aggregates:
            evidence_records = self.db.query(ReviewAspect).filter(
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
