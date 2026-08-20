from typing import Any

import implicit
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity

from app.core.ml_config import RANDOM_SEED, RecommenderConfig
from app.recommenders.base import BaseRecommender


class ALSRecommender(BaseRecommender):
    def __init__(
        self,
        factors: int = RecommenderConfig.CF_ALS_FACTORS,
        iterations: int = RecommenderConfig.CF_ALS_ITERATIONS,
        regularization: float = RecommenderConfig.CF_ALS_REGULARIZATION,
        confidence_alpha: float = RecommenderConfig.CF_ALS_CONFIDENCE_ALPHA,
    ):
        self.factors = factors
        self.iterations = iterations
        self.regularization = regularization
        self.confidence_alpha = confidence_alpha
        self.item_factors = None
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

        # implicit.als expects confidence weights (Hu/Koren/Volinsky 2008:
        # confidence = 1 + alpha*r), not raw preference values -- passing
        # the raw 1-10 rating straight through would read a low rating as
        # "low-confidence positive" instead of "confident dislike", since
        # implicit feedback has no concept of a negative observation.
        confidence = 1.0 + self.confidence_alpha * df['rating'].values

        n_users = len(user_ids.cat.categories)
        n_items = len(item_ids.cat.categories)

        # Implicit ALS >= 0.7 expects user-item matrix for training
        # We'll create the user-item matrix:
        user_item_matrix = csr_matrix((confidence, (row_indices, col_indices)), shape=(n_users, n_items))

        model = implicit.als.AlternatingLeastSquares(
            factors=self.factors,
            regularization=self.regularization,
            iterations=self.iterations,
            random_state=RANDOM_SEED
        )
        
        # Fit the model
        model.fit(user_item_matrix)
        
        # The item factors represent our game embeddings
        self.item_factors = model.item_factors

    def recommend(self, item_id: int, limit: int = 10) -> list[dict[str, Any]]:
        if self.item_factors is None:
            raise ValueError("Model has not been fitted.")

        if item_id not in self.item_id_to_idx:
            return []

        idx = self.item_id_to_idx[item_id]
        
        # Calculate cosine similarity with all other items using the latent factors
        query_vector = self.item_factors[idx].reshape(1, -1)
        sim_scores = cosine_similarity(query_vector, self.item_factors).flatten()
        
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
        return 'cf_als'
