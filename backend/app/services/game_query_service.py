from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Tuple, List, Optional
from app.database.models import Game, Category, Theme, Mechanic, Designer, Publisher

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
        categories: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        mechanics: Optional[List[str]] = None,
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

        # Joins (Multi-select AND matching)
        if categories:
            for cat in categories:
                query = query.filter(Game.categories.any(Category.name == cat))
        if themes:
            for theme in themes:
                query = query.filter(Game.themes.any(Theme.name == theme))
        if mechanics:
            for mech in mechanics:
                query = query.filter(Game.mechanics.any(Mechanic.name == mech))

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

    def get_themes(self) -> List[dict]:
        from app.database.models import GameTheme
        themes = self.db.query(
            Theme.id, 
            Theme.name, 
            func.count(GameTheme.game_id).label("game_count")
        ).join(GameTheme, Theme.id == GameTheme.theme_id)\
         .group_by(Theme.id)\
         .order_by(Theme.name).all()
        
        return [{"id": t.id, "name": t.name, "game_count": t.game_count} for t in themes]
