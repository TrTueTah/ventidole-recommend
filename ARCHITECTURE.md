# Seed Service - Architecture Documentation

## Overview

This is a **production-ready AI-powered K-pop recommendation service** built with FastAPI and LightFM. The system features automated model training, hot-reload capabilities, and comprehensive health monitoring.

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **API Framework** | FastAPI 0.104.1, Uvicorn 0.24.0 |
| **ML Framework** | LightFM 1.17 (Collaborative + Content-based filtering) |
| **Data Processing** | Pandas 2.0.0+, NumPy 1.24.0+, Scikit-learn 1.3.0+ |
| **Database** | PostgreSQL (Neon Cloud) with psycopg2 |
| **Validation** | Pydantic 2.5.0 |
| **Production** | Gunicorn 21.2.0 |
| **Containerization** | Docker & Docker Compose |

---

## Project Structure

```
/seed-service/
├── api/                              # FastAPI application core
│   ├── main.py                       # FastAPI app entry point with lifespan management
│   ├── schemas.py                    # Pydantic models (RecommendationResponse, HealthResponse, etc.)
│   ├── exceptions.py                 # Custom exception classes
│   ├── dependencies.py               # Dependency injection for FastAPI
│   ├── routers/
│   │   ├── recommendations.py        # GET /recommendations/{user_id} endpoint
│   │   ├── health.py                 # GET /health endpoint with multi-component checks
│   │   └── admin.py                  # POST /admin/reload-model, GET /admin/model-status
│   └── services/
│       ├── model_manager.py          # Loads, caches, and hot-reloads LightFM model
│       └── recommendation_service.py # Business logic for generating recommendations
│
├── data/                             # Data loading and preprocessing
│   ├── load_data.py                  # PostgreSQL queries (users, posts, interactions)
│   └── preprocess.py                 # Feature matrix building for users/items
│
├── models/                           # ML model training
│   ├── hybrid_lightfm.py             # Hybrid (content-based + CF) model trainer
│   ├── content_based.py              # Content-based LightFM training
│   └── cf_lightfm.py                 # Collaborative filtering (referenced)
│
├── pipeline/                         # Original training pipeline
│   ├── train_hybrid.py               # Training orchestration
│   └── evaluate_hybrid.py            # Model evaluation
│
├── scripts/                          # Automation and utilities
│   ├── train_model_cron.py           # Main automated training script (runs every 5 min)
│   └── setup_cron.sh                 # Cron job installer script
│
├── storage/                          # Model persistence
│   └── save_load.py                  # Pickle-based model serialization
│
├── inference/                        # Inference utilities (if present)
├── evaluation/                       # Model evaluation scripts
├── features/                         # Feature engineering utilities
│
├── logs/                             # Application logs
│   ├── training.log                  # Automated training execution logs
│   └── cron.log                      # Cron job execution logs
│
├── docker/                           # Containerization
│   ├── Dockerfile                    # Production Docker image
│   └── docker-compose.yml            # Service orchestration
│
├── config.py                         # Centralized configuration (DB, API, model)
├── requirements.txt                  # Python dependencies
├── hybrid_model.pkl                  # Trained LightFM model (1.1 MB)
├── hybrid_model_backup_*.pkl         # Automatic model backups (keeps last 5)
├── communities.json                  # Static K-pop communities metadata
├── idols.json                        # Static K-pop idols metadata
├── .env                              # Environment variables (secrets)
├── .env.example                      # Environment template
├── README.md                         # Main documentation
├── README_API.md                     # API documentation
├── TRAINING.md                       # Training system guide
├── NESTJS_INTEGRATION.md             # NestJS integration guide
└── QUICKSTART_TRAINING.md            # 5-minute quick start guide
```

---

## System Architecture

### Overall Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   NestJS     │    │  Direct HTTP │    │   Frontend   │      │
│  │   Backend    │    │   Clients    │    │     Apps     │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │              │
└─────────┼───────────────────┼───────────────────┼──────────────┘
          │                   │                   │
          └───────────────────┴───────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │   CORS Middleware   │
                   └──────────┬──────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│                     FASTAPI APPLICATION                          │
