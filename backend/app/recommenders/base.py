from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseRecommender(ABC):
    @abstractmethod
    def fit(self, df) -> None:
        """
        Train or prepare the recommender model with data.
        df: A pandas DataFrame containing at minimum user, item, and rating.
        """
        pass

    @abstractmethod
    def recommend(self, item_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return top N similar items for a given item_id.
        Returns a list of dicts: [{'item_id': int, 'score': float}, ...]
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Return the unique identifier for this model (e.g., 'cf_item_cosine')
        """
        pass
