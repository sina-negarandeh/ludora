from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Tuple, List, Optional
from app.database.models import Game, Category, Theme, Mechanic, Designer, Publisher

class GameService:
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
        max_weight: Optional[float] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None
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
            
        if min_year is not None:
            query = query.filter(Game.year_published >= min_year)
        if max_year is not None:
            query = query.filter(Game.year_published <= max_year)

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

    def get_game(self, bgg_id: int) -> Optional[Game]:
        return self.db.query(Game).filter(Game.bgg_id == bgg_id).first()
        
    def compare_games(self, game_ids: List[int]) -> List[Game]:
        games = self.db.query(Game).filter(Game.bgg_id.in_(game_ids)).all()
        # Ensure the order matches the requested game_ids
        game_map = {g.bgg_id: g for g in games}
        return [game_map[gid] for gid in game_ids if gid in game_map]
