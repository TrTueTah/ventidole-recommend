#!/bin/bash
#
# Setup Cron Job for Model Retraining
# This script configures a cron job to retrain the recommendation model every 5 minutes
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TRAINING_SCRIPT="$SCRIPT_DIR/train_model_cron.py"
PYTHON_PATH=$(which python3 || which python)

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Model Retraining Cron Job Setup${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Check if training script exists
if [ ! -f "$TRAINING_SCRIPT" ]; then
    echo -e "${RED}Error: Training script not found at $TRAINING_SCRIPT${NC}"
    exit 1
fi

# Make sure training script is executable
chmod +x "$TRAINING_SCRIPT"
echo -e "${GREEN}✓${NC} Training script is executable"

# Create logs directory if it doesn't exist
LOGS_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOGS_DIR"
echo -e "${GREEN}✓${NC} Logs directory created at $LOGS_DIR"

# Check Python version
PYTHON_VERSION=$($PYTHON_PATH --version 2>&1)
echo -e "${GREEN}✓${NC} Python found: $PYTHON_VERSION"

# Create the cron job entry
CRON_JOB="*/5 * * * * cd $PROJECT_DIR && $PYTHON_PATH $TRAINING_SCRIPT >> $LOGS_DIR/cron.log 2>&1"
CRON_COMMENT="# Recommendation model retraining every 5 minutes"

echo ""
echo -e "${YELLOW}Cron job to be added:${NC}"
echo "$CRON_COMMENT"
echo "$CRON_JOB"
echo ""

# Check if cron job already exists
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "$TRAINING_SCRIPT" || true)

if [ -n "$EXISTING_CRON" ]; then
    echo -e "${YELLOW}Warning: A cron job for this training script already exists:${NC}"
    echo "$EXISTING_CRON"
    echo ""
    read -p "Do you want to replace it? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Setup cancelled.${NC}"
        exit 0
    fi

    # Remove existing cron job
    (crontab -l 2>/dev/null | grep -v -F "$TRAINING_SCRIPT") | crontab -
    echo -e "${GREEN}✓${NC} Removed existing cron job"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_COMMENT"; echo "$CRON_JOB") | crontab -
echo -e "${GREEN}✓${NC} Cron job added successfully"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "The model will be retrained every 5 minutes."
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  • Training script: $TRAINING_SCRIPT"
echo "  • Logs directory: $LOGS_DIR"
echo "  • Training log: $LOGS_DIR/training.log"
echo "  • Cron log: $LOGS_DIR/cron.log"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  • View cron jobs:    crontab -l"
echo "  • Edit cron jobs:    crontab -e"
echo "  • Remove cron job:   crontab -e (then delete the line)"
echo "  • View training log: tail -f $LOGS_DIR/training.log"
echo "  • View cron log:     tail -f $LOGS_DIR/cron.log"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Wait for the first training run (within 5 minutes)"
echo "  2. Check logs: tail -f $LOGS_DIR/training.log"
echo "  3. Verify model file is updated: ls -lh $PROJECT_DIR/hybrid_model.pkl"
echo "  4. Reload API model: curl -X POST http://localhost:8000/admin/reload-model"
echo ""
echo -e "${GREEN}Happy recommending! 🚀${NC}"
