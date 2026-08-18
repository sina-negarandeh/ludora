import random

import numpy as np
import networkx as nx
import mlflow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer

from app.database.models import Game, GameRecommendation
from app.core.config import settings
from app.core.ml_config import RANDOM_SEED, RecommenderConfig
from app.core.mlflow_utils import tracked_run

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

def run_jaccard(session, games, bgg_ids, batch_size=200):
    """Weighted multi-relation Jaccard similarity (model id: 'graph_jaccard')."""
    weights = RecommenderConfig.GRAPH_JACCARD_WEIGHTS
    total_w = sum(weights.values())
    w_mech = weights["mechanics"] / total_w
    w_cat = weights["categories"] / total_w
    w_des = weights["designers"] / total_w
    w_pub = weights["publishers"] / total_w
    w_art = weights["artists"] / total_w
    LIMIT = RecommenderConfig.RECS_PER_MODEL_LIMIT
    n_games = len(games)

    with tracked_run("recommender/graph", run_name="graph_jaccard_precompute"):
        mlflow.log_params({**{f"weight_{k}": v for k, v in weights.items()}, "n_games": n_games, "recs_per_model_limit": LIMIT})

        print("Preparing data for Jaccard...")
        mechanics_list = [[m.name for m in g.mechanics] for g in games]
        categories_list = [[c.name for c in g.categories] for g in games]
        designers_list = [[d.name for d in g.designers] for g in games]
        publishers_list = [[p.name for p in g.publishers] for g in games]
        artists_list = [[a.name for a in g.artists] for g in games]

        X_mech = MultiLabelBinarizer(sparse_output=True).fit_transform(mechanics_list)
        X_cat = MultiLabelBinarizer(sparse_output=True).fit_transform(categories_list)
        X_des = MultiLabelBinarizer(sparse_output=True).fit_transform(designers_list)
        X_pub = MultiLabelBinarizer(sparse_output=True).fit_transform(publishers_list)
        X_art = MultiLabelBinarizer(sparse_output=True).fit_transform(artists_list)

        recs_to_insert = []
        total_recs_written = 0

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

            for i in range(end_idx - start_idx):
                jaccard_sim[i, start_idx + i] = -1

            jaccard_topk = np.argsort(jaccard_sim, axis=1)[:, -LIMIT:][:, ::-1]

            for i in range(end_idx - start_idx):
                gid = bgg_ids[start_idx + i]
                for tgt_idx in jaccard_topk[i]:
                    score = float(jaccard_sim[i, tgt_idx])
                    if score <= 0:
                        continue
                    recs_to_insert.append({
                        'game_id': gid,
                        'recommended_game_id': bgg_ids[tgt_idx],
                        'model': 'graph_jaccard',
                        'score': score,
                        'reasons': ["High structural similarity (Weighted Jaccard)"]
                    })

            if len(recs_to_insert) >= 5000:
                stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                    index_elements=['game_id', 'recommended_game_id', 'model']
                )
                session.execute(stmt)
                session.commit()
                total_recs_written += len(recs_to_insert)
                recs_to_insert = []

        if recs_to_insert:
            stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                index_elements=['game_id', 'recommended_game_id', 'model']
            )
            session.execute(stmt)
            session.commit()
            total_recs_written += len(recs_to_insert)

        mlflow.log_metrics({"recommendations_written": total_recs_written})

