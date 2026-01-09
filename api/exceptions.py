"""
Custom exceptions for the recommendation API
"""


class RecommendationException(Exception):
    """Base exception for recommendation errors"""
    pass


class UserNotFoundException(RecommendationException):
    """Raised when user ID is not found in training data"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found in recommendation system")


class NoRecommendationsException(RecommendationException):
    """Raised when no recommendations are available for a user"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"No recommendations available for user {user_id}")


class ModelNotLoadedException(RecommendationException):
    """Raised when model failed to load at startup"""
    def __init__(self, message: str = "Recommendation model is not loaded"):
        super().__init__(message)


class DatabaseConnectionException(RecommendationException):
    """Raised when database connection fails"""
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message)
