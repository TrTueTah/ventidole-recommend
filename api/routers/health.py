"""
Health check endpoint
"""
import logging
import time
from datetime import datetime
from fastapi import APIRouter, status
import psycopg2

from api.schemas import HealthResponse, HealthCheck
from api.services.model_manager import get_model_manager
from api.exceptions import ModelNotLoadedException
from config import DB_CONFIG

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Check the health status of the recommendation service"
)
async def health_check() -> HealthResponse:
    """
    Perform health checks on critical system components.

    Returns:
        HealthResponse with overall status and individual check results

    Health Check Components:
        - model: Verify model is loaded and accessible
        - database: Verify database connectivity
        - features: Verify feature matrices are loaded
    """
    checks = {}

    # 1. Check model availability
    checks["model"] = _check_model_loaded()

    # 2. Check database connectivity
    checks["database"] = await _check_database_connection()

    # 3. Check feature matrices
    checks["features"] = _check_feature_matrices()

    # 4. Determine overall status
    overall_status = _determine_overall_status(checks)

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        checks=checks
    )


def _check_model_loaded() -> HealthCheck:
    """Check if the recommendation model is loaded"""
    start_time = time.time()
    try:
        model_manager = get_model_manager()
        health_info = model_manager.health_check()

        if health_info["is_loaded"]:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                status="healthy",
                message=f"Model loaded successfully ({health_info['model_type']})",
                response_time_ms=response_time_ms
            )
        else:
            return HealthCheck(
                status="unhealthy",
                message="Model is not loaded",
                response_time_ms=None
            )
    except ModelNotLoadedException as e:
        return HealthCheck(
            status="unhealthy",
            message=f"Model not loaded: {str(e)}",
            response_time_ms=None
        )
    except Exception as e:
        logger.error(f"Model health check failed: {str(e)}", exc_info=True)
        return HealthCheck(
            status="unhealthy",
            message=f"Model check error: {str(e)}",
            response_time_ms=None
        )


async def _check_database_connection() -> HealthCheck:
    """Check database connectivity"""
    start_time = time.time()
    conn = None
    try:
        # Attempt to connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Execute a simple query
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()

        response_time_ms = (time.time() - start_time) * 1000

        # Determine status based on response time
        if response_time_ms < 100:
            status_str = "healthy"
            message = "Database connection active"
        elif response_time_ms < 500:
            status_str = "degraded"
            message = "Database connection slow"
        else:
            status_str = "degraded"
            message = "Database connection very slow"

        return HealthCheck(
            status=status_str,
            message=message,
            response_time_ms=response_time_ms
        )
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        return HealthCheck(
            status="unhealthy",
            message=f"Database connection failed: {str(e)}",
            response_time_ms=None
        )
    finally:
        if conn:
            conn.close()


def _check_feature_matrices() -> HealthCheck:
    """Check if feature matrices are loaded"""
    start_time = time.time()
    try:
        model_manager = get_model_manager()
        health_info = model_manager.health_check()

        num_users = health_info.get("num_users", 0)
        num_items = health_info.get("num_items", 0)

        if num_users > 0 and num_items > 0:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                status="healthy",
                message=f"Features loaded ({num_users} users, {num_items} items)",
                response_time_ms=response_time_ms
            )
        else:
            return HealthCheck(
                status="unhealthy",
                message="Feature matrices not loaded",
                response_time_ms=None
            )
    except Exception as e:
        logger.error(f"Feature health check failed: {str(e)}", exc_info=True)
        return HealthCheck(
            status="unhealthy",
            message=f"Feature check error: {str(e)}",
            response_time_ms=None
        )


def _determine_overall_status(checks: dict) -> str:
    """
    Determine overall system health based on individual checks.

    Args:
        checks: Dictionary of health check results

    Returns:
        Overall status: 'healthy', 'degraded', or 'unhealthy'
    """
    statuses = [check.status for check in checks.values()]

    # If any check is unhealthy, overall is unhealthy
    if "unhealthy" in statuses:
        return "unhealthy"

    # If any check is degraded, overall is degraded
    if "degraded" in statuses:
        return "degraded"

    # All checks are healthy
    return "healthy"
