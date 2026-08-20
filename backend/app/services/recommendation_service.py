# Known limitation, tracked in docs/roadmap.md: app/database/models.py uses
# SQLAlchemy's legacy Column(...) declarative style, not 2.0's typed
# Mapped[]/mapped_column(). Pyright can't tell an instance attribute like
# `game.rank` apart from the class-level Column descriptor, so it reports
# every read of a model attribute as Column[X] instead of X. These are
# false positives, not real bugs -- confirmed by direct behavior at
# runtime throughout this session -- and this file is unusually dense with
# them since it's mostly model-attribute plumbing. Suppressed here rather
# than project-wide so a real error of the same rule elsewhere still surfaces.
# pyright: reportArgumentType=false, reportCallIssue=false, reportGeneralTypeIssues=false

from sqlalchemy.orm import Session, joinedload

from app.core.ml_config import RECOMMENDATION_MODELS, RecommenderConfig, SearchConfig
from app.database.models import Game, GameEmbedding, GameRecommendation
from app.recommenders.utils import minmax_normalize_scores


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def get_recommendation_models(self) -> list[dict]:
        # Single source of truth in ml_config.py -- previously a stale,
        # disagreeing 3-entry list nothing else matched (the frontend
        # hardcoded its own separate 10-entry array instead of calling this).
        return RECOMMENDATION_MODELS

    def get_recommendations(self, game_id: int, model: str, limit: int = 10):
        source_game = self.db.query(Game).filter(Game.bgg_id == game_id).first()
        if not source_game:
            return None, []

        if model == "popularity":
            # Not personalized and not related to the source game -- the
            # same global top-N list is returned regardless of game_id, by
            # design (the non-personalized baseline every other model is
            # implicitly compared against). `score` is still populated (the
            # API schema requires it), but as a real popularity intensity
            # -- normalized inverse rank -- not a meaningless flat 1.0 for
            # every result. The frontend doesn't present this as a "% match"
            # for this model, since it isn't one.
            top_games = self.db.query(Game).order_by(Game.rank.asc()).filter(Game.rank.isnot(None), Game.bgg_id != game_id).limit(limit).all()
            if not top_games:
                return source_game, []
            inv_ranks = {g.bgg_id: 1.0 / g.rank for g in top_games}
            norm = minmax_normalize_scores(inv_ranks)
            recs = [
                {"game": g, "score": round(norm[g.bgg_id], 4), "reason": ["Highly ranked universally popular game"]}
                for g in top_games
            ]
            return source_game, recs

        if model == "hybrid":
            # Deliberately live, not precomputed: both inputs are already
            # precomputed top-N lists (RecommenderConfig.RECS_PER_MODEL_LIMIT
            # rows each), so combining them is a handful of floats and a
            # sort -- not an O(n^2) similarity matrix like the models that
            # actually justify batch precompute. Also means a "hybrid" row
            # is never stale relative to its two sources, unlike a stored
            # blend would be whenever cf_item_cosine/metadata get recomputed.
            collab_model = RecommenderConfig.HYBRID_COLLABORATIVE_MODEL
            content_model = RecommenderConfig.HYBRID_CONTENT_MODEL
            weights = RecommenderConfig.HYBRID_ENGINE_WEIGHTS

            source_rows = self.db.query(GameRecommendation).filter(
                GameRecommendation.game_id == game_id,
                GameRecommendation.model.in_([collab_model, content_model]),
            ).all()
            collab_scores = {r.recommended_game_id: r.score for r in source_rows if r.model == collab_model}
            content_scores = {r.recommended_game_id: r.score for r in source_rows if r.model == content_model}

            candidate_ids = (set(collab_scores) | set(content_scores)) - {game_id}
            if not candidate_ids:
                return source_game, []

            collab_norm = minmax_normalize_scores(collab_scores)
            content_norm = minmax_normalize_scores(content_scores)

            blended = {
                cid: weights["collaborative"] * collab_norm.get(cid, 0.0) + weights["content"] * content_norm.get(cid, 0.0)
                for cid in candidate_ids
            }
            top_ids = [cid for cid, score in sorted(blended.items(), key=lambda kv: kv[1], reverse=True)[:limit] if score > 0]

            games_by_id = {g.bgg_id: g for g in self.db.query(Game).filter(Game.bgg_id.in_(top_ids)).all()}
            recs = []
            for cid in top_ids:
                g = games_by_id.get(cid)
                if g is None:
                    continue
                sources = []
                if cid in collab_scores:
                    sources.append("collaborative")
                if cid in content_scores:
                    sources.append("content")
                recs.append({"game": g, "score": round(blended[cid], 4), "reason": [f"Blended {' + '.join(sources)} match"]})
            return source_game, recs

        if model == "embedding":
            # Deliberately live, not precomputed: this always reflects the
            # current game_embeddings state, unlike every other model here.
            # metadata/tfidf/ensemble used to be special-cased into this
            # same branch too -- silently discarding the genuinely distinct
            # scores scripts/precompute_content_recommendations.py computes
            # and writes for them, since it was never actually reachable.
            # They now fall through to the generic precomputed-lookup below,
            # same as every other model.
            source_embedding = self.db.query(GameEmbedding).filter(
                GameEmbedding.game_id == game_id,
                GameEmbedding.model == SearchConfig.EMBEDDING_MODEL,
            ).first()
            if source_embedding is None:
                return source_game, []

            distance_col = GameEmbedding.embedding.cosine_distance(source_embedding.embedding)
            similar = (
                self.db.query(GameEmbedding, distance_col.label("distance"))
                .options(joinedload(GameEmbedding.game))
                .filter(
                    GameEmbedding.game_id != game_id,
                    GameEmbedding.model == SearchConfig.EMBEDDING_MODEL,
                )
                .order_by(distance_col)
                .limit(limit)
                .all()
            )

            # cosine_distance is 0 (identical) to 2 (opposite); similarity =
            # 1 - distance gives the conventional -1..1 cosine similarity
            # instead of the previous hardcoded, meaningless score of 1.0
            # for every single result.
            recs = [
                {"game": e.game, "score": round(1.0 - distance, 4), "reason": ["Semantically similar based on rich metadata"]}
                for e, distance in similar
            ]
            return source_game, recs

        # Precomputed models -- content (metadata/tfidf), graph
        # (graph_jaccard/deepwalk), and collaborative (cf_item_cosine/
        # cf_als) all read the same way: their own distinct rows in
        # game_recommendations, written by their respective precompute
        # scripts. "hybrid" and "embedding" are handled above -- both live.
        db_recs = self.db.query(GameRecommendation).filter(
            GameRecommendation.game_id == game_id,
            GameRecommendation.model == model
        ).order_by(GameRecommendation.score.desc()).limit(limit).all()

        recs = []
        for r in db_recs:
            if not r.recommended_game:
                continue
            recs.append({
                "game": r.recommended_game,
                "score": round(r.score, 4),
                "reason": r.reasons or []
            })

        return source_game, recs
