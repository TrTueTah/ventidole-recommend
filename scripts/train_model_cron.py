#!/usr/bin/env python3
"""
Automated Model Training Script for Cron Job
Retrains the recommendation model with latest data and replaces the model file atomically.
"""
import os
import sys
import logging
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import fcntl

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.load_data import load_users, load_posts, load_interactions, load_community_followers
from data.preprocess import build_dataset
from models.hybrid_lightfm import train_hybrid
from storage.save_load import save_model
from config import MODEL_PATH

# Configuration
LOCK_FILE = "/tmp/model_training.lock"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "training.log"
MODEL_DIR = Path(__file__).parent.parent
TEMP_MODEL_PREFIX = "hybrid_model_temp_"

# Setup logging
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TrainingLock:
    """Context manager for preventing concurrent training runs"""
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_fd = None

    def __enter__(self):
        self.lock_fd = open(self.lock_file, 'w')
        try:
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired training lock: {self.lock_file}")
            return self
        except IOError:
            logger.warning("Another training process is already running. Exiting.")
            sys.exit(0)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_fd:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            self.lock_fd.close()
            logger.info("Released training lock")


def train_model():
    """
    Main training function with error handling and atomic model replacement.

    Returns:
        bool: True if training succeeded, False otherwise
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"Starting model training at {start_time.isoformat()}")
    logger.info("=" * 80)

    try:
        # Step 1: Load data from database
        logger.info("Step 1/5: Loading data from database...")
        users_df = load_users()
        posts_df = load_posts()
        interactions_df = load_interactions()
        community_followers_df = load_community_followers()

        logger.info(f"Loaded {len(users_df)} users, {len(posts_df)} posts, "
                   f"{len(interactions_df)} interactions, {len(community_followers_df)} followers")

        # Step 2: Build dataset and feature matrices
        logger.info("Step 2/5: Building dataset and feature matrices...")
        dataset, interactions, weights, user_feat_matrix, item_feat_matrix = build_dataset(
            users_df, posts_df, interactions_df, community_followers_df
        )
        logger.info(f"Dataset built: {user_feat_matrix.shape[0]} users, {item_feat_matrix.shape[0]} items")

        # Step 3: Train the model
        logger.info("Step 3/5: Training hybrid LightFM model...")
        model = train_hybrid(
            interactions,
            weights,
            user_feat_matrix,
            item_feat_matrix,
            epochs=30
        )
        logger.info("Model training completed successfully")

        # Step 4: Save model to temporary file
        logger.info("Step 4/5: Saving model and dataset to temporary file...")
        with tempfile.NamedTemporaryFile(
            mode='wb',
            prefix=TEMP_MODEL_PREFIX,
            suffix='.pkl',
            dir=MODEL_DIR,
            delete=False
        ) as temp_file:
            temp_model_path = temp_file.name
            logger.info(f"Temporary model path: {temp_model_path}")

        save_model(model, temp_model_path, dataset=dataset)
        logger.info(f"Model and dataset saved to temporary file: {temp_model_path}")

        # Step 5: Atomic replacement - rename temp file to final path
        logger.info("Step 5/5: Performing atomic model replacement...")
        final_model_path = MODEL_DIR / MODEL_PATH

        # Backup old model if it exists
        if final_model_path.exists():
            backup_path = MODEL_DIR / f"hybrid_model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            shutil.copy2(final_model_path, backup_path)
            logger.info(f"Backed up old model to: {backup_path}")

            # Clean up old backups (keep only last 5)
            cleanup_old_backups(MODEL_DIR, keep=5)

        # Atomic rename (replaces old file)
        shutil.move(temp_model_path, final_model_path)
        logger.info(f"Model replaced atomically: {final_model_path}")

        # Calculate training duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"Training completed successfully in {duration:.2f} seconds")
        logger.info(f"Model saved to: {final_model_path}")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"Training failed with error: {str(e)}", exc_info=True)

        # Clean up temp file if it exists
        if 'temp_model_path' in locals() and os.path.exists(temp_model_path):
            os.remove(temp_model_path)
            logger.info(f"Cleaned up temporary file: {temp_model_path}")

        return False


def cleanup_old_backups(directory: Path, keep: int = 5):
    """
    Remove old backup files, keeping only the most recent ones.

    Args:
        directory: Directory containing backup files
        keep: Number of recent backups to keep
    """
    backup_pattern = "hybrid_model_backup_*.pkl"
    backups = sorted(
        directory.glob(backup_pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    # Remove old backups beyond the keep limit
    for old_backup in backups[keep:]:
        try:
            old_backup.unlink()
            logger.info(f"Removed old backup: {old_backup}")
        except Exception as e:
            logger.warning(f"Failed to remove old backup {old_backup}: {e}")


def main():
    """Main entry point for cron job"""
    # Prevent concurrent training runs
    with TrainingLock(LOCK_FILE):
        success = train_model()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
