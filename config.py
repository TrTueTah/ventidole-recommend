# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', ''),
    'port': int(os.getenv('DB_PORT', 5432)),
    'dbname': os.getenv('DB_NAME', 'ventidole'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# API Configuration
API_CONFIG = {
    'host': os.getenv('API_HOST', '0.0.0.0'),
    'port': int(os.getenv('API_PORT', 8000)),
    'workers': int(os.getenv('API_WORKERS', 4))
}

# Model Configuration
MODEL_PATH = os.getenv('MODEL_PATH', 'hybrid_model.pkl')
TOP_K = int(os.getenv('TOP_K_RECOMMENDATIONS', 100))

# Pagination Configuration
DEFAULT_PAGE_LIMIT = int(os.getenv('DEFAULT_PAGE_LIMIT', 20))
MAX_PAGE_LIMIT = int(os.getenv('MAX_PAGE_LIMIT', 100))

# Cold-Start Configuration
COLD_START_INTERACTION_THRESHOLD = int(os.getenv('COLD_START_INTERACTION_THRESHOLD', 5))
COLD_START_RECENCY_WINDOW_DAYS = int(os.getenv('COLD_START_RECENCY_WINDOW_DAYS', 7))

# Cold-Start Scoring Weights (must sum to 1.0)
COLD_START_WEIGHT_COMMUNITY = float(os.getenv('COLD_START_WEIGHT_COMMUNITY', 0.45))
COLD_START_WEIGHT_CONTENT = float(os.getenv('COLD_START_WEIGHT_CONTENT', 0.25))
COLD_START_WEIGHT_RECENCY = float(os.getenv('COLD_START_WEIGHT_RECENCY', 0.20))
COLD_START_WEIGHT_POPULARITY = float(os.getenv('COLD_START_WEIGHT_POPULARITY', 0.10))