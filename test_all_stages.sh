#!/bin/bash
# Test all pipeline stages with PostgreSQL

DATE=$(date +%Y-%m-%d)
LOG_DIR="logs/$DATE"
mkdir -p "$LOG_DIR"

echo "=================================================="
echo "Testing Pipeline Stages 02-05 (PostgreSQL)"
echo "Date: $DATE"
echo "=================================================="

# Stage 02: Filter URLs by category
echo ""
echo ">>> Stage 02: Categorize URLs"
venv/bin/python stages/02_filter_for_newsletters.py --date $DATE 2>&1 | tee /tmp/stage02_test.log
STAGE02_EXIT=$?

if [ $STAGE02_EXIT -ne 0 ]; then
    echo "❌ Stage 02 failed with exit code $STAGE02_EXIT"
    exit 1
fi
echo "✓ Stage 02 completed"

# Stage 03: Rank URLs
echo ""
echo ">>> Stage 03: Rank URLs for 'daily' newsletter"
venv/bin/python stages/03_ranker.py --newsletter-name daily --date $DATE --categories economia politica 2>&1 | tee /tmp/stage03_test.log
STAGE03_EXIT=$?

if [ $STAGE03_EXIT -ne 0 ]; then
    echo "❌ Stage 03 failed with exit code $STAGE03_EXIT"
    exit 1
fi
echo "✓ Stage 03 completed"

# Stage 04: Extract content
echo ""
echo ">>> Stage 04: Extract article content"
venv/bin/python stages/04_extract_content.py --newsletter-name daily --date $DATE 2>&1 | tee /tmp/stage04_test.log
STAGE04_EXIT=$?

if [ $STAGE04_EXIT -ne 0 ]; then
    echo "❌ Stage 04 failed with exit code $STAGE04_EXIT"
    exit 1
fi
echo "✓ Stage 04 completed"

# Stage 05: Generate newsletters
echo ""
echo ">>> Stage 05: Generate newsletters"
venv/bin/python stages/05_generate_newsletters.py --newsletter-name daily --date $DATE 2>&1 | tee /tmp/stage05_test.log
STAGE05_EXIT=$?

if [ $STAGE05_EXIT -ne 0 ]; then
    echo "❌ Stage 05 failed with exit code $STAGE05_EXIT"
    exit 1
fi
echo "✓ Stage 05 completed"

echo ""
echo "=================================================="
echo "✓ All stages completed successfully!"
echo "=================================================="
echo ""
echo "Summary:"
grep -h "complete\|Total\|Generated" /tmp/stage0{2,3,4,5}_test.log | tail -20
