"""
Dependency injection functions for FastAPI endpoints
"""
from functools import lru_cache
from api.services.model_manager import get_model_manager, ModelManager
from api.services.recommendation_service import RecommendationService


@lru_cache()
def get_recommendation_service() -> RecommendationService:
    """
    Get or create a RecommendationService instance.
    Uses lru_cache to ensure singleton pattern.

    Returns:
        RecommendationService instance

    Usage in endpoint:
        @app.get("/recommendations/{user_id}")
        def get_recs(user_id: str, service: RecommendationService = Depends(get_recommendation_service)):
            return service.get_user_recommendations(user_id, limit=20, offset=0)
    """
    model_manager = get_model_manager()
    return RecommendationService(model_manager)
