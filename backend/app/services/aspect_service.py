# Known limitation, tracked in docs/roadmap.md: app/database/models.py uses
# SQLAlchemy's legacy Column(...) declarative style, not 2.0's typed
# Mapped[]/mapped_column(). Pyright can't tell an instance attribute like
# `game.rank` apart from the class-level Column descriptor, so it reports
# every read of a model attribute as Column[X] instead of X. These are
# false positives, not real bugs -- confirmed by direct behavior at
# runtime throughout this session -- and this file is unusually dense with
# them since it's mostly model-attribute plumbing. Suppressed here rather
# than project-wide so a real reportArgumentType/reportGeneralTypeIssues
# bug elsewhere still surfaces.
# pyright: reportArgumentType=false, reportGeneralTypeIssues=false

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.ml_config import ABSAConfig
from app.database.models import GameAspectAggregate, ReviewAspect


class EvidenceSample(BaseModel):
    sentiment: str
    text: str

class AspectAggregateResponse(BaseModel):
    aspect: str
    positive_count: int
    negative_count: int
    mixed_count: int
    neutral_count: int
    total_mentions: int
    mean_sentiment: float
    evidence_samples: list[EvidenceSample]

class AspectService:
    def __init__(self, db: Session):
        self.db = db

    def _top_evidence(self, game_id: int, aspect: str, sentiment: str, limit: int = 1) -> list[EvidenceSample]:
        rows = self.db.query(ReviewAspect).filter(
            ReviewAspect.game_id == game_id,
            ReviewAspect.aspect == aspect,
            ReviewAspect.sentiment == sentiment,
            ReviewAspect.evidence.isnot(None)
        ).order_by(ReviewAspect.confidence.desc()).limit(limit).all()
        return [EvidenceSample(sentiment=sentiment, text=r.evidence) for r in rows if r.evidence.strip()]

    def get_game_aspects(self, game_id: int) -> list[AspectAggregateResponse]:
        aggregates = self.db.query(GameAspectAggregate).filter(
            GameAspectAggregate.game_id == game_id,
            GameAspectAggregate.total_mentions >= ABSAConfig.MIN_MENTIONS_FOR_DISPLAY
        ).order_by(GameAspectAggregate.total_mentions.desc()).all()

        result = []
        for agg in aggregates:
            total = max(1, agg.total_mentions)
            pos_ratio = agg.positive_count / total
            neg_ratio = agg.negative_count / total
            dominance = ABSAConfig.CARD_DOMINANCE_THRESHOLD

            if pos_ratio >= dominance:
                # Confident Positive: single dominant bucket, matches the
                # card's ring/label/icon exactly.
                samples = self._top_evidence(game_id, agg.aspect, "positive", limit=3)
            elif neg_ratio >= dominance:
                samples = self._top_evidence(game_id, agg.aspect, "negative", limit=3)
            else:
                # Mixed: neither side is confidently dominant, so a single
                # quote from an arbitrary near-tied bucket wouldn't explain
                # *why* it's mixed. Show one positive + one negative quote
                # instead -- the actual reason the card reads as split.
                # Falls back to neutral quotes when one side has too little
                # evidence to pair (e.g. a genuinely neutral-dominant
                # aspect), so the card never comes up empty.
                samples = self._top_evidence(game_id, agg.aspect, "positive", limit=1)
                samples += self._top_evidence(game_id, agg.aspect, "negative", limit=1)
                if len(samples) < 2:
                    samples += self._top_evidence(game_id, agg.aspect, "neutral", limit=2 - len(samples))

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
