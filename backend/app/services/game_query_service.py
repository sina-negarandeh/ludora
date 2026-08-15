from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Tuple, List, Optional
from app.database.models import Game, Category, Mechanic, Designer, Publisher

class GameQueryService:
    def __init__(self, db: Session):
        self.db = db

    def get_games(
        self, 
        skip: int = 0, 
        limit: int = 50, 
        sort_by: str = "rank", 
        order: str = "asc",
        query_str: Optional[str] = None,
        category: Optional[str] = None,
        mechanic: Optional[str] = None,
        exact_players: Optional[int] = None,
        min_players: Optional[int] = None,
        max_players: Optional[int] = None,
        min_weight: Optional[float] = None,
        max_weight: Optional[float] = None
    ) -> Tuple[int, List[Game]]:
        
        query = self.db.query(Game)

        # Filters
        if query_str:
            query = query.filter(Game.name.ilike(f"%{query_str}%"))
        
        if exact_players is not None:
            query = query.filter(Game.min_players <= exact_players, Game.max_players >= exact_players)
            
        if min_players is not None:
            query = query.filter(Game.min_players >= min_players)
        if max_players is not None:
            query = query.filter(Game.max_players <= max_players)
            
        if min_weight is not None:
            query = query.filter(Game.game_weight >= min_weight)
        if max_weight is not None:
            query = query.filter(Game.game_weight <= max_weight)

        # Joins
        if category:
            query = query.join(Game.categories).filter(Category.name == category)
        if mechanic:
            query = query.join(Game.mechanics).filter(Mechanic.name == mechanic)

        # Count total after filters but before pagination
        # Use query.with_entities() to efficiently count without fetching full objects
        total = query.with_entities(func.count(Game.bgg_id)).scalar()

        # Sorting
        sort_column = getattr(Game, 'rank')
        if sort_by == 'rating':
            sort_column = getattr(Game, 'avg_rating')
        elif sort_by == 'year':
            sort_column = getattr(Game, 'year_published')
        elif sort_by == 'complexity':
            sort_column = getattr(Game, 'game_weight')
        elif sort_by == 'name':
            sort_column = getattr(Game, 'name')
            
        if order == 'desc':
            query = query.order_by(sort_column.desc().nulls_last())
        else:
            query = query.order_by(sort_column.asc().nulls_last())

        # Pagination
        games = query.offset(skip).limit(limit).all()

        return total, games

    def get_categories(self) -> List[str]:
        return [c[0] for c in self.db.query(Category.name).order_by(Category.name).all()]

    def get_mechanics(self) -> List[str]:
        return [m[0] for m in self.db.query(Mechanic.name).order_by(Mechanic.name).all()]

    def get_designers(self) -> List[str]:
        return [d[0] for d in self.db.query(Designer.name).order_by(Designer.name).all()]

    def get_publishers(self) -> List[str]:
        return [p[0] for p in self.db.query(Publisher.name).order_by(Publisher.name).all()]
