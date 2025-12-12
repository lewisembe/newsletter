# POC: Keyword-Based URL Search

**Proof of Concept** for searching news articles by keyword topics instead of scraping fixed media sources.

## Concept

**Current approach (Stage 01):**
```
sources.yml → Selenium scrapes FT/NYT/BBC → URLs → Pipeline
```

**POC approach:**
```
keyword_topics → Google News search → URLs → Pipeline
```

## Key Differences

| Aspect | Main Pipeline (sources) | POC (keywords) |
|--------|------------------------|----------------|
| **Input** | Fixed sources (sources.yml) | Keyword topics (config.yml) |
| **Method** | Selenium scraping | Google News RSS API |
| **Date** | `extracted_at` = today | `extracted_at` = real published date |
| **Source** | URL of media | `'keyword_search'` |
| **Tracking** | `source` column | `search_keyword` column |
| **Database** | `data/news.db` (production) | `poc_keyword_search/data/poc_news.db` |
| **Cost** | Free (scraping) | Free (Google News RSS) |
| **Coverage** | Limited to 9 sources | Entire Google News index |

## Architecture

```
poc_keyword_search/
├── 01_search_urls_by_topic.py    # Main script (Stage 01 alternative)
├── config.yml                     # Keyword topics configuration
├── init_poc_db.py                 # Database initialization
├── data/
│   └── poc_news.db               # Independent POC database
├── logs/
│   └── YYYY-MM-DD/
│       └── 01_search_urls_by_topic.log
└── src/
    └── google_news_searcher.py    # Google News API client
```

## Recent Updates (v3.0)

### New Features

1. **✅ Real URL Resolution** 🔗
   - **Now working!** Google News URLs are automatically decoded to original article URLs
   - Uses `googlenewsdecoder` library + Base64 fallback
   - Works on **all architectures** (x86_64, ARM64/Raspberry Pi)
   - Both URLs stored: `google_news_url` (redirect) and `url` (real article URL)
   - ~1 second per URL resolution

2. **Automatic Title Cleaning** ✂️
   - Removes " - SourceName" suffix from titles
   - Regex: `r'^(.*?)\s*-\s*[^-]+$'`
   - Falls back to original title if pattern doesn't match

3. **Default Classification** 🏷️
   - All Google News URLs classified as `contenido` by default
   - No LLM calls needed (faster, no cost)
   - Classification method: `google_news_default`
   - Rule name: `keyword_search`

4. **Customizable Time Windows** ⏰
   - Per-topic time window configuration
   - Options: `1h`, `1d`, `7d`, `30d`
   - Documented in config.yml with best practices

### Migration Required

If you have an existing POC database, run:

```bash
python poc_keyword_search/migrate_add_google_news_url.py
```

This adds the `google_news_url` column to store original redirect URLs.

## Setup

### 1. Install dependencies

```bash
pip install pygooglenews feedparser requests
```

(Already added to `requirements.txt`)

### 2. Initialize POC database

```bash
python poc_keyword_search/init_poc_db.py
```

This creates `poc_keyword_search/data/poc_news.db` with the same schema as the main database, plus the `search_keyword` and `google_news_url` columns.

### 3. Configure keyword topics

Edit `poc_keyword_search/config.yml`:

```yaml
keyword_topics:
  - topic: "inflación España"
    when: "1d"              # Time range: 1h, 1d, 7d, 30d
    max_results: 50         # Max articles
    priority: high

  - topic: "BCE tipos de interés"
    when: "1d"
    max_results: 30
    priority: high
```

## Usage

### Search all keywords from config

```bash
python poc_keyword_search/01_search_urls_by_topic.py --date 2025-11-24
```

### Search specific keywords only

```bash
python poc_keyword_search/01_search_urls_by_topic.py \
  --keywords "inflación España" "BCE tipos de interés"
```

### Skip URL classification (faster)

```bash
python poc_keyword_search/01_search_urls_by_topic.py --no-classification
```

## How It Works

### 1. Google News Search

```python
from poc_keyword_search.src.google_news_searcher import GoogleNewsSearcher

searcher = GoogleNewsSearcher(language="es", country="ES")
articles = searcher.search("inflación España", when="1d", max_results=50)
```

Returns:
```python
[
  {
    'url': 'https://elpais.com/economia/...',  # Resolved original URL
    'google_news_url': 'https://news.google.com/rss/articles/...',  # Redirect URL
    'title': 'La inflación baja al 2.8%',  # Cleaned (removed " - El País")
    'published_at': datetime(2025, 11, 24, 10, 30, tzinfo=UTC),  # Real date!
    'source': 'El País',
    'search_keyword': 'inflación España'
  },
  ...
]
```

### 2. URL Resolution & Title Cleaning

