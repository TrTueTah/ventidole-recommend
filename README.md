# Recommendation Service - Complete System

AI-powered K-pop post recommendation service with automated retraining and NestJS integration.

## 🎯 Overview

This repository contains a complete recommendation system featuring:

- **FastAPI Service**: Real-time recommendation API using LightFM hybrid model
- **Automated Training**: Cron job retrains model every 5 minutes with fresh data
- **Hot-Reload**: Update model without restarting service (zero downtime)
- **NestJS Integration**: Ready-to-use NestJS service for your backend
- **Infinite Scroll**: Offset-based pagination for smooth UX

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[QUICKSTART_TRAINING.md](QUICKSTART_TRAINING.md)** | Get started in 5 minutes |
| **[README_API.md](README_API.md)** | FastAPI service documentation |
| **[TRAINING.md](TRAINING.md)** | Automated training system guide |
| **[NESTJS_INTEGRATION.md](NESTJS_INTEGRATION.md)** | NestJS backend integration |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start FastAPI Service

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Set Up Automated Training

```bash
./scripts/setup_cron.sh
```

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Get recommendations (replace USER_ID with real user ID)
curl "http://localhost:8000/recommendations/USER_ID?limit=20&offset=0"

# Interactive docs
open http://localhost:8000/docs
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NestJS Backend                         │
│              (Your Main Application)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP REST API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Recommendation Service                 │
│                                                             │
│  GET  /recommendations/{user_id}  - Get recommendations    │
│  GET  /health                      - Health check          │
│  POST /admin/reload-model          - Reload model          │
│  GET  /admin/model-status          - Model status          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Uses
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  LightFM Hybrid Model                       │
│            (hybrid_model.pkl - 1.1 MB)                      │
│                                                             │
│  • Collaborative Filtering + Content-Based                 │
│  • User features: role, communities                        │
│  • Item features: tags, communityId                        │
│  • Trained on: views, likes, comments                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Trained from
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                       │
│                     (Neon Cloud)                            │
│                                                             │
│  • Users (500)                                             │
│  • Posts (2,016)                                           │
│  • Interactions (views, likes, comments)                   │
│  • Communities & Followers                                 │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │
                         │ Loads fresh data
┌─────────────────────────────────────────────────────────────┐
│              Cron Job (Every 5 minutes)                     │
│        scripts/train_model_cron.py                          │
│                                                             │
│  1. Load fresh data from PostgreSQL                        │
│  2. Build new feature matrices                             │
│  3. Train LightFM model (30 epochs)                        │
│  4. Save → hybrid_model.pkl (atomic replace)               │
│  5. Backup old model                                       │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
seed-service/
├── api/                              # FastAPI application
│   ├── main.py                       # FastAPI app entry point
│   ├── schemas.py                    # Pydantic models
│   ├── exceptions.py                 # Custom exceptions
│   ├── dependencies.py               # Dependency injection
│   ├── routers/
│   │   ├── recommendations.py        # Recommendation endpoints
│   │   ├── health.py                 # Health check
│   │   └── admin.py                  # Admin endpoints (reload)
│   └── services/
│       ├── model_manager.py          # Model loading & hot-reload
│       └── recommendation_service.py # Recommendation logic
│
├── scripts/                          # Automation scripts
│   ├── train_model_cron.py          # Automated training script
│   └── setup_cron.sh                 # Cron job installer
│
├── data/                             # Data loading (existing)
│   ├── load_data.py                  # PostgreSQL data loading
│   └── preprocess.py                 # Feature matrix building
│
├── models/                           # ML models (existing)
│   └── hybrid_lightfm.py             # LightFM training
│
├── pipeline/                         # Training pipeline (existing)
│   └── train_hybrid.py               # Original training script
│
├── logs/                             # Training & API logs
│   ├── training.log                  # Training execution logs
│   └── cron.log                      # Cron job logs
│
├── docker/                           # Docker deployment
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── .env                              # Environment config
├── config.py                         # Configuration
├── requirements.txt                  # Python dependencies
├── hybrid_model.pkl                  # Trained model (1.1 MB)
│
└── Documentation
    ├── README.md                     # This file
    ├── README_API.md                 # FastAPI docs
    ├── TRAINING.md                   # Training system docs
    ├── NESTJS_INTEGRATION.md         # NestJS integration
    └── QUICKSTART_TRAINING.md        # 5-minute quick start
```

## 🔑 Key Features

### FastAPI Service

✅ **Real-time Inference**: Uses trained model for instant recommendations
✅ **Infinite Scroll**: Offset-based pagination (`?limit=20&offset=0`)
✅ **Health Monitoring**: Comprehensive health checks
✅ **Auto Documentation**: Swagger UI and ReDoc
✅ **CORS Enabled**: Pre-configured for NestJS

### Automated Training

✅ **Scheduled Retraining**: Cron job runs every 5 minutes (configurable)
✅ **Atomic Replacement**: Zero-downtime model updates
✅ **Lock Prevention**: No concurrent training runs
✅ **Automatic Backups**: Keeps last 5 model versions
✅ **Comprehensive Logging**: Full audit trail

### Hot-Reload System

✅ **Zero Downtime**: Reload model without restarting service
✅ **File Change Detection**: Automatically detects new models
✅ **Admin API**: Trigger reload via REST endpoint
✅ **Status Monitoring**: Check model status and freshness

## 🎯 API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/recommendations/{user_id}` | Get personalized recommendations |
| `GET` | `/health` | Service health check |
| `GET` | `/` | API information |
| `GET` | `/docs` | Interactive API documentation |

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/admin/reload-model` | Reload model from disk |
| `GET` | `/admin/model-status` | Get model status |

### Query Parameters

**`GET /recommendations/{user_id}`**:
- `limit` (int, default: 20, max: 100): Items per page
- `offset` (int, default: 0): Pagination offset

## 💻 Usage Examples

### Get Recommendations

```bash
# First page
curl "http://localhost:8000/recommendations/user123?limit=20&offset=0"

