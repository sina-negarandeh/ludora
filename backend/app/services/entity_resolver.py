from sqlalchemy.orm import Session
from app.services.search_service import SearchService
from app.schemas.search import SearchQuery, SearchMode
from app.schemas.game_query import GameFilter
from app.database.models import Category, Theme, Mechanic, Subdomain, Subfamily, Designer, Artist, Publisher
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
    # Content/taxonomy tags: conceptually disjoint in practice (a string is
    # essentially never legitimately both a category and a mechanic), so
    # resolve_filters cross-checks each one against every cache here --
    # that lets a value the LLM put under the wrong field (e.g. a subdomain
    # value under "categories") still resolve correctly, and flags a
    # genuine cross-type collision as ambiguous.
    _CONTENT_TAG_TYPES = {
        "categories": ("category", Category),
        "themes": ("theme", Theme),
        "mechanics": ("mechanic", Mechanic),
        "subdomains": ("subdomain", Subdomain),
        "families": ("family", Subfamily),
    }
    # Credited-entity tags: real people/companies can genuinely hold more
    # than one role -- e.g. Uwe Rosenberg is a real, legitimate entry in
    # both `designers` and `artists` (confirmed against the DB; not a
    # data error). Cross-checking these the same way as the content tags
    # above would flag that as a false ambiguity even though the user's
    # phrasing ("designed by") and the LLM's field placement already
    # disambiguated it -- so these resolve only within their own field's
    # cache, never cross-checked against each other or the content tags.
    _CREDIT_TAG_TYPES = {
        "designers": ("designer", Designer),
        "artists": ("artist", Artist),
        "publishers": ("publisher", Publisher),
    }
    _ALL_TAG_TYPES = {**_CONTENT_TAG_TYPES, **_CREDIT_TAG_TYPES}

    _caches: Dict[str, Dict[str, str]] = {}
    _caches_loaded: bool = False

    def __init__(self, db: Session):
        self.db = db
        self.search_service = SearchService(db)
        if not EntityResolver._caches_loaded:
            self._load_caches()

    def _normalize(self, tag: str) -> str:
        return tag.strip().lower()

    def _load_caches(self):
        for _field_name, (label, model) in self._ALL_TAG_TYPES.items():
            cache = {}
            for row in self.db.query(model).all():
                cache[self._normalize(row.name)] = row.name
            EntityResolver._caches[label] = cache
        EntityResolver._caches_loaded = True

    def resolve_filters(self, filters: GameFilter) -> GameFilter:
        new_filters = filters.model_copy()

        for field_name, (label, _) in self._CREDIT_TAG_TYPES.items():
            values = getattr(filters, field_name)
            if not values:
                continue
            resolved = []
            for tag in values:
                norm = self._normalize(tag)
                if norm not in self._caches[label]:
                    raise EntityNotFoundError(tag)
                resolved.append(self._caches[label][norm])
            setattr(new_filters, field_name, resolved)

        all_content_tags = []
        for field_name in self._CONTENT_TAG_TYPES:
            values = getattr(filters, field_name)
            if values:
                all_content_tags.extend(values)

        resolved_content: Dict[str, list] = {field_name: [] for field_name in self._CONTENT_TAG_TYPES}

        for tag in all_content_tags:
            norm = self._normalize(tag)
            hit_fields = [fn for fn, (label, _) in self._CONTENT_TAG_TYPES.items() if norm in self._caches[label]]

            if not hit_fields:
                raise EntityNotFoundError(tag)

            if len(hit_fields) > 1:
                possible_types = [self._CONTENT_TAG_TYPES[fn][0] for fn in hit_fields]
                raise AmbiguousEntityError(query=tag, matches=[{"id": f"{tag} ({t})", "name": f"{tag} ({t})", "year": t} for t in possible_types])

            field_name = hit_fields[0]
            label = self._CONTENT_TAG_TYPES[field_name][0]
            resolved_content[field_name].append(self._caches[label][norm])

        for field_name, values in resolved_content.items():
            setattr(new_filters, field_name, values if values else None)

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
