"""
Recommendation Service - Business logic for generating recommendations

Supports two strategies:
1. Cold-start: For new users with minimal interactions (uses community-first ranking)
2. Normal: For users with sufficient interactions (uses hybrid LightFM model)
"""
import logging
import numpy as np
from typing import List, Optional

from api.schemas import RecommendationResponse, PostRecommendation, PaginationMetadata
from api.exceptions import UserNotFoundException, NoRecommendationsException
from api.services.model_manager import ModelManager
from api.services.cold_start_strategy import UserState
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

        Automatically selects the appropriate strategy:
        - Cold-start: For new users with < threshold interactions
        - Normal (hybrid): For users with sufficient interaction history

        Args:
            user_id: User ID to generate recommendations for
            limit: Number of items per page
            offset: Pagination offset
            total_to_generate: Total recommendations to generate (defaults to TOP_K from config)

        Returns:
            RecommendationResponse with paginated recommendations

        Raises:
            UserNotFoundException: If user ID not found in system
            NoRecommendationsException: If no recommendations available
        """
        if total_to_generate is None:
            total_to_generate = TOP_K

        logger.info(f"Generating recommendations for user {user_id} (limit={limit}, offset={offset})")

        # 1. Check if user exists in system (not just in model)
        is_known = self.model_manager.is_known_user(user_id)
        is_in_model = self.model_manager.is_user_in_model(user_id)

        if not is_known:
            logger.warning(f"User {user_id} not found in system")
            raise UserNotFoundException(user_id)

        # 2. Determine user state and select strategy
        user_state = self.model_manager.get_user_state(user_id)
        logger.info(f"User {user_id} state: {user_state.value}, in_model: {is_in_model}")

        # 3. Route to appropriate strategy
        if user_state == UserState.COLD_START or not is_in_model:
            # Use cold-start strategy for new users or users not in model
            return self._get_cold_start_recommendations(
                user_id, limit, offset, total_to_generate
            )
        else:
            # Use hybrid model for users with sufficient interactions
            return self._get_hybrid_recommendations(
                user_id, limit, offset, total_to_generate
            )

    def _get_cold_start_recommendations(
        self,
        user_id: str,
        limit: int,
        offset: int,
        total_to_generate: int
    ) -> RecommendationResponse:
        """
        Generate recommendations using cold-start strategy.

        Uses community-first, content-aware, recency-aware ranking.

        Args:
            user_id: User ID
            limit: Page size
            offset: Pagination offset
            total_to_generate: Max recommendations to generate

        Returns:
            RecommendationResponse with cold-start recommendations
        """
        logger.info(f"Using COLD-START strategy for user {user_id}")

        cold_start = self.model_manager.get_cold_start_strategy()

        # Generate recommendations
        results, total_count = cold_start.get_cold_start_recommendations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        if not results and offset == 0:
            logger.warning(f"No cold-start recommendations available for user {user_id}")
            raise NoRecommendationsException(user_id)

        # Convert to response format
        recommendations: List[PostRecommendation] = []
        for post_id, score, metadata in results:
            recommendations.append(PostRecommendation(
                post_id=post_id,
                score=score,
                metadata=metadata
            ))

        # Effective total is min of generated and requested
        effective_total = min(total_count, total_to_generate)

        pagination = PaginationMetadata(
            total=effective_total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < effective_total
        )

        logger.info(f"Returning {len(recommendations)} cold-start recommendations for user {user_id}")

        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            pagination=pagination,
            strategy="cold_start"
        )

    def _get_hybrid_recommendations(
        self,
        user_id: str,
        limit: int,
        offset: int,
        total_to_generate: int
    ) -> RecommendationResponse:
        """
        Generate recommendations using hybrid LightFM model.

        Uses collaborative filtering + content-based features.

        Args:
            user_id: User ID
            limit: Page size
            offset: Pagination offset
            total_to_generate: Max recommendations to generate

        Returns:
            RecommendationResponse with hybrid model recommendations
        """
        logger.info(f"Using HYBRID strategy for user {user_id}")

        # Get user index (already validated to exist)
        user_idx = self.model_manager.get_user_index(user_id)

        # Get model and features
        model = self.model_manager.get_model()
        item_features = self.model_manager.get_item_features()
        num_items = self.model_manager.get_num_items()

        # Predict scores for ALL items
        logger.debug(f"Predicting scores for {num_items} items for user index {user_idx}")
        item_indices = np.arange(num_items)
        scores = model.predict(
            user_idx,
            item_indices,
            item_features=item_features
        )

        # Sort by score and get top-N
        top_indices = np.argsort(-scores)[:total_to_generate]
        logger.debug(f"Generated top-{total_to_generate} recommendations")

        # Apply pagination
        paginated_indices = top_indices[offset:offset + limit]

        if len(paginated_indices) == 0 and offset == 0:
            logger.warning(f"No recommendations available for user {user_id}")
            raise NoRecommendationsException(user_id)

        # Convert to post IDs and enrich with metadata
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

        # Build pagination metadata
        pagination = PaginationMetadata(
            total=total_to_generate,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total_to_generate
        )

        logger.info(f"Returning {len(recommendations)} hybrid recommendations for user {user_id}")

        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            pagination=pagination,
            strategy="hybrid"
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
