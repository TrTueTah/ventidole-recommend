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