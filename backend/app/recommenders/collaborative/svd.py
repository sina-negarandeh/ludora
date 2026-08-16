import numpy as np
import pandas as pd
import pickle
import os
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any
from app.recommenders.base import BaseRecommender

class SVDRecommender(BaseRecommender):
    def __init__(self, n_factors: int = 50):
        self.n_factors = n_factors
        self.item_embeddings = None
        self.item_idx_to_id = {}
        self.item_id_to_idx = {}

    def fit(self, df: pd.DataFrame) -> None:
        """
        df must have 'user', 'item', 'rating' columns.
        """
        user_ids = df['user'].astype('category')
        item_ids = df['item'].astype('category')

        self.item_idx_to_id = dict(enumerate(item_ids.cat.categories))
        self.item_id_to_idx = {v: k for k, v in self.item_idx_to_id.items()}

        row_indices = user_ids.cat.codes
        col_indices = item_ids.cat.codes
        ratings = df['rating'].values

        n_users = len(user_ids.cat.categories)
        n_items = len(item_ids.cat.categories)

        # User-Item Sparse Matrix
        # shape: (n_users, n_items)
        ui_matrix = csr_matrix((ratings, (row_indices, col_indices)), shape=(n_users, n_items))

        # Perform Truncated SVD on the Item-User matrix (n_items, n_users)
        # This will give us item embeddings directly
        svd = TruncatedSVD(n_components=self.n_factors, random_state=42)
        self.item_embeddings = svd.fit_transform(ui_matrix.T)

    def recommend(self, item_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        if self.item_embeddings is None:
            raise ValueError("Model has not been fitted.")

        if item_id not in self.item_id_to_idx:
            return []

        idx = self.item_id_to_idx[item_id]
        
        # Calculate cosine similarity with all other items
        query_vector = self.item_embeddings[idx].reshape(1, -1)
        sim_scores = cosine_similarity(query_vector, self.item_embeddings).flatten()
        
        # Zero out self similarity
        sim_scores[idx] = -1.0
        
        # Sort descending
        top_indices = np.argsort(-sim_scores)[:limit]

        results = []
        for i in top_indices:
            if sim_scores[i] <= 0:
                continue
            results.append({
                'item_id': self.item_idx_to_id[i],
                'score': float(sim_scores[i])
            })
            
        return results

    def get_model_name(self) -> str:
        return 'cf_svd'

    def save(self, filepath: str) -> None:
        if self.item_embeddings is None:
            raise ValueError("Cannot save an unfitted model.")
        with open(filepath, 'wb') as f:
            pickle.dump({
                'n_factors': self.n_factors,
                'item_embeddings': self.item_embeddings,
                'item_idx_to_id': self.item_idx_to_id,
                'item_id_to_idx': self.item_id_to_idx
            }, f)

    def load(self, filepath: str) -> None:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file {filepath} not found.")
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.n_factors = data['n_factors']
            self.item_embeddings = data['item_embeddings']
            self.item_idx_to_id = data['item_idx_to_id']
            self.item_id_to_idx = data['item_id_to_idx']
