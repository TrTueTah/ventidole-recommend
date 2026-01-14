"""
Pydantic models for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class PostRecommendation(BaseModel):
    """Single post recommendation with score and metadata"""
    post_id: str = Field(..., description="Unique post identifier")
    score: float = Field(..., description="Recommendation score (higher is better, can be negative)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Post metadata (tags, communityId, etc.)")


class PaginationMetadata(BaseModel):
    """Pagination information for infinite scroll"""
    total: int = Field(..., description="Total number of recommendations generated", ge=0)
    limit: int = Field(..., description="Items per page", ge=1)
    offset: int = Field(..., description="Current offset", ge=0)
    has_more: bool = Field(..., description="Whether more items are available")


class RecommendationResponse(BaseModel):
    """Response for recommendation endpoint"""
    user_id: str = Field(..., description="User ID for whom recommendations were generated")
    recommendations: List[PostRecommendation] = Field(..., description="List of recommended posts")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")
    strategy: Optional[str] = Field(
        default=None,
        description="Strategy used for recommendations: 'cold_start' or 'hybrid'"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123",
                "recommendations": [
                    {
                        "post_id": "post789",
                        "score": 0.95,
                        "metadata": {
                            "tags": ["music", "concert"],
                            "communityId": "community456"
                        }
                    }
                ],
                "pagination": {
                    "total": 100,
                    "limit": 20,
                    "offset": 0,
                    "has_more": True
                },
                "strategy": "hybrid"
            }
        }


class HealthCheck(BaseModel):
    """Individual health check result"""
    status: str = Field(..., description="Status: 'healthy' | 'degraded' | 'unhealthy'")
    message: str = Field(..., description="Human-readable status message")
    response_time_ms: Optional[float] = Field(None, description="Check response time in milliseconds")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Overall status: 'healthy' | 'degraded' | 'unhealthy'")
    timestamp: datetime = Field(..., description="Timestamp of health check")
    checks: Dict[str, HealthCheck] = Field(..., description="Individual health check results")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-12-24T10:30:00Z",
                "checks": {
                    "model": {
                        "status": "healthy",
                        "message": "Model loaded successfully",
                        "response_time_ms": 0.5
                    },
                    "database": {
                        "status": "healthy",
                        "message": "Database connection active",
                        "response_time_ms": 15.2
                    }
                }
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Machine-readable error code")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Error timestamp")