**URL Resolution:**
- Google News URLs are HTTP redirects: `https://news.google.com/rss/articles/...`
- Automatically resolved to original article URL using `requests.head()` with redirects
- Both URLs stored in database for traceability
- Fallback to Google News URL if resolution fails

**Title Cleaning:**
- Google News titles have format: `"Article Title - SourceName"`
- Automatically cleaned using regex: `r'^(.*?)\s*-\s*[^-]+$'`
- Example: `"La inflación baja al 2.8% - El País"` → `"La inflación baja al 2.8%"`
- Falls back to original title if pattern doesn't match

### 3. URL Classification

All Google News URLs are **automatically classified as `contenido`** by default:
- No LLM calls needed (faster, no cost)
- Classification method: `google_news_default`
- Rule name: `keyword_search`

This assumes Google News results are legitimate articles (not navigation/ads).

### 4. Database Storage

URLs are saved to POC database with:
- `url` = **resolved original URL** (final article URL)
- `google_news_url` = **Google News redirect URL** (for traceability)
- `title` = **cleaned title** (without source suffix)
- `extracted_at` = **article's real published date** (from Google News)
- `source` = `'keyword_search'` (identifies POC URLs)
- `search_keyword` = keyword that found it (e.g., "inflación España")
- `content_type` = `'contenido'` (always, by default)
- `classification_method` = `'google_news_default'`

## Database Schema

The POC database has the same schema as the main database, with these additions:

```sql
CREATE TABLE urls (
    -- ... (same columns as main database)

    google_news_url TEXT,     -- NEW (v2): Original Google News redirect URL
    search_keyword TEXT,      -- NEW: Tracks which keyword found this URL

    -- ...
)
```

**Query examples:**

```sql
-- Get all URLs found by specific keyword
SELECT url, title, extracted_at, source
FROM urls
WHERE search_keyword = 'inflación España'
ORDER BY extracted_at DESC;

-- Compare sources vs keywords
SELECT
  CASE
    WHEN search_keyword IS NULL THEN 'sources'
    ELSE 'keywords'
  END as method,
  COUNT(*) as count
FROM urls
GROUP BY method;

-- Top keywords by article count
SELECT search_keyword, COUNT(*) as count
FROM urls
WHERE search_keyword IS NOT NULL
GROUP BY search_keyword
ORDER BY count DESC
LIMIT 10;
```

## Integration with Main Pipeline

The POC database is **completely independent** from the main database, so you can:

1. **Test in isolation:** Run POC without affecting production
2. **Compare results:** Run both pipelines and compare coverage/quality
3. **Merge later:** Copy POC URLs to main database if desired

### Option A: Use POC database with Stages 02-05

Modify stages to point to POC database:

```python
# In stages/02_filter_for_newsletters.py
db = SQLiteURLDatabase("poc_keyword_search/data/poc_news.db")
```

### Option B: Copy POC URLs to main database

```python
# TODO: Create migration script to copy URLs
# with search_keyword preserved
```

## Advantages of Keyword Search

### 1. **Broader Coverage**
- Not limited to 9 sources
- Finds articles from any media in Google News index
- Can discover new sources automatically

