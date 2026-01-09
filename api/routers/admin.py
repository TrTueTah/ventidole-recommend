"""
Admin endpoints for model management
"""
import logging
from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from api.services.model_manager import get_model_manager
from api.exceptions import ModelNotLoadedException

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


class ReloadResponse(BaseModel):
    """Response for model reload endpoint"""
    success: bool
    message: str
    details: Dict[str, Any]


@router.post(
    "/reload-model",
    response_model=ReloadResponse,
    status_code=status.HTTP_200_OK,
    summary="Reload recommendation model",
    description="Reload the recommendation model from disk if it has been updated. Enables hot-reloading without service restart."
)
async def reload_model() -> ReloadResponse:
    """
    Reload the recommendation model from disk.

    This endpoint checks if the model file has been modified since the last load.
    If modified, it reloads the model and all associated data (features, mappings, metadata).

    Returns:
        ReloadResponse with reload status and details

    Raises:
        HTTPException 503: If model reload fails
        HTTPException 500: For other internal errors

    Usage:
        - Call this endpoint after the cron job completes model training
        - The API will automatically detect the new model file and reload it
        - No service restart required

    Example:
        POST /admin/reload-model

        Response:
        {
          "success": true,
          "message": "Model reloaded successfully",
          "details": {
            "reloaded": true,
            "reason": "Model file modified",
            "previous_reload_time": "2025-12-24T10:00:00",
            "current_reload_time": "2025-12-24T10:05:00",
            "num_users": 500,
            "num_items": 2000
          }
        }
    """
    try:
        logger.info("Admin endpoint: Reload model requested")

        # Get model manager and trigger reload
        model_manager = get_model_manager()
        reload_info = model_manager.reload_model()

        if reload_info.get("reloaded"):
            message = "Model reloaded successfully"
            logger.info(message)
        else:
            message = "Model is already up to date"
            logger.info(message)

        return ReloadResponse(
            success=True,
            message=message,
            details=reload_info
        )

    except ModelNotLoadedException as e:
        logger.error(f"Model reload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Model reload failed",
                "error_code": "MODEL_RELOAD_ERROR",
                "error": str(e)
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error during model reload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error during model reload",
                "error_code": "INTERNAL_ERROR",
                "error": str(e)
            }
        )


@router.get(
    "/model-status",
    summary="Get model status",
    description="Get current status and metadata about the loaded model"
)
async def get_model_status() -> Dict[str, Any]:
    """
    Get current status of the loaded recommendation model.

    Returns detailed information about the model including:
    - Load status
    - Number of users and items
    - Model type
    - Last reload time
    - File path

    Returns:
        Dictionary with model status information

    Example:
        GET /admin/model-status

        Response:
        {
          "is_loaded": true,
          "num_users": 500,
          "num_items": 2000,
          "num_posts_metadata": 2000,
          "model_type": "LightFM",
          "model_path": "hybrid_model.pkl",
          "last_reload_time": "2025-12-24T10:05:00"
        }
    """
    try:
        model_manager = get_model_manager()
        status_info = model_manager.health_check()

        # Add file update check
        status_info["file_updated"] = model_manager.check_model_file_updated()

        return status_info

    except ModelNotLoadedException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Model not loaded",
                "error_code": "MODEL_NOT_LOADED",
                "error": str(e)
            }
        )
