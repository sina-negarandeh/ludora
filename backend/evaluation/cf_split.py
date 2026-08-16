import sys
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from collections import defaultdict
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from app.recommenders.collaborative.item_cosine import ItemCosineRecommender
from app.recommenders.collaborative.svd import SVDRecommender
from app.recommenders.collaborative.als import ALSRecommender

def calculate_ndcg(recommended_list, test_set, k):
    dcg = 0.0
    idcg = 0.0
    for i, item in enumerate(recommended_list[:k]):
        if item in test_set:
            dcg += 1.0 / math.log2(i + 2)
    for i in range(min(k, len(test_set))):
        idcg += 1.0 / math.log2(i + 2)
    return dcg / idcg if idcg > 0 else 0.0

def main():
    csv_path = os.path.join(os.path.dirname(__file__), '../../data/processed/master_ratings.csv')
    print(f"Loading data from {csv_path}...")
    
    # Load sample to speed up evaluation (e.g. 1M rows if large)
    df = pd.read_csv(
        csv_path, 
        usecols=['game_id', 'rating', 'user_id'],
        dtype={'game_id': 'int32', 'rating': 'float32', 'user_id': 'int32'}
    )
    df.rename(columns={'game_id': 'item', 'rating': 'rating', 'user_id': 'user'}, inplace=True)
    
    # Take a smaller sample of users for faster evaluation, or filter active users
    user_counts = df['user'].value_counts()
    active_users = user_counts[(user_counts >= 10) & (user_counts <= 100)].index
    
    # Sample 1000 active users for evaluation
    np.random.seed(42)
    eval_users = np.random.choice(active_users, 1000, replace=False)
    
    # The training set is everyone else PLUS the training portion of the eval_users
    # The test set is the test portion of the eval_users
    df_eval = df[df['user'].isin(eval_users)].copy()
    df_other = df[~df['user'].isin(eval_users)].copy()
    
    # Sort by user for train_test_split
    # We want 80/20 split per user for eval_users
    # To do this simply:
    train_eval_list = []
    test_eval_list = []
    
    # Fast grouped split
    for _, group in df_eval.groupby('user'):
        if len(group) < 2:
            train_eval_list.append(group)
            continue
        # Split 80/20
        train_grp, test_grp = train_test_split(group, test_size=0.2, random_state=42)
        train_eval_list.append(train_grp)
        test_eval_list.append(test_grp)
        
    df_train_eval = pd.concat(train_eval_list)
    df_test_eval = pd.concat(test_eval_list)
    
    df_train = pd.concat([df_other, df_train_eval])
    
    print(f"Total rows: {len(df)}")
    print(f"Train rows: {len(df_train)}")
    print(f"Test rows: {len(df_test_eval)} (from {len(eval_users)} eval users)")

    # Test sets per user: only considering likes >= 8.0 as relevant items
    test_likes = df_test_eval[df_test_eval['rating'] >= 8.0].groupby('user')['item'].apply(set).to_dict()
    # Filter eval_users to those who actually have relevant items in the test set
    eval_users_filtered = [u for u in eval_users if len(test_likes.get(u, set())) > 0]
    print(f"Valid eval users (with test likes): {len(eval_users_filtered)}")
    
    train_histories = df_train_eval[df_train_eval['rating'] >= 8.0].groupby('user')['item'].apply(set).to_dict()

    recommenders = [
        ItemCosineRecommender(min_shared_users=50),
        SVDRecommender(n_factors=50),
        ALSRecommender(factors=50, iterations=15, regularization=0.1)
    ]

    for recommender in recommenders:
        model_name = recommender.get_model_name()
        print(f"\nEvaluating {model_name}...")
        recommender.fit(df_train)
        
        precisions = []
        recalls = []
        ndcgs = []
        
        for u in eval_users_filtered:
            user_history = train_histories.get(u, set())
            if not user_history:
                continue
                
            # Aggregate scores for candidate items
            candidate_scores = defaultdict(float)
            for item in user_history:
                recs = recommender.recommend(item_id=item, limit=20)
                for rec in recs:
                    rec_item = rec['item_id']
                    if rec_item not in user_history:
                        candidate_scores[rec_item] += rec['score']
                        
            # Sort candidates
            top_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)[:10]
            top_items = [x[0] for x in top_candidates]
            
            test_set = test_likes[u]
            
            # Metrics @ 10
            k = 10
            hits = len(set(top_items) & test_set)
            precisions.append(hits / k)
            recalls.append(hits / len(test_set))
            ndcgs.append(calculate_ndcg(top_items, test_set, k))
            
        print(f"Metrics @ 10 for {model_name}:")
        print(f"Precision: {np.mean(precisions):.4f}")
        print(f"Recall:    {np.mean(recalls):.4f}")
        print(f"NDCG:      {np.mean(ndcgs):.4f}")

if __name__ == "__main__":
    main()
