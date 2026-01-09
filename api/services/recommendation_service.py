"""
Recommendation Service - Business logic for generating recommendations
"""
import logging
import numpy as np
from typing import List

from api.schemas import RecommendationResponse, PostRecommendation, PaginationMetadata
from api.exceptions import UserNotFoundException, NoRecommendationsException
from api.services.model_manager import ModelManager
from config import TOP_K

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service for generating paginated recommendations for users.
    """

    def __init__(self, model_manager: ModelManager):
        """
        Initialize recommendation service.

        Args:
            model_manager: ModelManager instance with loaded model
        """
        self.model_manager = model_manager

    def get_user_recommendations(
        self,
        user_id: str,
        limit: int,
        offset: int,
        total_to_generate: int = None
    ) -> RecommendationResponse:
        """
        Generate paginated recommendations for a user.

        Args:
            user_id: User ID to generate recommendations for
            limit: Number of items per page
            offset: Pagination offset
            total_to_generate: Total recommendations to generate (defaults to TOP_K from config)

        Returns:
            RecommendationResponse with paginated recommendations

        Raises:
            UserNotFoundException: If user ID not found in training data
            NoRecommendationsException: If no recommendations available
        """
        if total_to_generate is None:
            total_to_generate = TOP_K

        logger.info(f"Generating recommendations for user {user_id} (limit={limit}, offset={offset})")

        # 1. Validate user exists
        user_idx = self.model_manager.get_user_index(user_id)
        if user_idx is None:
            logger.warning(f"User {user_id} not found in recommendation system")
            raise UserNotFoundException(user_id)

        # 2. Get model and features
        model = self.model_manager.get_model()
        item_features = self.model_manager.get_item_features()
        num_items = self.model_manager.get_num_items()

        # 3. Predict scores for ALL items
        logger.debug(f"Predicting scores for {num_items} items for user index {user_idx}")
        item_indices = np.arange(num_items)
        scores = model.predict(
            user_idx,
            item_indices,
            item_features=item_features
        )

        # 4. Sort by score and get top-N
        top_indices = np.argsort(-scores)[:total_to_generate]
        logger.debug(f"Generated top-{total_to_generate} recommendations")

        # 5. Apply pagination
        paginated_indices = top_indices[offset:offset + limit]

        if len(paginated_indices) == 0 and offset == 0:
            logger.warning(f"No recommendations available for user {user_id}")
            raise NoRecommendationsException(user_id)

        # 6. Convert to post IDs and enrich with metadata
        recommendations: List[PostRecommendation] = []
        for idx in paginated_indices:
            post_id = self.model_manager.get_post_id(idx)
            if post_id is None:
                logger.warning(f"Could not find post ID for item index {idx}")
                continue

            score = float(scores[idx])
            metadata = self.model_manager.get_post_metadata(post_id)

            recommendations.append(PostRecommendation(
                post_id=post_id,
                score=score,
                metadata=metadata
            ))

        # 7. Build pagination metadata
        pagination = PaginationMetadata(
            total=total_to_generate,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total_to_generate
        )

        logger.info(f"Returning {len(recommendations)} recommendations for user {user_id}")

        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            pagination=pagination
        )

    def get_similar_items(self, item_id: str, limit: int = 10) -> List[PostRecommendation]:
        """
        Get similar items to a given item (future enhancement).

        Args:
            item_id: Item ID to find similar items for
            limit: Number of similar items to return

        Returns:
            List of similar items

        Note:
            This is a placeholder for future implementation.
            Could use item embeddings to compute cosine similarity.
        """
        raise NotImplementedError("Similar items feature not yet implemented")
