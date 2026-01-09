"""
Model Manager - Handles loading and caching of the recommendation model and features
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import numpy as np
from scipy.sparse import csr_matrix
from lightfm import LightFM
from lightfm.data import Dataset

# Import from existing modules
from data.load_data import load_users, load_posts, load_interactions, load_community_followers
from data.preprocess import build_dataset
from storage.save_load import load_model
from config import MODEL_PATH
from api.exceptions import ModelNotLoadedException

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

            # 2. Load data from PostgreSQL (only for metadata)
            logger.info("Loading data from database...")
            users_df = load_users()
            posts_df = load_posts()
            interactions_df = load_interactions()
            community_followers_df = load_community_followers()
            logger.info(f"Loaded {len(users_df)} users, {len(posts_df)} posts, {len(interactions_df)} interactions")

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
        return {
            "is_loaded": self.is_loaded,
            "num_users": len(self.user_to_idx) if self.is_loaded else 0,
            "num_items": len(self.item_to_idx) if self.is_loaded else 0,
            "num_posts_metadata": len(self.posts_metadata) if self.is_loaded else 0,
            "model_type": type(self.model).__name__ if self.model else None,
            "model_path": self.model_path,
            "last_reload_time": self.last_reload_time.isoformat() if self.last_reload_time else None
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
