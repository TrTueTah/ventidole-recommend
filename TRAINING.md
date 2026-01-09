# Automated Model Training & Hot-Reloading

This document explains how to set up automated model retraining with hot-reloading for the recommendation service.

## Overview

The recommendation service supports **automated model retraining** without requiring service restarts:

1. **Cron Job**: Runs training script every 5 minutes with fresh data from database
2. **Atomic Replacement**: New model file replaces old one safely (no downtime)
3. **Hot-Reload API**: API automatically detects new model and reloads it
4. **Zero Downtime**: Service continues serving recommendations during model updates

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Cron Job (Every 5 min)                     │
│                                                                 │
│  1. Load fresh data from PostgreSQL                            │
│  2. Build new feature matrices                                 │
│  3. Train LightFM model (30 epochs)                            │
│  4. Save to temp file                                          │
│  5. Atomic replace: temp → hybrid_model.pkl                    │
│                                                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Model file updated
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Service                            │
│                                                                 │
│  POST /admin/reload-model                                      │
│    ├─ Detect model file change (mtime check)                  │
│    ├─ Reload model + features + mappings                      │
│    ├─ Update in-memory cache                                  │
│    └─ Return reload status                                     │
│                                                                 │
│  Recommendations continue serving during reload!               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Setup Instructions

### 1. One-Time Setup: Install Cron Job

Run the automated setup script:

```bash
cd /Users/tanhtran/Documents/github/seed-service
./scripts/setup_cron.sh
```

This script will:
- ✅ Create logs directory
- ✅ Make training script executable
- ✅ Add cron job to run every 5 minutes
- ✅ Configure logging

**Manual Setup (Alternative)**:

```bash
# Edit crontab
crontab -e

# Add this line (replace with your actual path):
*/5 * * * * cd /Users/tanhtran/Documents/github/seed-service && python3 scripts/train_model_cron.py >> logs/cron.log 2>&1
```

### 2. Verify Cron Job Installation

```bash
# List active cron jobs
crontab -l

# You should see:
# Recommendation model retraining every 5 minutes
# */5 * * * * cd /path/to/seed-service && python3 scripts/train_model_cron.py >> logs/cron.log 2>&1
```

### 3. Monitor Training

```bash
# Watch training logs in real-time
tail -f logs/training.log

# Watch cron execution logs
tail -f logs/cron.log

# Check model file modification time
ls -lh hybrid_model.pkl
```

## How It Works

### Training Script (`scripts/train_model_cron.py`)

The training script performs these steps:

1. **Lock File Check**: Prevents concurrent training runs
2. **Data Loading**: Fetches latest data from PostgreSQL
3. **Feature Building**: Creates user/item feature matrices
4. **Model Training**: Trains LightFM hybrid model (30 epochs)
5. **Atomic Replacement**:
   ```python
   # Save to temp file
   save_model(model, "hybrid_model_temp_123.pkl")

   # Backup old model
   backup("hybrid_model.pkl" → "hybrid_model_backup_20251224_100500.pkl")

   # Atomic rename (instant, no downtime)
   move("hybrid_model_temp_123.pkl" → "hybrid_model.pkl")
   ```
6. **Cleanup**: Removes old backups (keeps last 5)

### Hot-Reload API Endpoints

#### `POST /admin/reload-model`

Reload the model from disk if it has been updated.

**Request**:
```bash
curl -X POST http://localhost:8000/admin/reload-model
```

**Response** (Model was updated):
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

**Response** (Model was not updated):
```json
{
  "success": true,
  "message": "Model is already up to date",
  "details": {
    "reloaded": false,
    "reason": "Model file not modified",
    "last_reload_time": "2025-12-24T10:05:00"
  }
}
```

#### `GET /admin/model-status`

Get current model status and check if update is available.

**Request**:
```bash
curl http://localhost:8000/admin/model-status
```

**Response**:
```json
{
  "is_loaded": true,
  "num_users": 500,
  "num_items": 2016,
  "num_posts_metadata": 2016,
  "model_type": "LightFM",
  "model_path": "hybrid_model.pkl",
  "last_reload_time": "2025-12-24T10:05:00",
  "file_updated": false
}
```

## Automated Reload Integration

You can automate the reload process after each training run by adding a webhook or script:

### Option 1: Modify Training Script

Add this to the end of `scripts/train_model_cron.py`:

```python
# After successful model save
if success:
    import requests
    try:
        response = requests.post("http://localhost:8000/admin/reload-model")
        logger.info(f"Model reload triggered: {response.json()}")
    except Exception as e:
        logger.warning(f"Failed to trigger reload: {e}")
```

### Option 2: Separate Reload Cron Job

```bash
# Add to crontab (runs 1 minute after training)
*/5 * * * * sleep 60 && curl -X POST http://localhost:8000/admin/reload-model >> logs/reload.log 2>&1
```

### Option 3: Watch Service (Production)

Use a file watcher service that automatically calls the reload endpoint when the model file changes:

```python
# watch_model.py
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

class ModelFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('hybrid_model.pkl'):
            print(f"Model file updated: {event.src_path}")
            response = requests.post("http://localhost:8000/admin/reload-model")
            print(f"Reload response: {response.json()}")

observer = Observer()
observer.schedule(ModelFileHandler(), path=".", recursive=False)
observer.start()
```

## Training Schedule Configuration

### Change Training Frequency

Edit the cron schedule:

```bash
crontab -e
```

**Examples**:

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Every 5 minutes | `*/5 * * * *` | Current setting |
| Every 10 minutes | `*/10 * * * *` | Less frequent |
| Every hour | `0 * * * *` | Hourly at minute 0 |
| Every 6 hours | `0 */6 * * *` | 4 times per day |
| Daily at 2 AM | `0 2 * * *` | Once per day |
| Every 30 minutes | `*/30 * * * *` | More frequent |