def run_deepwalk(session, games, bgg_ids, batch_size=200):
    """DeepWalk graph embeddings via gensim Word2Vec (model id: 'deepwalk').

    Replaces the memory-heavy, never-actually-trained node2vec PyPI-package
    path (scripts/build_node2vec_graph.py / train_node2vec.py — removed).
    Random walk generation is seeded for reproducibility.
    """
    LIMIT = RecommenderConfig.RECS_PER_MODEL_LIMIT
    n_games = len(games)
    rng = random.Random(RANDOM_SEED)

    with tracked_run("recommender/graph", run_name="deepwalk_precompute"):
        mlflow.log_params({
            "num_walks": RecommenderConfig.DEEPWALK_NUM_WALKS,
            "walk_length": RecommenderConfig.DEEPWALK_WALK_LENGTH,
            "vector_size": RecommenderConfig.DEEPWALK_VECTOR_SIZE,
            "window": RecommenderConfig.DEEPWALK_WINDOW,
            "epochs": RecommenderConfig.DEEPWALK_EPOCHS,
            "min_count": RecommenderConfig.DEEPWALK_MIN_COUNT,
            "random_seed": RANDOM_SEED,
            "n_games": n_games,
            "recs_per_model_limit": LIMIT,
        })

        print("Building Graph for DeepWalk...")
        from gensim.models import Word2Vec

        G = nx.Graph()
        for g in games:
            game_node = f"G_{g.bgg_id}"
            G.add_node(game_node, type="game")
            for m in g.mechanics:
                G.add_edge(game_node, f"M_{m.id}")
            for c in g.categories:
                G.add_edge(game_node, f"C_{c.id}")
            for d in g.designers:
                G.add_edge(game_node, f"D_{d.id}")
            for p in g.publishers:
                G.add_edge(game_node, f"P_{p.id}")
            for a in g.artists:
                G.add_edge(game_node, f"A_{a.id}")

        print(f"Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
        mlflow.log_params({"graph_nodes": G.number_of_nodes(), "graph_edges": G.number_of_edges()})

        print("Generating random walks...")
        num_walks = RecommenderConfig.DEEPWALK_NUM_WALKS
        walk_length = RecommenderConfig.DEEPWALK_WALK_LENGTH
        walks = []
        nodes = list(G.nodes())
        neighbors_dict = {node: list(G.neighbors(node)) for node in nodes}

        for walk_iter in range(num_walks):
            print(f"Walk iteration {walk_iter+1}/{num_walks}...")
            rng.shuffle(nodes)
            for node in nodes:
                walk = [node]
                curr_node = node
                for _ in range(walk_length - 1):
                    neighbors = neighbors_dict[curr_node]
                    if not neighbors:
                        break
                    curr_node = rng.choice(neighbors)
                    walk.append(curr_node)
                walks.append(walk)

        print("Training Word2Vec model on walks...")
        model = Word2Vec(
            walks,
            vector_size=RecommenderConfig.DEEPWALK_VECTOR_SIZE,
            window=RecommenderConfig.DEEPWALK_WINDOW,
            min_count=RecommenderConfig.DEEPWALK_MIN_COUNT,
            sg=1,
            workers=4,
            epochs=RecommenderConfig.DEEPWALK_EPOCHS,
            seed=RANDOM_SEED,
        )

        print("Extracting game embeddings...")
        embeddings = []
        for gid in bgg_ids:
            node_name = f"G_{gid}"
            if node_name in model.wv:
                embeddings.append(model.wv[node_name])
            else:
                embeddings.append(np.zeros(RecommenderConfig.DEEPWALK_VECTOR_SIZE))
        embeddings = np.array(embeddings)

        recs_to_insert = []
        total_recs_written = 0

        print("Computing DeepWalk similarities...")
        for start_idx in range(0, n_games, batch_size):
            end_idx = min(start_idx + batch_size, n_games)
            print(f"DeepWalk batch {start_idx} to {end_idx}...")

            batch_emb = embeddings[start_idx:end_idx]
            sim = cosine_similarity(batch_emb, embeddings)

            for i in range(end_idx - start_idx):
                sim[i, start_idx + i] = -1

            topk = np.argsort(sim, axis=1)[:, -LIMIT:][:, ::-1]

            for i in range(end_idx - start_idx):
                gid = bgg_ids[start_idx + i]
                for tgt_idx in topk[i]:
                    score = float(sim[i, tgt_idx])
                    if score <= 0:
                        continue
                    recs_to_insert.append({
                        'game_id': gid,
                        'recommended_game_id': bgg_ids[tgt_idx],
                        'model': 'deepwalk',
                        'score': score,
                        'reasons': ["Deep graph relationship match"]
                    })

            if len(recs_to_insert) >= 5000:
                stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                    index_elements=['game_id', 'recommended_game_id', 'model']
                )
                session.execute(stmt)
                session.commit()
                total_recs_written += len(recs_to_insert)
                recs_to_insert = []

        if recs_to_insert:
            stmt = insert(GameRecommendation).values(recs_to_insert).on_conflict_do_nothing(
                index_elements=['game_id', 'recommended_game_id', 'model']
            )
            session.execute(stmt)
            session.commit()
            total_recs_written += len(recs_to_insert)

        mlflow.log_metrics({"recommendations_written": total_recs_written})

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

    print("Clearing existing graph recommendations...")
    session.query(GameRecommendation).filter(
        GameRecommendation.model.in_(['graph_jaccard', 'deepwalk'])
    ).delete(synchronize_session=False)
    session.commit()

    bgg_ids = [g.bgg_id for g in games]

    run_jaccard(session, games, bgg_ids)
    run_deepwalk(session, games, bgg_ids)

    print("Graph recommendation precomputation complete!")

if __name__ == "__main__":
    main()
