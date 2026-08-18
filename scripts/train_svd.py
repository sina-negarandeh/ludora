import os
import pandas as pd
import mlflow

from app.recommenders.collaborative.svd import SVDRecommender
from app.core.ml_config import RANDOM_SEED, RecommenderConfig
from app.core.mlflow_utils import tracked_run

def main():
    base_dir = os.path.join(os.path.dirname(__file__), '../data/processed')
    ratings_path = os.path.join(base_dir, 'master_ratings.csv')

    if not os.path.exists(ratings_path):
        print(f"Error: {ratings_path} not found.")
        return

    print(f"Loading ratings from {ratings_path}...")
    # Load dataset. We expect user_id, game_id, rating
    df = pd.read_csv(
        ratings_path,
        usecols=['user_id', 'game_id', 'rating'],
        dtype={'user_id': 'int32', 'game_id': 'int32', 'rating': 'float32'}
    )

    # Rename to match what SVDRecommender expects ('user', 'item', 'rating')
    df.rename(columns={'user_id': 'user', 'game_id': 'item'}, inplace=True)

    print(f"Loaded {len(df)} ratings.")
    print(f"Unique Users: {df['user'].nunique()}, Unique Items: {df['item'].nunique()}")

    with tracked_run("recommender/collaborative", run_name="cf_svd_train"):
        mlflow.log_params({
            "n_factors": RecommenderConfig.CF_SVD_N_FACTORS,
            "random_seed": RANDOM_SEED,
            "n_ratings": len(df),
            "n_users": df['user'].nunique(),
            "n_items": df['item'].nunique(),
        })

        print("Training SVD Collaborative Filtering Model...")
        model = SVDRecommender(n_factors=RecommenderConfig.CF_SVD_N_FACTORS)
        model.fit(df)

        model_dir = os.path.join(os.path.dirname(__file__), '../data/models')
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, 'cf_svd.pkl')
        print(f"Saving SVD model to {model_path}...")
        model.save(model_path)
        mlflow.log_artifact(model_path)

    print("Done!")

if __name__ == "__main__":
    main()
