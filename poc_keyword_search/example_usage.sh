#!/bin/bash
# Example usage of POC Keyword Search

echo "====================================="
echo "POC Keyword Search - Example Usage"
echo "====================================="
echo ""

# 1. Initialize database (only needed once)
echo "1. Initialize POC database (if not done yet):"
echo "   python poc_keyword_search/init_poc_db.py"
echo ""

# 2. Search with specific keywords
echo "2. Search specific keywords:"
echo "   python poc_keyword_search/01_search_urls_by_topic.py --keywords \"inflación España\" \"BCE tipos de interés\""
echo ""

# 3. Search all keywords from config
echo "3. Search all keywords from config.yml:"
echo "   python poc_keyword_search/01_search_urls_by_topic.py --date 2025-11-24"
echo ""

# 4. Skip classification (faster, all URLs = contenido)
echo "4. Search without classification:"
echo "   python poc_keyword_search/01_search_urls_by_topic.py --no-classification"
echo ""

# 5. Query database
echo "5. Query results:"
echo "   sqlite3 poc_keyword_search/data/poc_news.db \"SELECT search_keyword, COUNT(*) FROM urls GROUP BY search_keyword;\""
echo ""

# 6. Compare with main pipeline
echo "6. Compare with main pipeline:"
echo "   # Run both:"
echo "   python stages/01_extract_urls.py --date 2025-11-24"
echo "   python poc_keyword_search/01_search_urls_by_topic.py --date 2025-11-24"
echo ""
echo "   # Compare counts:"
echo "   sqlite3 data/news.db \"SELECT COUNT(*) FROM urls WHERE DATE(extracted_at) = '2025-11-24';\""
echo "   sqlite3 poc_keyword_search/data/poc_news.db \"SELECT COUNT(*) FROM urls;\""
echo ""

echo "====================================="
echo "See poc_keyword_search/README.md for full documentation"
echo "====================================="
