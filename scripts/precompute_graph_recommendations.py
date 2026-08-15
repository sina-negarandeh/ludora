import sys
import os
import numpy as np
import scipy.sparse as sp
import networkx as nx
from node2vec import Node2Vec
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer

# Add backend to path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
sys.path.append('/app')

from app.database.models import Game, GameRecommendation
from app.core.config import settings

def sparse_jaccard(X_batch, X_all):
    """
    Computes Jaccard similarity between X_batch (B, M) and X_all (N, M)
    Returns matrix of shape (B, N)
    """
    intersection = X_batch.dot(X_all.T).toarray()
    batch_sums = np.asarray(X_batch.sum(axis=1)).flatten()
    all_sums = np.asarray(X_all.sum(axis=1)).flatten()
    
    union = batch_sums[:, None] + all_sums[None, :] - intersection
    
    with np.errstate(divide='ignore', invalid='ignore'):
        jaccard = intersection / union
    jaccard[np.isnan(jaccard)] = 0.0
    return jaccard

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

    # Clear existing graph recommendations
    print("Clearing existing graph recommendations...")
    session.query(GameRecommendation).filter(
        GameRecommendation.model.in_(['graph_jaccard', 'node2vec'])
    ).delete(synchronize_session=False)
    session.commit()

    bgg_ids = [g.bgg_id for g in games]
    
    # ---------------------------------------------------------
    # 1. Weighted Jaccard Similarity
    # ---------------------------------------------------------
    print("Preparing data for Jaccard...")
    
    mechanics_list = [[m.name for m in g.mechanics] for g in games]
    categories_list = [[c.name for c in g.categories] for g in games]
    designers_list = [[d.name for d in g.designers] for g in games]
    publishers_list = [[p.name for p in g.publishers] for g in games]
    artists_list = [[a.name for a in g.artists] for g in games]
    
    mlb_mech = MultiLabelBinarizer(sparse_output=True)
    X_mech = mlb_mech.fit_transform(mechanics_list)
    
    mlb_cat = MultiLabelBinarizer(sparse_output=True)
    X_cat = mlb_cat.fit_transform(categories_list)
    
    mlb_des = MultiLabelBinarizer(sparse_output=True)
    X_des = mlb_des.fit_transform(designers_list)
    
    mlb_pub = MultiLabelBinarizer(sparse_output=True)
    X_pub = mlb_pub.fit_transform(publishers_list)
    
    mlb_art = MultiLabelBinarizer(sparse_output=True)
    X_art = mlb_art.fit_transform(artists_list)
    
    # Weights requested: mech 0.4, cat 0.3, des 0.05, pub 0.025, art 0.025
    # Total = 0.8. Normalize to sum to 1.0.
    total_w = 0.4 + 0.3 + 0.05 + 0.025 + 0.025
    w_mech = 0.4 / total_w
    w_cat = 0.3 / total_w
    w_des = 0.05 / total_w
    w_pub = 0.025 / total_w
    w_art = 0.025 / total_w
    
    LIMIT = 10
    batch_size = 200
    
    recs_to_insert = []
    
    print("Computing Weighted Jaccard in batches...")
    for start_idx in range(0, n_games, batch_size):
        end_idx = min(start_idx + batch_size, n_games)
        print(f"Jaccard batch {start_idx} to {end_idx}...")
        
        j_mech = sparse_jaccard(X_mech[start_idx:end_idx], X_mech)
        j_cat = sparse_jaccard(X_cat[start_idx:end_idx], X_cat)
        j_des = sparse_jaccard(X_des[start_idx:end_idx], X_des)
        j_pub = sparse_jaccard(X_pub[start_idx:end_idx], X_pub)
        j_art = sparse_jaccard(X_art[start_idx:end_idx], X_art)
        
        jaccard_sim = (
            w_mech * j_mech + 
            w_cat * j_cat + 
            w_des * j_des + 
            w_pub * j_pub + 
            w_art * j_art
        )
        
        # Zero out self-similarity
        for i in range(end_idx - start_idx):
            jaccard_sim[i, start_idx + i] = -1
            
        jaccard_topk = np.argsort(jaccard_sim, axis=1)[:, -LIMIT:][:, ::-1]
        
        for i in range(end_idx - start_idx):
            gid = bgg_ids[start_idx + i]
            # Graph Jaccard recs
            for tgt_idx in jaccard_topk[i]:
                score = float(jaccard_sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append({
                    'game_id': gid,
                    'recommended_game_id': bgg_ids[tgt_idx],
                    'model': 'graph_jaccard',
                    'score': score,
                    'reasons': ["High structural similarity (Weighted Jaccard)"]
                })
        
        # Commit periodically
        if len(recs_to_insert) >= 5000:
            stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                index_elements=['game_id', 'recommended_game_id', 'model']
            )
            session.execute(stmt)
            session.commit()
            recs_to_insert = []
            
    if recs_to_insert:
        stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
            index_elements=['game_id', 'recommended_game_id', 'model']
        )
        session.execute(stmt)
        session.commit()
        recs_to_insert = []

    # ---------------------------------------------------------
    # 2. DeepWalk Graph Embeddings (replaces memory-heavy Node2Vec)
    # ---------------------------------------------------------
    print("Building Graph for DeepWalk...")
    import random
    from gensim.models import Word2Vec
    
    G = nx.Graph()
    
    for g in games:
        game_node = f"G_{g.bgg_id}"
        G.add_node(game_node, type="game")
        
        for m in g.mechanics:
            node = f"M_{m.id}"
            G.add_edge(game_node, node)
        for c in g.categories:
            node = f"C_{c.id}"
            G.add_edge(game_node, node)
        for d in g.designers:
            node = f"D_{d.id}"
            G.add_edge(game_node, node)
        for p in g.publishers:
            node = f"P_{p.id}"
            G.add_edge(game_node, node)
        for a in g.artists:
            node = f"A_{a.id}"
            G.add_edge(game_node, node)
            
    print(f"Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    print("Generating random walks...")
    num_walks = 10
    walk_length = 10
    walks = []
    nodes = list(G.nodes())
    
    # Pre-fetch neighbors to array for faster random choices
    neighbors_dict = {node: list(G.neighbors(node)) for node in nodes}
    
    for walk_iter in range(num_walks):
        print(f"Walk iteration {walk_iter+1}/{num_walks}...")
        random.shuffle(nodes)
        for node in nodes:
            walk = [node]
            curr_node = node
            for _ in range(walk_length - 1):
                neighbors = neighbors_dict[curr_node]
                if not neighbors:
                    break
                curr_node = random.choice(neighbors)
                walk.append(curr_node)
            walks.append(walk)
    
    print("Training Word2Vec model on walks...")
    model = Word2Vec(walks, vector_size=64, window=5, min_count=1, sg=1, workers=4, epochs=1)
    
    print("Extracting game embeddings...")
    embeddings = []
    for gid in bgg_ids:
        node_name = f"G_{gid}"
        if node_name in model.wv:
            embeddings.append(model.wv[node_name])
        else:
            embeddings.append(np.zeros(64))
    
    embeddings = np.array(embeddings)
    
    print("Computing Node2Vec similarities...")
    for start_idx in range(0, n_games, batch_size):
        end_idx = min(start_idx + batch_size, n_games)
        print(f"Node2Vec batch {start_idx} to {end_idx}...")
        
        batch_emb = embeddings[start_idx:end_idx]
        sim = cosine_similarity(batch_emb, embeddings)
        
        for i in range(end_idx - start_idx):
            sim[i, start_idx + i] = -1
            
        topk = np.argsort(sim, axis=1)[:, -LIMIT:][:, ::-1]
        
        for i in range(end_idx - start_idx):
            gid = bgg_ids[start_idx + i]
            for tgt_idx in topk[i]:
                score = float(sim[i, tgt_idx])
                if score <= 0: continue
                recs_to_insert.append({
                    'game_id': gid,
                    'recommended_game_id': bgg_ids[tgt_idx],
                    'model': 'node2vec',
                    'score': score,
                    'reasons': ["Deep graph relationship match"]
                })
                
        if len(recs_to_insert) >= 5000:
            stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                index_elements=['game_id', 'recommended_game_id', 'model']
            )
            session.execute(stmt)
            session.commit()
            recs_to_insert = []
            
    if recs_to_insert:
        stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
            index_elements=['game_id', 'recommended_game_id', 'model']
        )
        session.execute(stmt)
        session.commit()
        
    print("Graph recommendation precomputation complete!")

if __name__ == "__main__":
    main()
