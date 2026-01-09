# FastAPI Recommendation Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including cron
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory for cron jobs
RUN mkdir -p /app/logs

# Setup cron job for model retraining (every 5 minutes)
RUN echo "*/5 * * * * cd /app && /usr/local/bin/python /app/scripts/train_model_cron.py >> /app/logs/cron.log 2>&1" > /etc/cron.d/model-retrain && \
    chmod 0644 /etc/cron.d/model-retrain && \
    crontab /etc/cron.d/model-retrain && \
    touch /app/logs/cron.log

# Make scripts executable
RUN chmod +x /app/scripts/train_model_cron.py

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Create startup script to run both cron and uvicorn
RUN echo '#!/bin/bash\n\
# Start cron in background\n\
cron\n\
# Start FastAPI application\n\
exec uvicorn api.main:app --host 0.0.0.0 --port 8000' > /app/start.sh && \
    chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]
