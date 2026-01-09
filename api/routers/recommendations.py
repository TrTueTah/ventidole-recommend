"""
Recommendations endpoint
"""
import logging
from fastapi import APIRouter, Depends, Query, HTTPException, status

from api.schemas import RecommendationResponse
from api.services.recommendation_service import RecommendationService
from api.dependencies import get_recommendation_service
from api.exceptions import UserNotFoundException, NoRecommendationsException
from config import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)


@router.get(
    "/{user_id}",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendations for a user",
    description="Get paginated post recommendations for a specific user with infinite scroll support"
)
async def get_user_recommendations(
    user_id: str,
    limit: int = Query(
        default=DEFAULT_PAGE_LIMIT,
        ge=1,
        le=MAX_PAGE_LIMIT,
        description=f"Number of items per page (1-{MAX_PAGE_LIMIT})"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Pagination offset (0-based)"
    ),
    service: RecommendationService = Depends(get_recommendation_service)
) -> RecommendationResponse:
    """
    Generate personalized post recommendations for a user.

    Args:
        user_id: User ID to generate recommendations for
        limit: Number of items per page (default: 20, max: 100)
        offset: Pagination offset for infinite scroll (default: 0)
        service: Injected RecommendationService

    Returns:
        RecommendationResponse with paginated recommendations

    Raises:
        HTTPException 404: User not found in recommendation system
        HTTPException 500: Internal server error

    Example:
        GET /recommendations/abc123?limit=20&offset=0
        GET /recommendations/abc123?limit=20&offset=20  # Next page
        GET /recommendations/abc123?limit=20&offset=40  # Third page
    """
    try:
        logger.info(f"Recommendation request: user_id={user_id}, limit={limit}, offset={offset}")

        # Generate recommendations
        result = service.get_user_recommendations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        logger.info(f"Successfully generated {len(result.recommendations)} recommendations for user {user_id}")
        return result

    except UserNotFoundException as e:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": str(e),
                "error_code": "USER_NOT_FOUND",
                "user_id": user_id
            }
        )

    except NoRecommendationsException as e:
        # Return empty list instead of error for better UX
        logger.info(f"No recommendations available for user {user_id}")
        return RecommendationResponse(
            user_id=user_id,
            recommendations=[],
            pagination={
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False
            }
        )

    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error while generating recommendations",
                "error_code": "INTERNAL_ERROR"
            }
        )
