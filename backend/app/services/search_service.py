from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import Game, Category, Mechanic, Theme
from app.schemas.search import SearchQuery, PaginatedSearchResults, SearchResult, SearchDebug
from app.schemas.game_query import GameFilter
from typing import Dict, List
import datetime
from sentence_transformers import SentenceTransformer

# Load embedding model once globally
model = SentenceTransformer('all-MiniLM-L6-v2')

def apply_game_filters(query, filters: GameFilter):
    if not filters:
        return query
        
    if filters.exact_players is not None:
        query = query.filter(Game.min_players <= filters.exact_players, Game.max_players >= filters.exact_players)
        
    if filters.min_players is not None:
        query = query.filter(Game.min_players >= filters.min_players)
    if filters.max_players is not None:
        query = query.filter(Game.max_players <= filters.max_players)
        
    if filters.min_weight is not None:
        query = query.filter(Game.game_weight >= filters.min_weight)
    if filters.max_weight is not None:
        query = query.filter(Game.game_weight <= filters.max_weight)
        
    if filters.min_year is not None:
        query = query.filter(Game.year_published >= filters.min_year)
    if filters.max_year is not None:
        query = query.filter(Game.year_published <= filters.max_year)

    if filters.categories:
        for cat in filters.categories:
            query = query.filter(Game.categories.any(Category.name == cat))
    if filters.themes:
        for theme in filters.themes:
            query = query.filter(Game.themes.any(Theme.name == theme))
    if filters.mechanics:
        for mech in filters.mechanics:
            query = query.filter(Game.mechanics.any(Mechanic.name == mech))
            
    return query

class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.rrf_k = 60

    def search_lexical(self, q: str, limit: int = 100) -> Dict[int, int]:
        # Using websearch_to_tsquery for natural language-like parsing
        tsquery = func.websearch_to_tsquery('english', q)
        
        # Rank the results using ts_rank_cd
        results = (
            self.db.query(Game.bgg_id)
            .filter(Game.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(Game.search_vector, tsquery).desc())
            .limit(limit)
            .all()
        )
        
        return {row.bgg_id: rank + 1 for rank, row in enumerate(results)}

    def search_semantic(self, q: str, limit: int = 100) -> Dict[int, int]:
        embedding = model.encode(q).tolist()
        
        results = (
            self.db.query(Game.bgg_id)
            .order_by(Game.embedding.cosine_distance(embedding))
            .limit(limit)
            .all()
        )
        
        return {row.bgg_id: rank + 1 for rank, row in enumerate(results)}

    def search(self, search_query: SearchQuery, skip: int, limit: int) -> PaginatedSearchResults:
        lexical_ranks = {}
        semantic_ranks = {}
        
        # 1. Retrieval
        if search_query.mode in ["lexical", "hybrid"]:
            lexical_ranks = self.search_lexical(search_query.q, limit=100)
            
        if search_query.mode in ["semantic", "hybrid"]:
            semantic_ranks = self.search_semantic(search_query.q, limit=100)
            
        # 2. Candidate Pool & RRF
        candidate_ids = set(lexical_ranks.keys()).union(semantic_ranks.keys())
        
        scored_candidates = []
        for bgg_id in candidate_ids:
            l_rank = lexical_ranks.get(bgg_id)
            s_rank = semantic_ranks.get(bgg_id)
            
            l_score = 1.0 / (self.rrf_k + l_rank) if l_rank else 0.0
            s_score = 1.0 / (self.rrf_k + s_rank) if s_rank else 0.0
            
            # Simple sum of RRF scores
            rrf_score = l_score + s_score
            
            scored_candidates.append({
                "bgg_id": bgg_id,
                "lexical_rank": l_rank,
                "semantic_rank": s_rank,
                "rrf_score": rrf_score
            })
            
        # 3. Filtering
        base_query = self.db.query(Game).filter(Game.bgg_id.in_([c["bgg_id"] for c in scored_candidates]))
        filtered_query = apply_game_filters(base_query, search_query.filters)
        
        # Execute query to get full game objects
        filtered_games = {g.bgg_id: g for g in filtered_query.all()}
        
        # 4. Final Ranking
        # Only keep candidates that passed the filter
        final_candidates = [c for c in scored_candidates if c["bgg_id"] in filtered_games]
        
        # Sort by RRF score descending
        final_candidates.sort(key=lambda x: x["rrf_score"], reverse=True)
        
        # 5. Pagination
        total = len(final_candidates)
        paginated_candidates = final_candidates[skip:skip + limit]
        
        search_results = []
        for c in paginated_candidates:
            game_obj = filtered_games[c["bgg_id"]]
            search_results.append(
                SearchResult(
                    game=game_obj,
                    score=c["rrf_score"],
                    debug=SearchDebug(
                        lexical_rank=c["lexical_rank"],
                        semantic_rank=c["semantic_rank"],
                        rrf_score=c["rrf_score"]
                    )
                )
            )
            
        return PaginatedSearchResults(total=total, items=search_results)