│                             │                                    │
│  ┌──────────────────────────▼─────────────────────────┐         │
│  │           API ROUTERS (Endpoints)                  │         │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │         │
│  │  │  Health  │  │  Recom.  │  │  Admin   │        │         │
│  │  │  /health │  │ /recom.. │  │ /admin/* │        │         │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘        │         │
│  └───────┼─────────────┼─────────────┼───────────────┘         │
│          │             │             │                          │
│  ┌───────▼─────────────▼─────────────▼───────────────┐         │
│  │        DEPENDENCY INJECTION LAYER                  │         │
│  │      (get_recommendation_service)                  │         │
│  └───────────────────────┬────────────────────────────┘         │
│                          │                                      │
│  ┌───────────────────────▼────────────────────────────┐         │
│  │         RECOMMENDATION SERVICE                     │         │
│  │   • Validate user ID                              │         │
│  │   • Generate recommendations                       │         │
│  │   • Apply pagination                               │         │
│  │   • Enrich with metadata                           │         │
│  └───────────────────────┬────────────────────────────┘         │
│                          │                                      │
│  ┌───────────────────────▼────────────────────────────┐         │
│  │           MODEL MANAGER                            │         │
│  │   • Load/cache model                              │         │
│  │   • Hot-reload detection (mtime)                   │         │
│  │   • Thread-safe access                             │         │
│  │   • Feature matrix caching                         │         │
│  └───────────────────────┬────────────────────────────┘         │
│                          │                                      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  hybrid_model.pkl       │
              │  (LightFM Model - 1.1MB)│
              └────────────┬────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                    DATA LAYER                                    │
│                          │                                      │
│  ┌───────────────────────▼────────────────────────────┐         │
│  │           PostgreSQL Database                      │         │
│  │  • Users (500)                                     │         │
│  │  • Posts (2,016)                                   │         │
│  │  • Interactions (views, likes, comments)           │         │
│  │  • Community followers                             │         │
│  └────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Workflows

### 1. Recommendation Request Flow

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ GET /recommendations/user123?limit=20&offset=0
     ▼
┌─────────────────┐
│  FastAPI Router │
└────┬────────────┘
     │
     ▼
┌──────────────────────────┐
│ RecommendationService    │
│                          │
│ 1. Validate user_id      │───┐
└────┬─────────────────────┘   │
     │                         │
     ▼                         ▼
┌──────────────────────┐   ┌─────────────┐
│   Model Manager      │   │ Feature     │
│                      │◄──│ Mappings    │
│ 2. Get user index    │   └─────────────┘
│ 3. Load LightFM      │
│ 4. Predict scores    │
│    for all posts     │
└────┬─────────────────┘
     │ [post_id, score] × 2016
     ▼
┌──────────────────────────┐
│ RecommendationService    │
│                          │
│ 5. Sort by score (desc)  │
│ 6. Get top-100           │
│ 7. Apply pagination      │
│    (offset=0, limit=20)  │
│ 8. Enrich with metadata  │
└────┬─────────────────────┘
     │
     ▼
┌──────────────────────────┐
│   Response JSON          │
│                          │
│ {                        │
│   items: [20 posts],     │
│   total: 100,            │
│   limit: 20,             │
│   offset: 0,             │
│   has_more: true         │
│ }                        │
└────┬─────────────────────┘
     │
     ▼
┌──────────┐
│  Client  │
└──────────┘
```

### 2. Automated Training & Hot-Reload Flow

```
┌─────────────────────────────────────────────────────────────┐
│               TRAINING PIPELINE (Every 5 min)               │
└─────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  Cron Job    │
    │  (*/5 * * *) │
    └──────┬───────┘
           │
           ▼
    ┌─────────────────────┐
    │ Check lock file     │───┐ Lock exists?
    │ /tmp/model_train... │   │─Yes─► Exit (Skip)
    └──────┬──────────────┘   │
           │                  │
           No                 │
           │                  │
           ▼                  │
    ┌─────────────────────┐  │
    │ Create lock file    │◄─┘
    └──────┬──────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ scripts/train_model_cron.py  │
    │                              │
    │ 1. Load data from PostgreSQL │
    │    • Users                   │
    │    • Posts                   │
    │    • Interactions            │
    │    • Communities             │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ data/preprocess.py           │
    │                              │
    │ 2. Build feature matrices    │
    │    • User: role + community  │
    │    • Item: tags + community  │
    │    • Interaction weights     │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ models/hybrid_lightfm.py     │
    │                              │
    │ 3. Train LightFM model       │
    │    • 30 components           │
    │    • 30 epochs               │
    │    • WARP loss               │
    │    • ~45 seconds             │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ Atomic File Replacement      │
    │                              │
    │ 4. Save to temp file         │
    │ 5. Backup old model          │
    │    (keep last 5)             │
    │ 6. Atomic rename             │
    │    → hybrid_model.pkl        │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ Release lock file            │
    │ Log completion               │
    └──────┬───────────────────────┘
           │
           │ File modified!
           │
┌──────────▼────────────────────────────────────────────────┐
│              HOT-RELOAD DETECTION                          │
└────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ Model Manager                │
    │                              │
    │ • Detect mtime change        │
    │ • Or /admin/reload-model     │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ Reload Model                 │
    │                              │
    │ 1. Load new hybrid_model.pkl │
    │ 2. Update feature mappings   │
    │ 3. Clear old cache           │
    │ 4. No service restart!       │
    └──────┬───────────────────────┘
           │
           ▼
    ┌──────────────────────────────┐
    │ API Service                  │
    │ ✓ Using new model            │
    │ ✓ Zero downtime              │
    └──────────────────────────────┘