### 2. **Topic-Focused**
- Search by specific topics (e.g., "inflación España")
- More relevant results (Google's ranking)
- Better for niche topics

### 3. **Real Dates**
- `extracted_at` = actual published date
- Can filter by real news date, not extraction date
- Historical searches possible (with `when="30d"`)

### 4. **No Scraping Issues**
- No Selenium/browser overhead
- No website changes breaking scraper
- No rate limiting per source

### 5. **Scalable**
- Add new keywords without coding
- Parallel searches possible
- Lower infrastructure requirements

## Limitations

### 1. **Google News Dependency**
- Relies on Google News indexing
- Subject to Google's filtering/ranking
- Potential rate limits (be respectful)

### 2. **Less Editorial Control**
- Can't whitelist/blacklist specific sources easily
- Quality varies (Google's decision)
- May include blogs, opinion pieces

### 3. **Language/Regional Bias**
- Results depend on `language` and `country` settings
- May miss regional media not in Google News

### 4. ✅ **URL Resolution (Now Working!)**

**Solution:** Google News URLs are now automatically decoded to real article URLs using the `googlenewsdecoder` library.

**How it works:**
1. Google News URLs (`https://news.google.com/rss/articles/CBMi...`) are Base64-encoded redirects
2. The decoder extracts the original article URL from the encoded data
3. Fallback to manual Base64 decoding if the library fails
4. Both URLs are stored: `url` (real) and `google_news_url` (original redirect)

**Performance:**
- ~1 second per URL (vs. 2-3 seconds with Selenium)
- Works on all architectures (x86_64, ARM64, Raspberry Pi)
- No browser or geckodriver needed

**Configuration:**

```yaml
search_config:
  resolve_urls: true  # Default: enabled (decodes to real URLs)
                      # Set to false to keep Google News URLs
```

**Installation:**

```bash
pip install googlenewsdecoder>=0.1.7
```

Already included in `requirements.txt`.

### 5. **No Full Content**
- Only gets URL + title + metadata
- Still need Stage 04 for full content extraction
- Some URLs may be paywalled

## Comparison with Main Pipeline

### Test Script

```bash
# Run both pipelines on same day
python stages/01_extract_urls.py --date 2025-11-24
python poc_keyword_search/01_search_urls_by_topic.py --date 2025-11-24

# Compare results
sqlite3 data/news.db "SELECT COUNT(*) FROM urls WHERE DATE(extracted_at) = '2025-11-24';"
sqlite3 poc_keyword_search/data/poc_news.db "SELECT COUNT(*) FROM urls WHERE DATE(extracted_at) = '2025-11-24';"
```

### Metrics to Compare

- **Coverage:** Which finds more relevant articles?
- **Quality:** Which has better signal/noise ratio?
- **Speed:** Which is faster?
- **Cost:** Token usage (if using LLM classification)
- **Diversity:** Source distribution
- **Timeliness:** How fresh are the articles?

## Configuration Reference

### `config.yml`

```yaml
# Database
database:
  path: "poc_keyword_search/data/poc_news.db"

# Google News
search_config:
  language: "es"           # es, en, fr
  country: "ES"            # ES, US, FR, GB
  rate_limit_delay: 1.0    # Seconds between requests

# Keyword topics
keyword_topics:
  - topic: "string"        # Search query
    when: "1d"             # 1h, 1d, 7d, 30d
    max_results: 50        # Max articles per keyword
    priority: high         # Metadata (not used yet)
    description: "..."     # Human-readable description
```

### Google News Time Ranges

Time windows are **fully customizable per topic** in config.yml:

- `1h` - Last hour (real-time breaking news)
- `1d` - Last 24 hours (recommended for daily execution)
- `7d` - Last 7 days (weekly topics or less frequent news)
- `30d` - Last 30 days (monthly topics or rare events)

**Best Practices:**
- Daily execution: Use `"1d"` for most topics
- Hourly updates: Use `"1h"` for breaking news
- Weekly digests: Use `"7d"` for slower-moving topics
- Elections/events: Use `"7d"` or `"30d"` for less frequent coverage

## Logs

Logs are saved to:
```
poc_keyword_search/logs/YYYY-MM-DD/01_search_urls_by_topic.log
```

Example output:
```
2025-11-24 14:30:00 - INFO - POC KEYWORD SEARCH - Stage 01 Alternative
2025-11-24 14:30:01 - INFO - Total keywords to search: 9
2025-11-24 14:30:02 - INFO - [1/9] Searching: 'inflación España' (when=1d)
2025-11-24 14:30:03 - INFO - Found 47 results for 'inflación España'
2025-11-24 14:30:04 - INFO - ✓ 'inflación España': 42 new, 5 duplicates, 40 content, 2 no_content
...
2025-11-24 14:35:00 - INFO - POC STAGE 01 COMPLETED
2025-11-24 14:35:00 - INFO - Keywords searched: 9
2025-11-24 14:35:00 - INFO - New articles saved: 243
2025-11-24 14:35:00 - INFO -   - Content URLs: 231
2025-11-24 14:35:00 - INFO -   - No-content URLs: 12
```

## Next Steps

### Immediate
1. ✅ Create POC structure
2. ✅ Implement Google News searcher
3. ✅ Implement Stage 01 alternative
4. ⏳ Test with real keywords
5. ⏳ Compare with main pipeline results

### Future Enhancements
- [ ] Adapt Stages 02-05 to work with POC database
- [ ] Create comparison dashboard
- [ ] Add DuckDuckGo/SerpAPI as fallback searchers
- [ ] Implement hybrid mode (sources + keywords)
- [ ] Auto-suggest keywords from trending topics
- [ ] Merge POC URLs to main database (if successful)

## Troubleshooting

### "POC database not found"
```bash
python poc_keyword_search/init_poc_db.py
```

### "pygooglenews not installed"
```bash
pip install pygooglenews feedparser
```

### No results found
- Check `language` and `country` in config.yml
- Try broader keywords (e.g., "España economía" vs "inflación subyacente")
- Increase `when` time range (e.g., "7d" instead of "1d")

### Rate limiting from Google
- Increase `rate_limit_delay` in config.yml
- Reduce number of keywords
- Don't run too frequently (respect Google's ToS)

## License

Same as main newsletter_utils pipeline.
