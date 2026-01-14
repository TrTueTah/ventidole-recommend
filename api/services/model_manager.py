"""
Model Manager - Handles loading and caching of the recommendation model and features
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, Set
import numpy as np
from scipy.sparse import csr_matrix
from lightfm import LightFM
from lightfm.data import Dataset

# Import from existing modules
from data.load_data import (
    load_users, load_posts, load_interactions, load_community_followers,
    load_posts_with_engagement, load_user_interaction_counts, load_community_dominant_tags,
    check_user_exists, load_user_followed_communities
)
from data.preprocess import build_dataset
from storage.save_load import load_model
from config import MODEL_PATH
from api.exceptions import ModelNotLoadedException
from api.services.cold_start_strategy import ColdStartStrategy, UserState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelManager:
    """
    Manages the lifecycle of the recommendation model and associated data.
    Loads model and feature matrices at startup and provides thread-safe access.
    """

    def __init__(self):
        self.model: Optional[LightFM] = None
        self.dataset: Optional[Dataset] = None
        self.user_features: Optional[csr_matrix] = None
        self.item_features: Optional[csr_matrix] = None
        self.user_to_idx: Dict[str, int] = {}
        self.idx_to_user: Dict[int, str] = {}
        self.item_to_idx: Dict[str, int] = {}
        self.idx_to_item: Dict[int, str] = {}
        self.posts_metadata: Dict[str, Dict[str, Any]] = {}
        self.is_loaded: bool = False
        self.model_path: Optional[str] = None
        self.model_mtime: Optional[float] = None  # Model file modification time
        self.last_reload_time: Optional[datetime] = None

        # Cold-start strategy
        self.cold_start_strategy: Optional[ColdStartStrategy] = None
        self.user_followed_communities: Dict[str, Set[str]] = {}
        self.all_users: Set[str] = set()  # All known users (including those without interactions)

    def load_recommendation_model(self, model_path: str = None) -> None:
        """
        Load the trained model and build feature matrices.
        This should be called once at application startup.

        Args:
            model_path: Path to the trained model file. Defaults to MODEL_PATH from config.

        Raises:
            ModelNotLoadedException: If model loading fails
        """
        if model_path is None:
            model_path = MODEL_PATH

        try:
            logger.info(f"Loading recommendation model from {model_path}...")

            # 1. Load the trained model, dataset, and feature matrices
            self.model, saved_dataset, saved_user_features, saved_item_features = load_model(model_path)
            logger.info("Model loaded successfully")

            # 2. Load data from PostgreSQL (for metadata and cold-start)
            logger.info("Loading data from database...")
            users_df = load_users()
            posts_df = load_posts()
            interactions_df = load_interactions()
            community_followers_df = load_community_followers()
            logger.info(f"Loaded {len(users_df)} users, {len(posts_df)} posts, {len(interactions_df)} interactions")

            # Store all known users
            self.all_users = set(users_df['id'].tolist())

            # 3. Use saved dataset and feature matrices for consistency
            # If they were saved with model, use them directly to avoid feature mismatch
            # Otherwise, rebuild from current data (backward compatibility)
            if saved_dataset is not None and saved_user_features is not None and saved_item_features is not None:
                logger.info("Using saved dataset and feature matrices for consistent inference...")
                self.dataset = saved_dataset
                self.user_features = saved_user_features
                self.item_features = saved_item_features
            else:
                logger.info("Building feature matrices from current data (legacy model)...")
                self.dataset, interactions, weights, self.user_features, self.item_features = build_dataset(
                    users_df, posts_df, interactions_df, community_followers_df
                )
            logger.info(f"Feature matrices loaded: user_features shape={self.user_features.shape}, item_features shape={self.item_features.shape}")

            # 4. Extract mappings from dataset
            logger.info("Extracting ID mappings...")
            user_mapping, _, item_mapping, _ = self.dataset.mapping()

            # Convert to internal dictionaries
            self.user_to_idx = user_mapping
            self.item_to_idx = item_mapping
            self.idx_to_user = {v: k for k, v in user_mapping.items()}
            self.idx_to_item = {v: k for k, v in item_mapping.items()}

            logger.info(f"Mappings created: {len(self.user_to_idx)} users, {len(self.item_to_idx)} items")

            # 5. Cache post metadata for enrichment
            logger.info("Caching post metadata...")
            self.posts_metadata = {}
            for _, row in posts_df.iterrows():
                post_id = row['id']
                self.posts_metadata[post_id] = {
                    'metadata': row.get('metadata', {}),
                    'communityId': row.get('communityId')
                }
            logger.info(f"Cached metadata for {len(self.posts_metadata)} posts")

            # 6. Initialize cold-start strategy
            logger.info("Initializing cold-start strategy...")
            self._initialize_cold_start_strategy(community_followers_df)
            logger.info("Cold-start strategy initialized")

            # Track model file info for reload detection
            self.model_path = model_path
            if os.path.exists(model_path):
                self.model_mtime = os.path.getmtime(model_path)
            self.last_reload_time = datetime.now()

            # Mark as loaded
            self.is_loaded = True
            logger.info("Model manager initialization complete")

        except FileNotFoundError as e:
            error_msg = f"Model file not found: {model_path}"
            logger.error(error_msg)
            raise ModelNotLoadedException(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load model: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ModelNotLoadedException(error_msg) from e

    def _initialize_cold_start_strategy(self, community_followers_df) -> None:
        """
        Initialize the cold-start strategy with required data.

        Args:
            community_followers_df: DataFrame with userId, communityId columns
        """
        # Create cold-start strategy instance
        self.cold_start_strategy = ColdStartStrategy()

        # Build user -> followed communities mapping
        self.user_followed_communities = {}
        for _, row in community_followers_df.iterrows():
            user_id = row['userId']
            community_id = row['communityId']
            if user_id not in self.user_followed_communities:
                self.user_followed_communities[user_id] = set()
            self.user_followed_communities[user_id].add(community_id)

        # Load additional data for cold-start
        try:
            # User interaction counts
            interaction_counts_df = load_user_interaction_counts()
            user_interaction_counts = dict(zip(
                interaction_counts_df['user_id'],
                interaction_counts_df['interaction_count']
            ))
        except Exception as e:
            logger.warning(f"Failed to load interaction counts: {e}, using empty dict")
            user_interaction_counts = {}

        try:
            # Community dominant tags
            tags_df = load_community_dominant_tags()
            community_dominant_tags: Dict[str, Dict[str, int]] = {}
            for _, row in tags_df.iterrows():
                comm_id = row['communityId']
                if comm_id not in community_dominant_tags:
                    community_dominant_tags[comm_id] = {}
                community_dominant_tags[comm_id][row['tag']] = row['tag_count']
        except Exception as e:
            logger.warning(f"Failed to load community tags: {e}, using empty dict")
            community_dominant_tags = {}

        try:
            # Posts with engagement data
            posts_engagement_df = load_posts_with_engagement()
            posts_data: Dict[str, Dict[str, Any]] = {}
            for _, row in posts_engagement_df.iterrows():
                post_id = row['id']
                posts_data[post_id] = {
                    'metadata': row.get('metadata', {}),
                    'communityId': row.get('communityId'),
                    'createdAt': row.get('createdAt'),
                    'view_count': row.get('view_count', 0) or 0,
                    'like_count': row.get('like_count', 0) or 0,
                    'comment_count': row.get('comment_count', 0) or 0
                }
        except Exception as e:
            logger.warning(f"Failed to load posts engagement: {e}, using basic metadata")
            posts_data = self.posts_metadata.copy()

        # Load data into cold-start strategy
        self.cold_start_strategy.load_data(
            user_interaction_counts=user_interaction_counts,
            user_followed_communities=self.user_followed_communities,
            community_dominant_tags=community_dominant_tags,
            posts_data=posts_data
        )

    def get_cold_start_strategy(self) -> ColdStartStrategy:
        """Get the cold-start strategy instance."""
        if not self.is_loaded or self.cold_start_strategy is None:
            raise ModelNotLoadedException("Cold-start strategy not initialized")
        return self.cold_start_strategy

    def get_user_state(self, user_id: str) -> UserState:
        """
        Determine if a user is in cold-start or normal state.

        Args:
            user_id: User ID to check

        Returns:
            UserState.COLD_START or UserState.NORMAL
        """
        if self.cold_start_strategy is None:
            raise ModelNotLoadedException("Cold-start strategy not initialized")
        return self.cold_start_strategy.detect_user_state(user_id)

    def is_known_user(self, user_id: str) -> bool:
        """
        Check if user exists in the system (even if not in training data).
        Falls back to database check for users created after startup.

        Args:
            user_id: User ID to check

        Returns:
            True if user exists in database
        """
        # First check cached users
        if user_id in self.all_users:
            return True

        # Fall back to database check for new users created after startup
        try:
            exists = check_user_exists(user_id)
            if exists:
                # Add to cache for future requests
                self.all_users.add(user_id)
                logger.info(f"New user {user_id} found in database, added to cache")
            return exists
        except Exception as e:
            logger.error(f"Error checking user existence in database: {e}")
            return False

    def is_user_in_model(self, user_id: str) -> bool:
        """
        Check if user exists in the trained model.

        Args:
            user_id: User ID to check

        Returns:
            True if user is in the model's training data
        """
        return user_id in self.user_to_idx

    def get_model(self) -> LightFM:
        """Get the loaded model"""
        if not self.is_loaded or self.model is None:
            raise ModelNotLoadedException("Model is not loaded")
        return self.model

    def get_user_features(self) -> csr_matrix:
        """Get user feature matrix"""
        if not self.is_loaded or self.user_features is None:
            raise ModelNotLoadedException("User features not loaded")
        return self.user_features

    def get_item_features(self) -> csr_matrix:
        """Get item feature matrix"""
        if not self.is_loaded or self.item_features is None:
            raise ModelNotLoadedException("Item features not loaded")
        return self.item_features

    def get_user_index(self, user_id: str) -> Optional[int]:
        """
        Get internal index for a user ID.

        Args:
            user_id: User ID to lookup

        Returns:
            Internal index or None if user not found
        """
        return self.user_to_idx.get(user_id)

    def get_post_id(self, item_index: int) -> Optional[str]:
        """
        Get post ID from internal item index.

        Args:
            item_index: Internal item index

        Returns:
            Post ID or None if index not found
        """
        return self.idx_to_item.get(item_index)

    def get_post_metadata(self, post_id: str) -> Dict[str, Any]:
        """
        Get metadata for a post.

        Args:
            post_id: Post ID

        Returns:
            Post metadata dictionary (empty dict if not found)
        """
        return self.posts_metadata.get(post_id, {})

    def get_num_items(self) -> int:
        """Get total number of items in the system"""
        if not self.is_loaded:
            raise ModelNotLoadedException("Model not loaded")
        return len(self.item_to_idx)

    def get_num_users(self) -> int:
        """Get total number of users in the system"""
        if not self.is_loaded:
            raise ModelNotLoadedException("Model not loaded")
        return len(self.user_to_idx)

    def health_check(self) -> Dict[str, Any]:
        """
        Check health status of the model manager.

        Returns:
            Dictionary with health check information
        """
        cold_start_info = {}
        if self.cold_start_strategy:
            cold_start_info = {
                "users_with_interactions": len(self.cold_start_strategy.user_interaction_counts),
                "users_with_followed_communities": len(self.cold_start_strategy.user_followed_communities),
                "communities_with_tags": len(self.cold_start_strategy.community_dominant_tags),
                "posts_with_engagement": len(self.cold_start_strategy.posts_data)
            }

        return {
            "is_loaded": self.is_loaded,
            "num_users": len(self.user_to_idx) if self.is_loaded else 0,
            "num_all_users": len(self.all_users) if self.is_loaded else 0,
            "num_items": len(self.item_to_idx) if self.is_loaded else 0,
            "num_posts_metadata": len(self.posts_metadata) if self.is_loaded else 0,
            "model_type": type(self.model).__name__ if self.model else None,
            "model_path": self.model_path,
            "last_reload_time": self.last_reload_time.isoformat() if self.last_reload_time else None,
            "cold_start_strategy": cold_start_info
        }

    def check_model_file_updated(self) -> bool:
        """
        Check if the model file has been updated on disk.

        Returns:
            True if model file has been modified since last load, False otherwise
        """
        if not self.model_path or not os.path.exists(self.model_path):
            return False

        current_mtime = os.path.getmtime(self.model_path)
        if self.model_mtime is None:
            return True

        return current_mtime > self.model_mtime

    def reload_model(self) -> Dict[str, Any]:
        """
        Reload the model from disk if it has been updated.
        This enables hot-reloading without restarting the API.

        Returns:
            Dictionary with reload status information

        Raises:
            ModelNotLoadedException: If model reload fails
        """
        logger.info("Checking if model needs reloading...")

        if not self.model_path:
            raise ModelNotLoadedException("No model path configured")

        # Check if file has been updated
        if not self.check_model_file_updated():
            logger.info("Model file has not changed, skipping reload")
            return {
                "reloaded": False,
                "reason": "Model file not modified",
                "last_reload_time": self.last_reload_time.isoformat() if self.last_reload_time else None
            }

        logger.info(f"Model file has been updated, reloading from {self.model_path}...")
        old_reload_time = self.last_reload_time

        try:
            # Reload the model using the existing load method
            self.load_recommendation_model(self.model_path)

            logger.info("Model reloaded successfully")
            return {
                "reloaded": True,
                "reason": "Model file modified",
                "previous_reload_time": old_reload_time.isoformat() if old_reload_time else None,
                "current_reload_time": self.last_reload_time.isoformat() if self.last_reload_time else None,
                "num_users": self.get_num_users(),
                "num_items": self.get_num_items()
            }

        except Exception as e:
            logger.error(f"Failed to reload model: {str(e)}", exc_info=True)
            raise ModelNotLoadedException(f"Model reload failed: {str(e)}") from e


# Global singleton instance (will be initialized at app startup)
_model_manager_instance: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """
    Get the global model manager instance.
    This is used for dependency injection in FastAPI endpoints.
    """
    global _model_manager_instance
    if _model_manager_instance is None:
        raise ModelNotLoadedException("Model manager not initialized")
    return _model_manager_instance


def initialize_model_manager(model_path: str = None) -> ModelManager:
    """
    Initialize the global model manager instance.
    Should be called once at application startup.

    Args:
        model_path: Path to model file

    Returns:
        Initialized ModelManager instance
    """
    global _model_manager_instance
    _model_manager_instance = ModelManager()
    _model_manager_instance.load_recommendation_model(model_path)
    return _model_manager_instance
