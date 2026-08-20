
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import embeddings as embedding_model
from app.core.ml_config import SearchConfig
from app.database.models import Artist, Category, Designer, Game, GameEmbedding, Mechanic, Publisher, Subdomain, Subfamily, Theme
from app.schemas.game_query import SORT_FIELD_TO_COLUMN, GameFilter, SortSpec
from app.schemas.search import PaginatedSearchResults, SearchDebug, SearchQuery, SearchResult


def apply_game_filters(query, filters: GameFilter | None):
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

    if filters.min_playtime is not None:
        query = query.filter(Game.mfg_playtime >= filters.min_playtime)
    if filters.max_playtime is not None:
        query = query.filter(Game.mfg_playtime <= filters.max_playtime)

    if filters.min_year is not None:
        query = query.filter(Game.year_published >= filters.min_year)
    if filters.max_year is not None:
        query = query.filter(Game.year_published <= filters.max_year)

    if filters.subdomains:
        for sub in filters.subdomains:
            query = query.filter(Game.subdomains.any(Subdomain.name == sub))
    if filters.categories:
        for cat in filters.categories:
            query = query.filter(Game.categories.any(Category.name == cat))
    if filters.themes:
        for theme in filters.themes:
            query = query.filter(Game.themes.any(Theme.name == theme))
    if filters.families:
        for fam in filters.families:
            query = query.filter(Game.families.any(Subfamily.name == fam))
    if filters.mechanics:
        for mech in filters.mechanics:
            query = query.filter(Game.mechanics.any(Mechanic.name == mech))
    if filters.designers:
        for designer in filters.designers:
            query = query.filter(Game.designers.any(Designer.name == designer))
    if filters.artists:
        for artist in filters.artists:
            query = query.filter(Game.artists.any(Artist.name == artist))
    if filters.publishers:
        for publisher in filters.publishers:
            query = query.filter(Game.publishers.any(Publisher.name == publisher))

    return query

class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.rrf_k = SearchConfig.RRF_K

    def search_lexical(self, q: str, limit: int = SearchConfig.CANDIDATE_POOL_SIZE) -> dict[int, int]:
        # 'english_unaccent' (not plain 'english') — must match the config
        # search_vector itself was built with (scripts/update_search_vectors.py),
        # or accent-insensitive matching silently doesn't happen: querying
        # "Chvatil" against an 'english'-tokenized tsvector containing
        # "Chvátil" returns zero rows, since the two accent forms produce
        # different lexemes under the plain config.
        tsquery = func.websearch_to_tsquery('english_unaccent', q)
        
        # Rank the results using ts_rank_cd. Tried adding normalization=1
        # (divide by 1 + log(document length)) to discount long, noisy
        # descriptions — measured it against a real query ("worker
        # placement"): it dropped the exact-name match "Worker Placement"
        # out of the top 5 entirely (its own description is long, so it got
        # penalized as much as an irrelevant long document would), while
        # promoting a much weaker match with a short description to #1.
        # ts_rank_cd's length normalization applies to the whole combined
        # tsvector, not per-field, so it can't distinguish "long because
        # noisy" from "long because it's a substantive, relevant match" —
        # reverted; not a clear win over the default.
        results = (
            self.db.query(Game.bgg_id)
            .filter(Game.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(Game.search_vector, tsquery).desc())
            .limit(limit)
            .all()
        )
        
        return {row.bgg_id: rank + 1 for rank, row in enumerate(results)}

    def search_semantic(self, q: str, limit: int = SearchConfig.CANDIDATE_POOL_SIZE) -> dict[int, int]:
        embedding = embedding_model.encode([q], is_query=True)[0]

        # Filter to the currently-configured model first — game_embeddings can
        # hold rows for more than one model at once (e.g. during a comparison),
        # and vectors of different dimensions can't be compared to each other.
        results = (
            self.db.query(GameEmbedding.game_id)
            .filter(GameEmbedding.model == SearchConfig.EMBEDDING_MODEL)
            .order_by(GameEmbedding.embedding.cosine_distance(embedding))
            .limit(limit)
            .all()
        )

        return {row.game_id: rank + 1 for rank, row in enumerate(results)}

    def _sort_by_field(self, candidates: list, filtered_games: dict[int, Game], sort: SortSpec) -> list:
        """Reorders `candidates` by a Game column instead of relevance --
        same field vocabulary and nulls-last placement as GameService.get_games'
        SQL ORDER BY, just applied in Python since these candidates were
        already fetched (and filtered/ranked by relevance) as a fixed list,
        not a live query. A game missing the sorted-on value (e.g. no
        rating yet) sorts after every game that has one, regardless of
        direction, matching nulls_last() on the plain browse path.
        """
        attr = SORT_FIELD_TO_COLUMN[sort.field]
        reverse = sort.direction == "desc"
        with_value = [c for c in candidates if getattr(filtered_games[c["bgg_id"]], attr) is not None]
        without_value = [c for c in candidates if getattr(filtered_games[c["bgg_id"]], attr) is None]
        with_value.sort(key=lambda c: getattr(filtered_games[c["bgg_id"]], attr), reverse=reverse)
        return with_value + without_value

    def search(self, search_query: SearchQuery, skip: int, limit: int) -> PaginatedSearchResults:
        lexical_ranks = {}
        semantic_ranks = {}
        
        # 1. Retrieval
        if search_query.mode in ["lexical", "hybrid"]:
            lexical_ranks = self.search_lexical(search_query.q, limit=SearchConfig.CANDIDATE_POOL_SIZE)

        if search_query.mode in ["semantic", "hybrid"]:
            semantic_ranks = self.search_semantic(search_query.q, limit=SearchConfig.CANDIDATE_POOL_SIZE)
            
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

        if search_query.sort:
            # An explicit sort overrides relevance ordering, but only
            # within a tight top-relevance slice, not the whole retrieval
            # pool -- see SearchConfig.SORT_RELEVANCE_POOL_SIZE for why a
            # marginal, barely-relevant match can't win purely by scoring
            # well on the sort field. Everything past that slice stays in
            # the result set, just left in relevance order instead of
            # re-sorted by field -- dropping it outright would both
            # understate `total` below the real match count and make any
            # page past the slice come back empty even though more real
            # matches exist.
            final_candidates.sort(key=lambda x: x["rrf_score"], reverse=True)
            floor = SearchConfig.SORT_RELEVANCE_POOL_SIZE
            reranked_head = self._sort_by_field(final_candidates[:floor], filtered_games, search_query.sort)
            final_candidates = reranked_head + final_candidates[floor:]
        else:
            # Default: sort by RRF score descending.
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
