import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any
from app.recommenders.base import BaseRecommender

class ItemCosineRecommender(BaseRecommender):
    def __init__(self, min_shared_users: int = 50):
        self.min_shared_users = min_shared_users
        self.item_sim_matrix = None
        self.item_idx_to_id = {}
        self.item_id_to_idx = {}

    def fit(self, df: pd.DataFrame) -> None:
        """
        df must have 'user', 'item', 'rating' columns.
        """
        # Map user/item IDs to contiguous indices
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

        # To enforce minimum shared users, we can compute the dot product of a binary occurrence matrix.
        # This gives us the count of users who rated both item i and item j.
        binary_matrix = ui_matrix.copy()
        binary_matrix.data = np.ones_like(binary_matrix.data)
        
        # Co-occurrence matrix: item x item (number of shared users)
        co_occurrences = binary_matrix.T.dot(binary_matrix)

        # Compute cosine similarity on the actual ratings
        # Item-Item similarity matrix
        sim_matrix = cosine_similarity(ui_matrix.T, dense_output=False)

        # Apply minimum shared users threshold
        # Since sim_matrix and co_occurrences are both sparse, we can multiply them after zeroing out
        # pairs with less than min_shared_users
        
        # Create a mask of valid pairs
        valid_mask = co_occurrences >= self.min_shared_users
        
        # Element-wise multiply the sim_matrix with the valid mask
        self.item_sim_matrix = sim_matrix.multiply(valid_mask)
        
        # Zero out diagonal (self similarity)
        self.item_sim_matrix.setdiag(0)

    def recommend(self, item_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        if self.item_sim_matrix is None:
            raise ValueError("Model has not been fitted.")

        if item_id not in self.item_id_to_idx:
            return []

        idx = self.item_id_to_idx[item_id]
        row = self.item_sim_matrix.getrow(idx)
        
        # If the row is empty (no valid similarities), return empty
        if row.nnz == 0:
            return []

        # Get indices and scores
        indices = row.indices
        scores = row.data
        
        # Sort by score descending
        sorted_items = np.argsort(-scores)
        top_k = sorted_items[:limit]

        results = []
        for i in top_k:
            results.append({
                'item_id': self.item_idx_to_id[indices[i]],
                'score': float(scores[i])
            })
            
        return results

    def get_model_name(self) -> str:
        return 'cf_item_cosine'
