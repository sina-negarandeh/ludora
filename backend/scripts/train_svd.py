import os
import sys
import pandas as pd
from pathlib import Path

# Add backend dir to path so we can import app modules
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.recommenders.collaborative.svd import SVDRecommender

def main():
    base_dir = os.path.join(os.path.dirname(__file__), '../../data/processed')
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
    
    print("Training SVD Collaborative Filtering Model...")
    # 50 factors is a good balance for item embeddings
    model = SVDRecommender(n_factors=50)
    model.fit(df)
    
    model_dir = os.path.join(os.path.dirname(__file__), '../../data/models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, 'cf_svd.pkl')
    print(f"Saving SVD model to {model_path}...")
    model.save(model_path)
    
    print("Done!")

if __name__ == "__main__":
    main()
