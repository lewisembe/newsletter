#!/bin/bash
#
# Log and data cleanup script for newsletter_utils
#
# This script manages log rotation and cleanup to prevent disk space issues.
# It should be run periodically via cron or manually when needed.
#

set -euo pipefail

# Configuration
PROJECT_ROOT="/home/luis.martinezb/Documents/newsletter_utils"
LOG_RETENTION_DAYS=30
DATA_RETENTION_DAYS=90
DOCKER_LOG_MAX_SIZE="50m"

cd "$PROJECT_ROOT"

echo "=== Newsletter Utils Cleanup Script ==="
echo "Started at: $(date)"
echo ""

# 1. Cleanup old log directories (YYYY-MM-DD format)
echo "[1/6] Cleaning up log directories older than ${LOG_RETENTION_DAYS} days..."
find logs/ -type d -name "2025-*" -mtime +${LOG_RETENTION_DAYS} -exec rm -rf {} + 2>/dev/null || true
echo "  ✓ Old log directories removed"

# 2. Cleanup old newsletter output files
echo "[2/6] Cleaning up newsletter files older than ${DATA_RETENTION_DAYS} days..."
find data/newsletters/ -type f \( -name "*.json" -o -name "*.md" \) -mtime +${DATA_RETENTION_DAYS} -delete 2>/dev/null || true
echo "  ✓ Old newsletter files removed"

# 3. Cleanup Python cache
echo "[3/6] Removing Python cache directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "  ✓ Python cache cleaned"

# 4. Cleanup old Docker logs (requires sudo)
echo "[4/6] Cleaning up Docker container logs..."
if command -v docker &> /dev/null; then
    # Truncate large container logs
    for container in $(docker ps -q); do
        container_name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/^\///')
        log_file="/var/lib/docker/containers/${container}/${container}-json.log"
        if [ -f "$log_file" ]; then
            log_size=$(du -h "$log_file" 2>/dev/null | cut -f1)
            echo "  - $container_name: $log_size"
        fi
    done

    # Note: To actually truncate logs, use:
    # sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
    echo "  ℹ To truncate Docker logs, run: sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log"
else
    echo "  ⚠ Docker not found, skipping"
fi

# 5. Cleanup old POC directories
echo "[5/6] Checking old/archived directories..."
du -sh old/ poc_keyword_search/ 2>/dev/null || echo "  No old directories found"
echo "  ℹ Review 'old/' and 'poc_keyword_search/' manually if they're too large"

# 6. Docker system cleanup
echo "[6/6] Docker system cleanup..."
if command -v docker &> /dev/null; then
    echo "  Current Docker disk usage:"
    docker system df
    echo ""
    echo "  ℹ To reclaim space, run: docker system prune -a --volumes"
else
    echo "  ⚠ Docker not found, skipping"
fi

echo ""
echo "=== Cleanup Summary ==="
echo "Logs directory size:      $(du -sh logs/ 2>/dev/null | cut -f1)"
echo "Data directory size:      $(du -sh data/ 2>/dev/null | cut -f1)"
echo "Total project size:       $(du -sh . 2>/dev/null | cut -f1)"
echo ""
echo "Completed at: $(date)"
