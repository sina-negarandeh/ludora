from sqlalchemy.orm import Session
from app.services.search_service import SearchService
from app.schemas.search import SearchQuery, SearchMode
from app.schemas.game_query import GameFilter
from app.database.models import Category, Theme, Mechanic
from typing import List, Dict, Any

class EntityNotFoundError(Exception):
    def __init__(self, query: str):
        self.query = query
        super().__init__(f"Could not resolve any game or tag for query: '{query}'")

class AmbiguousEntityError(Exception):
    def __init__(self, query: str, matches: List[Dict[str, Any]]):
        self.query = query
        self.matches = matches
        super().__init__(f"Ambiguous match for query: '{query}'. Provide matches for clarification.")

class EntityResolver:
    _categories_cache: Dict[str, str] = {}
    _themes_cache: Dict[str, str] = {}
    _mechanics_cache: Dict[str, str] = {}
    _caches_loaded: bool = False

    def __init__(self, db: Session):
        self.db = db
        self.search_service = SearchService(db)
        if not EntityResolver._caches_loaded:
            self._load_caches()

    def _normalize(self, tag: str) -> str:
        return tag.strip().lower()

    def _load_caches(self):
        for c in self.db.query(Category).all():
            self._categories_cache[self._normalize(c.name)] = c.name
        for t in self.db.query(Theme).all():
            self._themes_cache[self._normalize(t.name)] = t.name
        for m in self.db.query(Mechanic).all():
            self._mechanics_cache[self._normalize(m.name)] = m.name
        EntityResolver._caches_loaded = True

    def resolve_filters(self, filters: GameFilter) -> GameFilter:
        all_tags = []
        if filters.categories: all_tags.extend(filters.categories)
        if filters.themes: all_tags.extend(filters.themes)
        if filters.mechanics: all_tags.extend(filters.mechanics)

        resolved_cats = []
        resolved_themes = []
        resolved_mechs = []

        for tag in all_tags:
            norm = self._normalize(tag)
            
            is_cat = norm in self._categories_cache
            is_theme = norm in self._themes_cache
            is_mech = norm in self._mechanics_cache

            matches = sum([is_cat, is_theme, is_mech])

            if matches == 0:
                raise EntityNotFoundError(tag)
            
            if matches > 1:
                possible_types = []
                if is_cat: possible_types.append("category")
                if is_theme: possible_types.append("theme")
                if is_mech: possible_types.append("mechanic")
                
                raise AmbiguousEntityError(query=tag, matches=[{"id": f"{tag} ({t})", "name": f"{tag} ({t})", "year": t} for t in possible_types])

            if is_cat:
                resolved_cats.append(self._categories_cache[norm])
            elif is_theme:
                resolved_themes.append(self._themes_cache[norm])
            elif is_mech:
                resolved_mechs.append(self._mechanics_cache[norm])

        new_filters = filters.model_copy()
        new_filters.categories = resolved_cats if resolved_cats else None
        new_filters.themes = resolved_themes if resolved_themes else None
        new_filters.mechanics = resolved_mechs if resolved_mechs else None

        return new_filters

    def resolve_game(self, query: str) -> int:
        sq = SearchQuery(q=query, mode=SearchMode.LEXICAL)
        results = self.search_service.search(sq, skip=0, limit=5)
        
        if results.total == 0:
            raise EntityNotFoundError(query)

        items = results.items
        exact_matches = [r for r in items if r.game.name.lower() == query.lower()]
        if len(exact_matches) == 1:
            return exact_matches[0].game.bgg_id

        if len(items) == 1:
            return items[0].game.bgg_id

        matches = []
        for r in items:
            matches.append({
                "id": r.game.bgg_id,
                "name": r.game.name,
                "year": r.game.year_published
            })
            
        raise AmbiguousEntityError(query=query, matches=matches)

    def resolve_games(self, queries: List[str]) -> List[int]:
        ids = []
        for q in queries:
            ids.append(self.resolve_game(q))
        return ids
