# Recommendation Service API

FastAPI-based REST API service for real-time K-pop post recommendations using LightFM hybrid model.

## Overview

This service provides personalized post recommendations for users with support for infinite scroll pagination. It integrates with your existing NestJS backend via REST API calls.

## Features

- **Real-time Inference**: Uses the trained LightFM model for on-the-fly recommendations
- **Infinite Scroll**: Offset-based pagination for smooth user experience
- **Health Monitoring**: Health check endpoint for service monitoring
- **Auto Documentation**: Interactive API docs via Swagger UI
- **CORS Support**: Pre-configured for NestJS integration

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (Neon)
- Trained model file (`hybrid_model.pkl`)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the service:
```bash
# Development (with auto-reload)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production (with multiple workers)
gunicorn api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Endpoints

### Get Recommendations

**Endpoint**: `GET /recommendations/{user_id}`

**Parameters**:
- `user_id` (path, required): User ID to get recommendations for
- `limit` (query, optional): Items per page (default: 20, max: 100)
- `offset` (query, optional): Pagination offset (default: 0)

**Example Request**:
```bash
curl http://localhost:8000/recommendations/abc123?limit=20&offset=0
```

**Example Response**:
```json
{
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
    "has_more": true
  }
}
```

### Health Check

**Endpoint**: `GET /health`

**Example Request**:
```bash
curl http://localhost:8000/health
```

**Example Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-24T10:30:00Z",
  "checks": {
    "model": {
      "status": "healthy",
      "message": "Model loaded successfully (LightFM)",
      "response_time_ms": 0.5
    },
    "database": {
      "status": "healthy",
      "message": "Database connection active",
      "response_time_ms": 15.2
    },
    "features": {
      "status": "healthy",
      "message": "Features loaded (500 users, 2000 items)",
      "response_time_ms": 0.3
    }
  }
}
```

## Interactive Documentation

Once the service is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Docker Deployment

### Build and Run

```bash
# Using docker-compose
cd docker
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop service
docker-compose down
```

### Build Manually

```bash
# Build image
docker build -f docker/Dockerfile -t recommendation-service .

# Run container
docker run -d \
  --name recommendation-api \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/hybrid_model.pkl:/app/hybrid_model.pkl:ro \
  recommendation-service
```

## Integration with NestJS Backend

### TypeScript Client Example

```typescript
import axios from 'axios';

export class RecommendationService {
  private readonly apiUrl = process.env.RECOMMENDATION_API_URL || 'http://localhost:8000';

  async getUserRecommendations(userId: string, limit = 20, offset = 0) {
    try {
      const response = await axios.get(
        `${this.apiUrl}/recommendations/${userId}`,
        { params: { limit, offset } }
      );
      return response.data;
    } catch (error) {
      if (error.response?.status === 404) {
        // User not found - return fallback recommendations
        return this.getFallbackRecommendations(userId);
      }
      throw error;
    }
  }

  async checkHealth() {
    const response = await axios.get(`${this.apiUrl}/health`);
    return response.data;
  }
}
```

### Infinite Scroll Implementation

```typescript
// Frontend example
let offset = 0;
const limit = 20;

async function loadMoreRecommendations(userId: string) {
  const data = await recommendationService.getUserRecommendations(userId, limit, offset);

  // Append recommendations to UI
  appendRecommendations(data.recommendations);

  // Update offset for next page
  if (data.pagination.has_more) {
    offset += limit;
  } else {
    // No more recommendations
    hideLoadMoreButton();
  }
}
```

## Configuration

### Environment Variables

All configuration is managed via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | `ep-jolly-queen-ahi39fhj.c-3.us-east-1.aws.neon.tech` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `ventidole` |
| `DB_USER` | Database user | `neondb_owner` |
| `DB_PASSWORD` | Database password | *required* |
| `API_HOST` | API host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `API_WORKERS` | Number of workers | `4` |
| `MODEL_PATH` | Path to model file | `hybrid_model.pkl` |
| `TOP_K_RECOMMENDATIONS` | Total recommendations to generate | `100` |
| `DEFAULT_PAGE_LIMIT` | Default page size | `20` |
| `MAX_PAGE_LIMIT` | Maximum page size | `100` |

## Error Handling

### Common Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 404 | `USER_NOT_FOUND` | User ID not found in recommendation system |
| 422 | Validation Error | Invalid request parameters |
| 500 | `INTERNAL_ERROR` | Internal server error |
| 503 | `MODEL_ERROR` | Model not loaded or unavailable |
| 503 | `DATABASE_ERROR` | Database connection failed |

### Error Response Format

```json
{
  "detail": "User abc123 not found in recommendation system",
  "error_code": "USER_NOT_FOUND",
  "user_id": "abc123",
  "timestamp": "2025-12-24T10:30:00Z"
}
```

## Performance

- **Cold Start**: 5-10 seconds (model + data loading)
- **Request Latency**: <100ms (95th percentile)
- **Throughput**: 100-200 requests/second (4 workers)
- **Memory Usage**: ~100-150 MB

## Troubleshooting

### Model fails to load

```bash
# Check if model file exists
ls -lh hybrid_model.pkl

# Check logs
tail -f logs/api.log
```

### Database connection issues

```bash
# Test database connection
python -c "import psycopg2; from config import DB_CONFIG; conn = psycopg2.connect(**DB_CONFIG); print('Connected!')"
```

### Import errors

```bash
# Ensure all dependencies are installed
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Code Structure

```
seed-service/
├── api/
│   ├── main.py                    # FastAPI app entry point
│   ├── dependencies.py            # Dependency injection
│   ├── schemas.py                 # Pydantic models
│   ├── exceptions.py              # Custom exceptions
│   ├── routers/
│   │   ├── recommendations.py     # Recommendation endpoint
│   │   └── health.py              # Health check endpoint
│   └── services/
│       ├── model_manager.py       # Model loading & caching
│       └── recommendation_service.py  # Recommendation logic
├── data/                          # Existing: Data loading
├── models/                        # Existing: ML models
├── storage/                       # Existing: Model persistence
├── requirements.txt               # Python dependencies
└── .env                          # Environment configuration
```

## Future Enhancements

- [ ] Redis caching for user recommendations
- [ ] Rate limiting per user/IP
- [ ] Request tracing with correlation IDs
- [ ] Model reload endpoint (without restart)
- [ ] A/B testing framework
- [ ] Prometheus metrics
- [ ] Online learning pipeline

## License

MIT

## Support

For issues or questions, please contact the development team or open an issue on GitHub.