# Second page
curl "http://localhost:8000/recommendations/user123?limit=20&offset=20"

# Third page
curl "http://localhost:8000/recommendations/user123?limit=20&offset=40"
```

**Response**:
```json
{
  "user_id": "user123",
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

### Reload Model

```bash
# Trigger model reload after training
curl -X POST http://localhost:8000/admin/reload-model
```

**Response**:
```json
{
  "success": true,
  "message": "Model reloaded successfully",
  "details": {
    "reloaded": true,
    "reason": "Model file modified",
    "previous_reload_time": "2025-12-24T10:00:00",
    "current_reload_time": "2025-12-24T10:05:00",
    "num_users": 500,
    "num_items": 2016
  }
}
```

## 🔧 Configuration

### Environment Variables

```bash
# Database (PostgreSQL)
DB_HOST=ep-jolly-queen-ahi39fhj.c-3.us-east-1.aws.neon.tech
DB_PORT=5432
DB_NAME=ventidole
DB_USER=neondb_owner
DB_PASSWORD=your_password

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Model
MODEL_PATH=hybrid_model.pkl
TOP_K_RECOMMENDATIONS=100

# Pagination
DEFAULT_PAGE_LIMIT=20
MAX_PAGE_LIMIT=100
```

### Training Schedule

Edit cron schedule to change training frequency:

```bash
crontab -e

# Examples:
*/5 * * * *    # Every 5 minutes (current)
*/10 * * * *   # Every 10 minutes
0 * * * *      # Every hour
0 */6 * * *    # Every 6 hours
0 2 * * *      # Daily at 2 AM
```

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
cd docker
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop service
docker-compose down
```

## 🔗 NestJS Integration

See [NESTJS_INTEGRATION.md](NESTJS_INTEGRATION.md) for complete integration guide.

**Quick Example**:

```typescript
// recommendation.service.ts
import { HttpService } from '@nestjs/axios';

@Injectable()
export class RecommendationService {
  constructor(private httpService: HttpService) {}

  async getUserRecommendations(userId: string, limit = 20, offset = 0) {
    const response = await firstValueFrom(
      this.httpService.get(
        `http://localhost:8000/recommendations/${userId}`,
        { params: { limit, offset } }
      )
    );
    return response.data;
  }
}
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| Cold Start | 5-10 seconds |
| Request Latency | <100ms (p95) |
| Throughput | 100-200 req/sec (4 workers) |
| Memory Usage | ~100-150 MB |
| Training Duration | ~45 seconds |

## 🛠️ Monitoring

### Training Logs

```bash
# Watch training in real-time
tail -f logs/training.log

# Check cron execution
tail -f logs/cron.log

# View model file age
ls -lh hybrid_model.pkl

# List backups
ls -lt hybrid_model_backup_*.pkl
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Model status
curl http://localhost:8000/admin/model-status
```

## 🔍 Troubleshooting

### Training not running?

```bash
# Test manually
python3 scripts/train_model_cron.py

# Check cron
crontab -l

# View logs
tail -f logs/training.log
```

### API not reloading?

```bash
# Check model file
ls -lh hybrid_model.pkl

# Manual reload
curl -X POST http://localhost:8000/admin/reload-model
```

### Database connection issues?

```bash
# Test connection
python3 -c "import psycopg2; from config import DB_CONFIG; conn = psycopg2.connect(**DB_CONFIG); print('Connected!')"
```

## 📈 Roadmap

**Short-term** (1-2 weeks):
- [ ] Redis caching for recommendations
- [ ] Rate limiting per user/IP
- [ ] Request tracing with correlation IDs

**Medium-term** (1-2 months):
- [ ] A/B testing framework
- [ ] Prometheus metrics
- [ ] Model quality monitoring

**Long-term** (3+ months):
- [ ] Online learning pipeline
- [ ] Real-time feature updates
- [ ] Multi-model serving (fallback strategies)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

MIT License

## 🆘 Support

- **Documentation**: See docs in this repository
- **Issues**: Open a GitHub issue
- **Email**: Contact your development team

---

## Summary

This is a **production-ready recommendation system** featuring:

✅ FastAPI service with real-time inference
✅ Automated model retraining (every 5 minutes)
✅ Hot-reload without downtime
✅ Complete NestJS integration guide
✅ Comprehensive monitoring and logging
✅ Docker deployment ready

**Get started**: See [QUICKSTART_TRAINING.md](QUICKSTART_TRAINING.md)

**Happy recommending! 🚀**
