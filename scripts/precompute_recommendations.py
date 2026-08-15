import sys
import os
import datetime
import json
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

# Add backend to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game, GameRecommendation
from app.core.config import settings

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

    # Clear existing recommendations
    print("Clearing existing recommendations...")
    session.query(GameRecommendation).delete()
    session.commit()

    bgg_ids = [g.bgg_id for g in games]
    
    # ---------------------------------------------------------
    # 1. Quality Scores (for Hybrid)
    # ---------------------------------------------------------
    print("Computing quality scores...")
    # Fill None ranks with a high number (e.g. 100000)
    ranks = np.array([g.rank if g.rank is not None else 100000 for g in games], dtype=float)
    # Inverse rank (higher is better)
    inv_ranks = 1.0 / (ranks + 1)
    ratings = np.array([g.avg_rating if g.avg_rating is not None else 0.0 for g in games], dtype=float)
    
    scaler = MinMaxScaler()
    inv_ranks_norm = scaler.fit_transform(inv_ranks.reshape(-1, 1)).flatten()
    ratings_norm = scaler.fit_transform(ratings.reshape(-1, 1)).flatten()
    
    # Quality = 0.5 * norm_rank + 0.5 * norm_rating
    quality_scores = 0.5 * inv_ranks_norm + 0.5 * ratings_norm
    quality_scores_norm = scaler.fit_transform(quality_scores.reshape(-1, 1)).flatten()

    # ---------------------------------------------------------
    # 2. Metadata Features
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
        cat_texts.append(f"{categories} {mechanics}")

    num_features = np.array(num_features)
    num_features_norm = scaler.fit_transform(num_features)
    
    cat_vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
    cat_features = cat_vectorizer.fit_transform(cat_texts)

    # ---------------------------------------------------------
    # 3. TF-IDF Text Features
    # ---------------------------------------------------------
    print("Extracting TF-IDF text features...")
    texts = []
    for g in games:
        cat_str = " ".join([c.name.replace(" ", "_") for c in g.categories])
        mech_str = " ".join([m.name.replace(" ", "_") for m in g.mechanics])
        des_str = " ".join([d.name.replace(" ", "_") for d in g.designers])
        pub_str = " ".join([p.name.replace(" ", "_") for p in g.publishers])
        
        text = f"{g.name} {g.description or ''} {cat_str} {mech_str} {des_str} {pub_str}"
        texts.append(text)
        
    text_vectorizer = TfidfVectorizer(stop_words='english', max_features=10000)
    tfidf_features = text_vectorizer.fit_transform(texts)

    # ---------------------------------------------------------
    # 4. Semantic Embeddings
    # ---------------------------------------------------------
    print("Extracting embeddings...")
    embeddings = []
    valid_embedding_mask = []
    for g in games:
        if g.embedding:
            # SQLAlchemy returns lists for pgvector Vectors
            emb = np.array(g.embedding, dtype=float)
            embeddings.append(emb)
            valid_embedding_mask.append(True)
        else:
            embeddings.append(np.zeros(384, dtype=float))
            valid_embedding_mask.append(False)
    embeddings = np.array(embeddings)

    # ---------------------------------------------------------
    # Compute Similarities & Save
    # ---------------------------------------------------------
    LIMIT = 10
    batch_size = 500
    
    recs_to_insert = []
    
    print("Computing recommendations in batches...")
    
    for start_idx in range(0, n_games, batch_size):
        end_idx = min(start_idx + batch_size, n_games)
        print(f"Processing batch {start_idx} to {end_idx}...")
        
        # 1. Metadata similarity
        batch_cat = cat_features[start_idx:end_idx]
        cat_sim = cosine_similarity(batch_cat, cat_features)
        
        batch_num = num_features_norm[start_idx:end_idx]
        num_sim = cosine_similarity(batch_num, num_features_norm)
        
        meta_sim = 0.7 * cat_sim + 0.3 * num_sim
        
        # 2. TF-IDF similarity
        batch_tfidf = tfidf_features[start_idx:end_idx]
        tfidf_sim = cosine_similarity(batch_tfidf, tfidf_features)
        
        # 3. Embedding similarity
        batch_emb = embeddings[start_idx:end_idx]
        emb_sim = cosine_similarity(batch_emb, embeddings)
        for i in range(end_idx - start_idx):
            if not valid_embedding_mask[start_idx + i]:
                emb_sim[i] = 0.0
                
        # Zero out self-similarity
        for i in range(end_idx - start_idx):
            global_i = start_idx + i
            meta_sim[i, global_i] = -1
            tfidf_sim[i, global_i] = -1
            emb_sim[i, global_i] = -1

        # Normalize the rows to 0-1 for Hybrid
        def row_norm(mat):
            min_v = mat.min(axis=1, keepdims=True)
            max_v = mat.max(axis=1, keepdims=True)
            diff = max_v - min_v
            diff[diff == 0] = 1.0
            return (mat - min_v) / diff

        meta_norm = row_norm(meta_sim)
        tfidf_norm = row_norm(tfidf_sim)
        emb_norm = row_norm(emb_sim)

        # 4. Hybrid similarity
        # Final = 0.45 * emb + 0.25 * meta + 0.15 * tfidf + 0.15 * quality
        hybrid_sim = 0.45 * emb_norm + 0.25 * meta_norm + 0.15 * tfidf_norm + 0.15 * quality_scores_norm.reshape(1, -1)
        for i in range(end_idx - start_idx):
            hybrid_sim[i, start_idx + i] = -1
            
        # Top K indices for each
        meta_topk = np.argsort(meta_sim, axis=1)[:, -LIMIT:][:, ::-1]
        tfidf_topk = np.argsort(tfidf_sim, axis=1)[:, -LIMIT:][:, ::-1]
        emb_topk = np.argsort(emb_sim, axis=1)[:, -LIMIT:][:, ::-1]
        hybrid_topk = np.argsort(hybrid_sim, axis=1)[:, -LIMIT:][:, ::-1]

        for i in range(end_idx - start_idx):
            global_i = start_idx + i
            gid = bgg_ids[global_i]
            
            # Metadata recs
            for tgt_idx in meta_topk[i]:
                score = float(meta_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append(GameRecommendation(
                    game_id=gid,
                    recommended_game_id=bgg_ids[tgt_idx],
                    model='metadata',
                    score=score,
                    reasons=["Similar categories and mechanics"]
                ))
                
            # TF-IDF recs
            for tgt_idx in tfidf_topk[i]:
                score = float(tfidf_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append(GameRecommendation(
                    game_id=gid,
                    recommended_game_id=bgg_ids[tgt_idx],
                    model='tfidf',
                    score=score,
                    reasons=["Similar text descriptions"]
                ))
                
            # Embedding recs
            for tgt_idx in emb_topk[i]:
                score = float(emb_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append(GameRecommendation(
                    game_id=gid,
                    recommended_game_id=bgg_ids[tgt_idx],
                    model='embedding',
                    score=score,
                    reasons=["High semantic similarity"]
                ))
                
            # Hybrid recs
            for tgt_idx in hybrid_topk[i]:
                score = float(hybrid_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append(GameRecommendation(
                    game_id=gid,
                    recommended_game_id=bgg_ids[tgt_idx],
                    model='hybrid',
                    score=score,
                    reasons=["High overall match (content + quality)"]
                ))

        # Commit periodically
        if len(recs_to_insert) >= 20000:
            session.bulk_save_objects(recs_to_insert)
            session.commit()
            recs_to_insert = []

    if recs_to_insert:
        session.bulk_save_objects(recs_to_insert)
        session.commit()

    print("Recommendation precomputation complete!")

if __name__ == "__main__":
    main()