```

### 3. Data Pipeline

```
┌────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                      │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐            │
│  │  Users   │  │  Posts   │  │Interactions │            │
│  │  (500)   │  │ (2,016)  │  │ (views,     │            │
│  │          │  │          │  │  likes,     │            │
│  │ • id     │  │ • id     │  │  comments)  │            │
│  │ • role   │  │ • tags   │  │             │            │
│  └──────────┘  │ • comm.. │  └─────────────┘            │
│                │ • meta.. │                              │
│                └──────────┘                              │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼ SQL Queries (load_data.py)
┌────────────────────────────────────────────────────────────┐
│                    Feature Engineering                     │
│                   (preprocess.py)                          │
│                                                            │
│  User Features:                 Item Features:             │
│  ┌───────────────────┐         ┌────────────────────┐     │
│  │ role:admin        │         │ tag:dance          │     │
│  │ role:user         │         │ tag:music          │     │
│  │ community:123     │         │ tag:news           │     │
│  │ community:456     │         │ community:123      │     │
│  └───────────────────┘         └────────────────────┘     │
│                                                            │
│  Interaction Matrix:                                       │
│  ┌─────────────────────────────────────┐                  │
│  │ user_id | post_id | weight          │                  │
│  │ ──────────────────────────────────  │                  │
│  │   1     |   100   |   1.0           │                  │
│  │   1     |   101   |   1.0           │                  │
│  │   2     |   100   |   1.0           │                  │
│  └─────────────────────────────────────┘                  │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼ LightFM Training
┌────────────────────────────────────────────────────────────┐
│              Hybrid LightFM Model                          │
│                                                            │
│  • Algorithm: WARP (Weighted Approximate Rank Pairwise)    │
│  • Components: 30                                          │
│  • Epochs: 30                                              │
│  • Loss: Ranking optimization                              │
│                                                            │
│  Hybrid = Collaborative Filtering + Content-Based          │
│  ┌────────────────┐    ┌─────────────────┐               │
│  │ User-Item      │ +  │ Feature-based   │               │
│  │ Interactions   │    │ Similarity      │               │
│  └────────────────┘    └─────────────────┘               │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼ Serialization (storage/save_load.py)
┌────────────────────────────────────────────────────────────┐
│            hybrid_model.pkl (1.1 MB)                       │
│                                                            │
│  • User embeddings                                         │
│  • Item embeddings                                         │
│  • Feature mappings                                        │
│  • Model parameters                                        │
└────────────────────────────────────────────────────────────┘
```

---

## Core Components

| Component | Purpose | Key Responsibilities |
|-----------|---------|---------------------|
| **api/main.py** | FastAPI application entry point | App initialization, CORS setup, exception handlers, router registration, lifespan management |
| **api/routers/recommendations.py** | Recommendation endpoint | Accept user_id, limit, offset; delegate to RecommendationService |
| **api/routers/health.py** | Health monitoring | Multi-component health checks (model, database, features) |
| **api/routers/admin.py** | Model management | Trigger model reload, check model status |
| **api/services/model_manager.py** | Model lifecycle | Load model, cache features, hot-reload detection, thread-safe access |
| **api/services/recommendation_service.py** | Recommendation logic | Generate paginated recommendations, score sorting, metadata enrichment |
| **data/load_data.py** | Database queries | Load users, posts, interactions from PostgreSQL |
| **data/preprocess.py** | Feature engineering | Build user/item feature matrices, LightFM dataset construction |
| **models/hybrid_lightfm.py** | Model training | Train hybrid LightFM model using user/item features |
| **scripts/train_model_cron.py** | Automated training | Scheduled model retraining with atomic file replacement, backup management |
| **storage/save_load.py** | Model persistence | Serialize/deserialize LightFM model via pickle |

---

## API Endpoints

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|-----------|
| **GET** | `/` | API root with endpoint listing | None |
| **GET** | `/health` | Multi-component health check | None |
| **GET** | `/recommendations/{user_id}` | Get paginated recommendations | `limit` (1-100, default 20), `offset` (default 0) |
| **POST** | `/admin/reload-model` | Trigger model reload | None |
| **GET** | `/admin/model-status` | Check model load status | None |
| **GET** | `/docs` | Swagger UI (auto-generated) | None |
| **GET** | `/redoc` | ReDoc (auto-generated) | None |

---

## Key Features

### 1. Zero-Downtime Hot Reload
- Model Manager tracks file modification time (mtime)
- Automatically detects when `hybrid_model.pkl` is updated
- Reloads model via `/admin/reload-model` endpoint without service restart
- Admin endpoint can trigger reload after cron training completes

### 2. Atomic Model Replacement
- Training writes to temporary file first
- Backs up old model with timestamp (keeps last 5)
- Atomic rename operation (no corruption risk)
- Lock file prevents concurrent training runs

### 3. Dependency Injection Pattern
- FastAPI dependency: `get_recommendation_service()`
- Uses `lru_cache` for singleton pattern
- Reduces coupling between endpoints and services

### 4. Hybrid Recommendation Model
- **Collaborative Filtering**: User-item interaction history (views, likes, comments)
- **Content-Based**: User features (role, community interests) + Item features (tags, community)
- LightFM with WARP loss (Weighted Approximate Rank Pairwise)
- 30 components, 30 epochs training

### 5. Pagination for Infinite Scroll
- Offset-based pagination (standard for frontend scrolling)
- Generates top-100 recommendations, pages through them
- Metadata includes `has_more` flag for frontend logic

### 6. Comprehensive Health Checks
- Model availability and type
- Database connectivity with response time measurement
- Feature matrices dimensions validation
- Overall status: healthy, degraded, or unhealthy

---

## Data Model

### User Features
- `role:{role}` - User role (e.g., "admin", "user")
- `community:{communityId}` - Each community the user follows (sparse multi-valued)

### Item (Post) Features
- `tag:{tag}` - Each tag from post metadata (sparse multi-valued)
- `community:{communityId}` - Community the post belongs to

### Interactions
- Views (post_view table)
- Likes (post_like table)
- Comments (comment table)
- All weighted equally (1.0)

---

## Configuration

### Environment Variables (config.py)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL credentials
- `API_HOST`, `API_PORT`, `API_WORKERS` - Server configuration
- `MODEL_PATH` - Path to trained model file
- `TOP_K_RECOMMENDATIONS` - Number of recommendations to generate (default 100)
- `DEFAULT_PAGE_LIMIT`, `MAX_PAGE_LIMIT` - Pagination limits

### Cron Schedule
- Current: `*/5 * * * *` (every 5 minutes)
- Lockfile prevents concurrent runs: `/tmp/model_training.lock`

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Cold Start | 5-10 seconds |
| Request Latency (p95) | <100ms |
| Throughput | 100-200 req/sec (4 workers) |
| Memory Usage | 100-150 MB |
| Training Duration | ~45 seconds |
| Model Size | 1.1 MB |

---

## Docker Deployment

### docker-compose.yml
- Single service: `recommendation-api`
- Mounts:
  - `hybrid_model.pkl` (read-only)
  - `.env` file (read-only)
- Healthcheck via `/health` endpoint (30s interval)
- Restart policy: unless-stopped
- Environment variable injection

---

## NestJS Integration

The service is designed to integrate with NestJS applications via HTTP:

```typescript
// Example NestJS integration
async getRecommendations(userId: string, limit: 20, offset: 0) {
  return this.httpService.get(
    `http://localhost:8000/recommendations/${userId}`,
    { params: { limit, offset } }
  )
}
```

CORS is pre-configured to accept requests from typical development ports (3000, 4000, 5000) and allows all origins in development mode.

---

## Logging and Monitoring

### Log Files
- `/logs/training.log` - Model training execution and performance
- `/logs/cron.log` - Cron job execution status

### Monitoring Points
- Health endpoint provides component-level insights
- Model status endpoint shows user/item counts and reload times
- Cron logs show training duration and success/failure

---

## Design Patterns

1. **Repository Pattern**: Data access abstraction via `load_data.py`
2. **Service Layer**: Business logic separation in `services/`
3. **Dependency Injection**: FastAPI dependencies for loose coupling
4. **Singleton Pattern**: Cached services via `lru_cache`
5. **Factory Pattern**: Model creation and loading
6. **Strategy Pattern**: Different training strategies (CF, content-based, hybrid)

---

## Future Considerations

- **Scalability**: Consider Redis for model caching in multi-instance deployments
- **A/B Testing**: Framework for testing different model versions
- **Real-time Updates**: WebSocket support for live recommendation updates
- **Feature Store**: Centralized feature management for consistency
- **Model Versioning**: Track and rollback model versions
- **Advanced Metrics**: Precision@K, Recall@K, NDCG tracking
- **Cold Start Handling**: Improved strategies for new users/posts

---

## Documentation References

- [README.md](README.md) - Main documentation
- [README_API.md](README_API.md) - API documentation
- [TRAINING.md](TRAINING.md) - Training system guide
- [NESTJS_INTEGRATION.md](NESTJS_INTEGRATION.md) - NestJS integration guide
- [QUICKSTART_TRAINING.md](QUICKSTART_TRAINING.md) - 5-minute quick start guide
