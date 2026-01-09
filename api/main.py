"""
FastAPI Recommendation Service
Main application entry point
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from api.routers import health, recommendations, admin
from api.services.model_manager import initialize_model_manager
from api.exceptions import (
    UserNotFoundException,
    NoRecommendationsException,
    ModelNotLoadedException,
    DatabaseConnectionException
)
from config import MODEL_PATH, API_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup: Load model and initialize resources
    logger.info("=" * 80)
    logger.info("Starting FastAPI Recommendation Service")
    logger.info("=" * 80)

    try:
        logger.info(f"Loading model from {MODEL_PATH}...")
        model_manager = initialize_model_manager(MODEL_PATH)
        logger.info("Model loaded successfully!")
        logger.info(f"Users: {model_manager.get_num_users()}, Items: {model_manager.get_num_items()}")

    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}", exc_info=True)
        logger.error("Application startup failed!")
        raise

    logger.info("Application startup complete")
    logger.info("=" * 80)

    yield  # Application runs

    # Shutdown: Cleanup resources
    logger.info("Shutting down FastAPI Recommendation Service")
    logger.info("Cleanup complete")


# Create FastAPI application
app = FastAPI(
    title="Recommendation Service API",
    description="FastAPI-based recommendation service for K-pop post recommendations using LightFM hybrid model",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# CORS Middleware (configure for NestJS backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # NestJS default port
        "http://localhost:4000",
        "http://localhost:5000",
        "*"  # Allow all origins in development (restrict in production)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers
@app.exception_handler(UserNotFoundException)
async def user_not_found_handler(request: Request, exc: UserNotFoundException):
    """Handle user not found exceptions"""
    logger.warning(f"User not found: {exc.user_id}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc),
            "error_code": "USER_NOT_FOUND",
            "user_id": exc.user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(NoRecommendationsException)
async def no_recommendations_handler(request: Request, exc: NoRecommendationsException):
    """Handle no recommendations available"""
    logger.info(f"No recommendations for user: {exc.user_id}")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "user_id": exc.user_id,
            "recommendations": [],
            "pagination": {
                "total": 0,
                "limit": 20,
                "offset": 0,
                "has_more": False
            }
        }
    )


@app.exception_handler(ModelNotLoadedException)
async def model_not_loaded_handler(request: Request, exc: ModelNotLoadedException):
    """Handle model not loaded exceptions"""
    logger.error(f"Model not loaded: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Recommendation service unavailable",
            "error_code": "MODEL_ERROR",
            "message": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(DatabaseConnectionException)
async def database_error_handler(request: Request, exc: DatabaseConnectionException):
    """Handle database connection exceptions"""
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database connection failed",
            "error_code": "DATABASE_ERROR",
            "message": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Register routers
app.include_router(health.router)
app.include_router(recommendations.router)
app.include_router(admin.router)


# Root endpoint
@app.get(
    "/",
    tags=["Root"],
    summary="API root endpoint",
    description="Returns basic information about the API"
)
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Recommendation Service API",
        "version": "1.0.0",
        "description": "FastAPI-based recommendation service for K-pop posts",
        "endpoints": {
            "health": "/health",
            "recommendations": "/recommendations/{user_id}",
            "admin_reload": "/admin/reload-model",
            "admin_status": "/admin/model-status",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server with uvicorn...")
    uvicorn.run(
        "api.main:app",
        host=API_CONFIG['host'],
        port=API_CONFIG['port'],
        reload=True,
        log_level="info"
    )
