from datetime import datetime, timezone

import numpy as np
import mlflow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

from app.database.models import Game, GameRecommendation
from app.core.config import settings
from app.core.ml_config import RecommenderConfig
from app.core.mlflow_utils import tracked_run

# Model IDs this script owns -- used to scope both the pre-run DELETE and
# mlflow logging to exactly what it writes, not every model in the table.
# ("embedding" is served live via pgvector, not written here.)
OWNED_MODELS = ['metadata', 'tfidf']

def main():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Fetching games...")
    games = session.query(Game).all()
    n_games = len(games)
    print(f"Loaded {n_games} games.")

    if n_games == 0:
        return

    mlflow.log_params({
        "n_games": n_games,
        "recs_per_model_limit": RecommenderConfig.RECS_PER_MODEL_LIMIT,
        "tfidf_max_features": RecommenderConfig.TFIDF_MAX_FEATURES,
        "metadata_categorical_weight": RecommenderConfig.METADATA_CATEGORICAL_WEIGHT,
        "metadata_numeric_weight": RecommenderConfig.METADATA_NUMERIC_WEIGHT,
    })

    # Clear only the models this script owns -- an unscoped DELETE here
    # would silently wipe every other model's precomputed rows (graph,
    # collaborative) had this script run after them.
    print(f"Clearing existing recommendations for {OWNED_MODELS}...")
    session.query(GameRecommendation).filter(GameRecommendation.model.in_(OWNED_MODELS)).delete(synchronize_session=False)
    session.commit()

    bgg_ids = [g.bgg_id for g in games]
    computed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # ---------------------------------------------------------
    # 1. Metadata Features
    # ---------------------------------------------------------
    print("Extracting metadata features...")
    num_features = []
    cat_texts = []

    for g in games:
        weight = g.game_weight if g.game_weight is not None else 1.0
        playtime = g.mfg_playtime if g.mfg_playtime is not None else 30.0
        min_p = g.min_players if g.min_players is not None else 1.0
        max_p = g.max_players if g.max_players is not None else 4.0
        num_features.append([weight, playtime, min_p, max_p])

        categories = " ".join([c.name.replace(" ", "_") for c in g.categories])
        mechanics = " ".join([m.name.replace(" ", "_") for m in g.mechanics])
        subdomains = " ".join([s.name.replace(" ", "_") for s in g.subdomains])
        families = " ".join([f.name.replace(" ", "_") for f in g.families])
        cat_texts.append(f"{categories} {mechanics} {subdomains} {families}")

    num_features = np.array(num_features)
    scaler = MinMaxScaler()
    num_features_norm = scaler.fit_transform(num_features)

    cat_vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
    cat_features = cat_vectorizer.fit_transform(cat_texts)

    # ---------------------------------------------------------
    # 2. TF-IDF Text Features
    # ---------------------------------------------------------
    print("Extracting TF-IDF text features...")
    texts = []
    for g in games:
        cat_str = " ".join([c.name.replace(" ", "_") for c in g.categories])
        mech_str = " ".join([m.name.replace(" ", "_") for m in g.mechanics])
        subdomain_str = " ".join([s.name.replace(" ", "_") for s in g.subdomains])
        family_str = " ".join([f.name.replace(" ", "_") for f in g.families])
        des_str = " ".join([d.name.replace(" ", "_") for d in g.designers])
        pub_str = " ".join([p.name.replace(" ", "_") for p in g.publishers])

        text = f"{g.name} {g.description or ''} {cat_str} {mech_str} {subdomain_str} {family_str} {des_str} {pub_str}"
        texts.append(text)

    text_vectorizer = TfidfVectorizer(stop_words='english', max_features=RecommenderConfig.TFIDF_MAX_FEATURES)
    tfidf_features = text_vectorizer.fit_transform(texts)

    # ---------------------------------------------------------
    # Compute Similarities & Save
    # ---------------------------------------------------------
    LIMIT = RecommenderConfig.RECS_PER_MODEL_LIMIT
    batch_size = 100

    recs_to_insert = []
    total_recs_written = 0

    print("Computing recommendations in batches...")

    for start_idx in range(0, n_games, batch_size):
        end_idx = min(start_idx + batch_size, n_games)
        print(f"Processing batch {start_idx} to {end_idx}...")

        # 1. Metadata similarity
        batch_cat = cat_features[start_idx:end_idx]
        cat_sim = cosine_similarity(batch_cat, cat_features)

        batch_num = num_features_norm[start_idx:end_idx]
        num_sim = cosine_similarity(batch_num, num_features_norm)

        meta_sim = (
            RecommenderConfig.METADATA_CATEGORICAL_WEIGHT * cat_sim
            + RecommenderConfig.METADATA_NUMERIC_WEIGHT * num_sim
        )

        # 2. TF-IDF similarity
        batch_tfidf = tfidf_features[start_idx:end_idx]
        tfidf_sim = cosine_similarity(batch_tfidf, tfidf_features)

        # Zero out self-similarity
        for i in range(end_idx - start_idx):
            global_i = start_idx + i
            meta_sim[i, global_i] = -1
            tfidf_sim[i, global_i] = -1

        meta_topk = np.argsort(meta_sim, axis=1)[:, -LIMIT:][:, ::-1]
        tfidf_topk = np.argsort(tfidf_sim, axis=1)[:, -LIMIT:][:, ::-1]

        for i in range(end_idx - start_idx):
            global_i = start_idx + i
            gid = bgg_ids[global_i]

            # Metadata recs
            for tgt_idx in meta_topk[i]:
                score = float(meta_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append({
                    'game_id': gid,
                    'recommended_game_id': bgg_ids[tgt_idx],
                    'model': 'metadata',
                    'score': score,
                    'reasons': ["Similar categories and mechanics"],
                    'computed_at': computed_at,
                })

            # TF-IDF recs
            for tgt_idx in tfidf_topk[i]:
                score = float(tfidf_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append({
                    'game_id': gid,
                    'recommended_game_id': bgg_ids[tgt_idx],
                    'model': 'tfidf',
                    'score': score,
                    'reasons': ["Similar text descriptions"],
                    'computed_at': computed_at,
                })

        # Commit periodically
        if len(recs_to_insert) >= 5000:
            stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                index_elements=['game_id', 'recommended_game_id', 'model']
            )
            session.execute(stmt)
            session.commit()
            total_recs_written += len(recs_to_insert)
            recs_to_insert = []

    if recs_to_insert:
        total_recs_written += len(recs_to_insert)
        stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
            index_elements=['game_id', 'recommended_game_id', 'model']
        )
        session.execute(stmt)
        session.commit()

    mlflow.log_metrics({"recommendations_written": total_recs_written})
    print("Recommendation precomputation complete!")

if __name__ == "__main__":
    with tracked_run("recommender/content_based", run_name="precompute"):
        main()