### Disable Automated Training

```bash
# Remove cron job
crontab -e
# Delete the line with train_model_cron.py

# Or comment it out (add # at beginning)
# */5 * * * * cd /path/to/seed-service && python3 scripts/train_model_cron.py
```

## Monitoring & Troubleshooting

### Check Training Status

```bash
# View latest training logs
tail -n 100 logs/training.log

# View all training runs today
grep "$(date +%Y-%m-%d)" logs/training.log

# Check for errors
grep -i error logs/training.log

# Check training duration
grep "Training completed successfully" logs/training.log
```

### Common Issues

#### 1. Training Takes Too Long

**Symptom**: Training runs overlap, lock file prevents execution

**Solution**:
- Reduce training frequency (change cron from `*/5` to `*/10` or `*/15`)
- Reduce epochs in `scripts/train_model_cron.py` (change `epochs=30` to `epochs=10`)
- Optimize feature matrices (reduce dimensionality)

#### 2. Database Connection Timeout

**Symptom**: Training fails with database errors

**Solution**:
- Check database connection in `.env` file
- Verify PostgreSQL is accessible from cron environment
- Add retry logic to training script

#### 3. Model Reload Fails

**Symptom**: `/admin/reload-model` returns 503 error

**Solution**:
- Check if model file exists: `ls -lh hybrid_model.pkl`
- Check file permissions: `chmod 644 hybrid_model.pkl`
- Check API logs: `tail -f logs/api.log`
- Restart API service

#### 4. Cron Job Not Running

**Symptom**: No new logs in `logs/training.log`

**Solution**:
```bash
# Check if cron is running
pgrep cron

# Check cron logs (macOS)
log show --predicate 'process == "cron"' --last 1h

# Check cron logs (Linux)
grep CRON /var/log/syslog

# Test training script manually
cd /Users/tanhtran/Documents/github/seed-service
python3 scripts/train_model_cron.py
```

### Performance Metrics

Monitor these metrics to optimize training:

```bash
# Training duration
grep "Training completed successfully" logs/training.log | tail -5

# Model file size
ls -lh hybrid_model*.pkl

# Number of backups
ls -1 hybrid_model_backup_*.pkl | wc -l

# Lock file status (should not exist when idle)
ls -lh /tmp/model_training.lock 2>/dev/null || echo "Not locked"
```

## Production Recommendations

### 1. Adjust Training Frequency

- **High Traffic**: Every 30-60 minutes
- **Medium Traffic**: Every 2-4 hours
- **Low Traffic**: Daily or twice daily
- **Testing/Development**: Every 5 minutes (current)

### 2. Add Monitoring

Set up alerts for:
- Training failures (check exit code in cron)
- Model file not updated for > 24 hours
- API reload failures
- Disk space (model backups accumulate)

### 3. Database Optimization

- Use read replicas for training (don't impact production DB)
- Schedule training during low-traffic periods
- Add indexes on interaction tables for faster queries

### 4. Model Validation

Before deploying a new model, validate it:

```python
# Add to training script
def validate_model(model, test_interactions):
    from evaluation.metrics import precision_at_k
    precision = precision_at_k(model, test_interactions, k=10)

    if precision < 0.05:  # Threshold
        logger.error(f"Model quality too low: {precision}")
        return False
    return True

# Only save if validation passes
if validate_model(model, test_data):
    save_model(model, temp_model_path)
else:
    logger.error("Model validation failed, keeping old model")
```

## Manual Training

To manually retrain the model outside of the cron schedule:

```bash
# Run training script directly
cd /Users/tanhtran/Documents/github/seed-service
python3 scripts/train_model_cron.py

# Or use the original pipeline
python3 pipeline/train_hybrid.py

# Then reload the API
curl -X POST http://localhost:8000/admin/reload-model
```

## Logs and Backups

### Log Files

| File | Purpose | Rotation |
|------|---------|----------|
| `logs/training.log` | Detailed training logs | Append-only |
| `logs/cron.log` | Cron execution output | Append-only |
| `logs/api.log` | API request logs | Daily (if configured) |

### Model Backups

- **Location**: Same directory as `hybrid_model.pkl`
- **Naming**: `hybrid_model_backup_YYYYMMDD_HHMMSS.pkl`
- **Retention**: Last 5 backups (configurable in `train_model_cron.py`)
- **Purpose**: Rollback if new model performs poorly

**Restore from backup**:
```bash
# List backups
ls -lt hybrid_model_backup_*.pkl | head -5

# Restore a specific backup
cp hybrid_model_backup_20251224_100500.pkl hybrid_model.pkl

# Reload API
curl -X POST http://localhost:8000/admin/reload-model
```

## Summary

✅ **Automated Training**: Model retrains every 5 minutes with fresh data
✅ **Zero Downtime**: Atomic file replacement ensures no service interruption
✅ **Hot-Reload**: API detects new model and reloads without restart
✅ **Safe Rollback**: Automatic backups allow quick recovery
✅ **Comprehensive Logging**: Full audit trail of training runs
✅ **Lock Prevention**: No concurrent training runs

## Next Steps

1. **Set up cron job**: Run `./scripts/setup_cron.sh`
2. **Monitor first run**: `tail -f logs/training.log`
3. **Test reload**: `curl -X POST http://localhost:8000/admin/reload-model`
4. **Adjust frequency**: Based on your traffic patterns
5. **Set up alerts**: Monitor training failures and model staleness

For API documentation, see [README_API.md](README_API.md).
