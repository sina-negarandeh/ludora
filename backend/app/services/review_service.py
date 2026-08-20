
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import Review


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def get_game_reviews(
        self,
        bgg_id: int, 
        page: int = 1, 
        page_size: int = 10,
        min_rating: float | None = None,
        max_rating: float | None = None,
        language: str | None = None
    ):
        skip = (page - 1) * page_size
        
        query = self.db.query(Review).filter(Review.game_id == bgg_id)
        if min_rating is not None:
            query = query.filter(Review.rating >= min_rating)
        if max_rating is not None:
            query = query.filter(Review.rating <= max_rating)
        if language is not None:
            query = query.filter(Review.language == language)
            
        total = query.count()
        
        reviews = query.order_by(
            Review.comment.is_(None),
            Review.rating.desc().nullslast(),
            Review.id.desc()
        ).offset(skip).limit(page_size).all()

        items = []
        for r in reviews:
            items.append({
                "id": r.id,
                "user": r.user.external_user_id if r.user else "Anonymous",
                "rating": r.rating,
                "comment": r.comment
            })
            
        return total, items

    def get_game_review_stats(self, bgg_id: int):
        all_reviews_count = self.db.query(Review).filter(Review.game_id == bgg_id).count()
        language_breakdown = {}
        rating_breakdown = {"positive": 0.0, "mixed": 0.0, "negative": 0.0}
        
        if all_reviews_count > 0:
            lang_counts = self.db.query(
                Review.language, func.count(Review.id)
            ).filter(Review.game_id == bgg_id).group_by(Review.language).all()
            
            for lang, count in lang_counts:
                if lang and lang != 'unknown':
                    pct = round((count / all_reviews_count) * 100, 1)
                    language_breakdown[lang] = pct
                    
            positive_count = self.db.query(Review).filter(Review.game_id == bgg_id, Review.rating >= 7).count()
            mixed_count = self.db.query(Review).filter(Review.game_id == bgg_id, Review.rating >= 4, Review.rating < 7).count()
            negative_count = self.db.query(Review).filter(Review.game_id == bgg_id, Review.rating < 4).count()
            
            rating_breakdown["positive"] = round((positive_count / all_reviews_count) * 100, 1)
            rating_breakdown["mixed"] = round((mixed_count / all_reviews_count) * 100, 1)
            rating_breakdown["negative"] = round((negative_count / all_reviews_count) * 100, 1)
            
        return language_breakdown, rating_breakdown
