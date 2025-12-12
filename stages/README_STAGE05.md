# Stage 05: Generate Newsletters - AI-Powered News Digest Creation

> **Status:** ✅ Production Ready | **Created:** 2025-11-13 | **Updated:** 2025-11-19 (3-step approach)

## 📋 Overview

Stage 05 transforms ranked URLs and extracted article content into engaging, narrative-style newsletters. Using a **3-step LLM approach**, this stage guarantees 100% URL coverage with premium narrative quality while optimizing costs.

**Key Features:**
- 📝 **Narrative prose generation** - No bullet lists, just flowing storytelling
- ✅ **100% URL coverage** - 3-step approach ensures all articles are mentioned
- 🎯 **Smart content selection** - Full content for top N articles, headlines for the rest
- 💎 **Premium quality** - Uses gpt-4o for narrative, gpt-4o-mini for summaries
- 🎨 **Template system** - Multiple prompt templates for different styles
- 📊 **Dual output formats** - Generate Markdown and/or HTML
- 💾 **Database integration** - Full tracking in `pipeline_runs` table
- 🔧 **Highly configurable** - Per-newsletter customization via YAML
- 💰 **Cost optimized** - ~$0.03/newsletter with premium quality

## 🔄 Process Flow (3-Step Approach)

```
Input: Ranked JSON from Stage 03
  └─> Read ranked URLs with IDs
  └─> Query database for article metadata
  └─> Separate: Articles WITH content vs WITHOUT content

  ┌─ STEP 1: Summarize with gpt-4o-mini (cost-effective) ─────────┐
  │  For each article WITH full content (e.g., 7 articles):       │
  │    └─> Generate 150-200 word executive summary                │
  │    └─> Extract key facts, data, context                       │
  │    └─> Cost: ~$0.001 per article                              │
  └────────────────────────────────────────────────────────────────┘

  ┌─ STEP 2: Main narrative with gpt-4o (premium quality) ────────┐
  │  Input: Article summaries from Step 1                         │
  │    └─> Generate in-depth narrative for main stories           │
  │    └─> Organize by category (Economía, Finanzas, etc.)        │
  │    └─> Create introduction and thematic sections              │
  │    └─> Cost: ~$0.015 for main narrative                       │
  └────────────────────────────────────────────────────────────────┘

  ┌─ STEP 3: Complete with headlines using gpt-4o (coverage) ─────┐
  │  Input: Main narrative + remaining headlines (e.g., 13)       │
  │    └─> Integrate ALL headlines not yet mentioned              │
  │    └─> Add 1-3 sentences per headline with context            │
  │    └─> Guarantee 100% URL coverage                            │
  │    └─> Cost: ~$0.013 for completion                           │
  └────────────────────────────────────────────────────────────────┘

  └─> Render output using Jinja2 templates
  └─> Save to data/newsletters/
  └─> Update pipeline_runs in database

Output: newsletter_{name}_{date}_{timestamp}.{md|html}
Total Cost: ~$0.031/newsletter (vs $0.002 single-pass with 50% coverage)
```

## 🚀 Why 3-Step Approach?

**Problem with single-pass generation:**
- ❌ LLM ignores headlines without full content (only 50-60% coverage)
- ❌ Large context overwhelms the model
- ❌ Quality suffers when forcing everything into one prompt

**Solution - 3 steps:**
1. **gpt-4o-mini summaries** → Compress full articles, save expensive tokens
2. **gpt-4o main narrative** → Premium storytelling with summaries
3. **gpt-4o completion** → Force 100% coverage of remaining headlines

**Results:**
- ✅ **100% URL coverage** (20/20 URLs mentioned vs 11/20 before)
- ✅ **Premium quality** (gpt-4o narrative)
- ✅ **Reasonable cost** (~$0.03/newsletter = $0.90/month for daily)
- ✅ **Small input tokens** for expensive calls (summaries vs full text)

## 🎯 Input Requirements

### Required Input

**Ranked JSON file from Stage 03:**
```json
{
  "run_date": "2025-11-13",
  "generated_at": "2025-11-13T14:30:52Z",
  "total_primary": 25,
  "ranked_urls": [
    {
      "rank": 1,
      "id": 12345,
      "url": "https://...",
      "title": "Article title",
      "categoria_tematica": "tecnologia",
      "source": "ft.com",
      "score": 95,
      "reason": "High relevance..."
    }
  ]
}
```

**Database content (from Stage 04):**
- `full_content` field populated for top N articles
- `extraction_status` = 'success'
- `word_count` available
- `content_extraction_method` metadata

### What Happens if Content is Missing?

Stage 05 gracefully handles missing content:
- Articles without `full_content` are mentioned briefly (headline only)
- Minimum requirement: At least 1 article with full content
- Warning logged if fewer than expected articles have content
- Newsletter generation continues with available content

## 📤 Output

### Output Files

**Location:** `data/newsletters/`

**Naming convention:**
```
newsletter_{newsletter_name}_{date}_{timestamp}.{ext}
```

**Examples:**
```
newsletter_tech_daily_2025-11-13_143052.md
newsletter_tech_daily_2025-11-13_143052.html
newsletter_finance_weekly_2025-11-13_101530.md
```

### Output Formats

#### Markdown Format (`.md`)
- Clean, readable text format
- Suitable for Telegram, Slack, email clients
- GitHub-flavored Markdown
- Embedded links: `[title](url)`
- Source citations in text

#### HTML Format (`.html`)
- Styled, responsive email-ready HTML
- Professional newsletter design
- Mobile-friendly layout
- Hyperlinked sources
- Article metadata display

#### Context Report (`.json`) - NEW! ✨
**Naming:** `context_report_{newsletter_name}_{date}_{timestamp}.json`

Automatically generated execution report containing:
- **Configuration used** (categories, models, parameters)
- **Initial ranked order** from Stage 03
- **Content extraction results** (success/failure stats)
- **Full content** of successfully extracted articles
- **Categories** for each URL
- **Execution metadata** (methods, errors, word counts)

**Purpose:** Debugging, verification, and auditing of newsletter generation.

**See:** `stages/CONTEXT_REPORT_FORMAT.md` for detailed documentation.

### Newsletter Structure

Both formats follow this structure:

```markdown
# Newsletter Title

> Description

**Fecha:** 2025-11-13
**Artículos totales:** 25 (10 con contenido completo)

---

## [LLM-Generated Introduction]

[2-3 paragraphs with overview and context]

## [Thematic Block 1]

[Narrative prose weaving related articles together]
Según [Financial Times](url), ... El artículo de [BBC](url) señala...

## [Thematic Block 2]

[More narrative content]

## [Conclusion]

[1-2 paragraphs wrapping up]

---

## 📋 Fuentes de este newsletter

1. [Article Title](url) - source.com ✓
2. [Article Title](url) - other.com
...
```

**Key characteristics:**
- Narrative prose (not bullet lists)
- Integrated source citations
- Thematic organization
- Context and connections between stories
- Professional but accessible tone

## 🛠️ Command-Line Usage

### Basic Usage

```bash
venv/bin/python stages/05_generate_newsletters.py \
  --input data/processed/ranked_2025-11-13_tech_143052.json \
  --newsletter-name tech_daily
```

### Full Options

```bash
venv/bin/python stages/05_generate_newsletters.py \
  --input data/processed/ranked_2025-11-13_tech_143052.json \
  --newsletter-name tech_daily \
  --output-format both \
  --template tech_focus \
  --top-with-content 15 \
  --force \
  --verbose
```

### Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `--input` | ✅ | Path to ranked JSON from Stage 03 | - |
| `--newsletter-name` | ✅ | Newsletter name (for output filename) | - |
| `--output-format` | ❌ | Output format: `markdown`, `html`, or `both` | `markdown` |
| `--template` | ❌ | Prompt template name | `default` |
| `--top-with-content` | ❌ | Number of articles with full content | 10 |
| `--skip-llm` | ❌ | Skip LLM (template only, for testing) | False |
| `--force` | ❌ | Force regeneration if output exists | False |
| `--verbose` | ❌ | Enable verbose logging | False |

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Stage 05: Newsletter Generation
MODEL_WRITER=gpt-4o-mini              # LLM model for generation
STAGE05_TOP_WITH_CONTENT=10           # Default articles with full content
STAGE05_MAX_CONTENT_TOKENS=1000       # Max tokens per article (truncation)
STAGE05_MAX_SUMMARY_LENGTH=150        # Reserved for future use
```

### Newsletter Config (newsletters.yml)

```yaml
stage05:
  # Enable/disable newsletter generation
  enabled: true

  # Output format: 'markdown', 'html', or 'both'
  output_format: "markdown"

  # Prompt template (from templates/prompts/)
  template: "default"  # Options: default, tech_focus, concise

  # Newsletter metadata
  title: "Tech Daily Digest"
  description: "Your daily dose of technology news"

  # Number of top articles with full content
  top_with_content: 10

  # Maximum tokens per article content
  max_content_tokens: 1000

  # Override LLM model
  model_writer: "gpt-4o"  # Use gpt-4o for higher quality

  # Skip LLM calls (testing mode)
  skip_llm: false

  # Force regeneration
  force: false
```

## 🎨 Template System

### Prompt Templates

**Location:** `templates/prompts/`

Stage 05 uses a template-based prompt system for maximum flexibility.

#### Available Templates

##### 1. **default** - Radio Host Style
```json
{
  "name": "default",
  "description": "Default newsletter - Radio host narrative",
  "system_prompt": "Eres un analista de noticias profesional...",
  "user_prompt_template": "Fecha: {date}..."
}
```

**Best for:** General news, diverse audiences
**Tone:** Professional, conversational, engaging
**Structure:** Intro → Thematic blocks → Conclusion

##### 2. **tech_focus** - Technical Analysis
```json
{
  "name": "tech_focus",
  "description": "Tech-focused with deeper analysis",
  "system_prompt": "Eres un analista tecnológico senior...",
  "user_prompt_template": "..."
}
```

**Best for:** Tech newsletters, professional audiences
**Tone:** Technical but accessible, analytical
**Focus:** Implications, trends, strategic insights

##### 3. **concise** - Executive Briefing
```json
{
  "name": "concise",
  "description": "Quick morning briefing style",
  "system_prompt": "Eres un editor de noticias para ejecutivos...",
  "user_prompt_template": "..."
}
```

**Best for:** Quick updates, busy executives
**Tone:** Direct, efficient, dense
**Structure:** Short paragraphs, maximum information density

### Creating Custom Templates

1. Create new JSON file in `templates/prompts/`
2. Follow the structure:
```json
{
  "name": "my_template",
  "description": "Brief description",
  "system_prompt": "System prompt with personality and instructions",
  "user_prompt_template": "User prompt with {context}, {date}, {newsletter_name}"
}
```

3. Use in config:
```yaml
stage05:
  template: "my_template"
```

### Output Templates (Jinja2)

**Location:** `templates/outputs/`

- `newsletter.md` - Markdown output template
- `newsletter.html` - HTML output template

**Available variables:**
- `newsletter_name` - Newsletter title
- `newsletter_description` - Description
- `date` - Run date
- `generated_at` - Generation timestamp
- `content` - LLM-generated content
- `articles` - List of article dictionaries
- `total_articles` - Total count
- `articles_with_content` - Count with full content

## 🧠 LLM Context Building

### Context Structure

Stage 05 builds a structured context for the LLM:

```
FECHA: 2025-11-13
TOTAL ARTÍCULOS: 25

=== ARTÍCULOS PRINCIPALES (con contenido completo): 10 ===

## [1] Article Title
- Fuente: ft.com
- Categoría: tecnologia
- URL: https://...
- Palabras: 847

**Contenido:**
[Full article text, truncated to max_content_tokens]

--------------------------------------------------------------------------------

[... 9 more articles with full content ...]

=== OTROS TITULARES (solo títulos): 15 ===

[11] Headline text (bbc.com) - tecnologia
[12] Another headline (economist.com) - economia
[... rest of headlines ...]
```

### Content Truncation

To manage token budgets, article content is intelligently truncated:

```python
def truncate_content(content: str, max_tokens: int = 1000) -> str:
    """
    Takes 70% from beginning + 30% from end
    Most important info usually at start and conclusion
    """
```

**Example:**
- Article: 3000 words (~4000 tokens)
- Max tokens: 1000
- Result: First ~700 tokens + last ~300 tokens + truncation marker

This preserves:
- Lead paragraph (who, what, when, where, why)
- Key details from beginning
- Conclusion and final thoughts

## 📊 Database Integration

### pipeline_runs Table

Stage 05 tracks execution in `pipeline_runs`:

```sql
INSERT INTO pipeline_runs (
  newsletter_name,
  run_date,
  stage,
  status,
  output_file,
  started_at,
  completed_at
) VALUES (
  'tech_daily',
  '2025-11-13',
  5,
  'completed',
  'data/newsletters/newsletter_tech_daily_2025-11-13_143052.md',
  '2025-11-13T14:30:50Z',
  '2025-11-13T14:32:15Z'
)
```

**Status values:**
- `pending` - Not yet started
- `running` - Currently executing
- `completed` - Successfully finished
- `failed` - Error occurred

### Query Examples

```python
# Get Stage 05 run for newsletter
run = db.get_pipeline_run('tech_daily', '2025-11-13', 5)

# Check if newsletter was generated
if run and run['status'] == 'completed':
    print(f"Newsletter at: {run['output_file']}")
```

## 🔧 Token Management

### Token Tracking

All LLM calls are tracked in `logs/token_usage.csv`:

```csv
timestamp,stage,operation,model,prompt_tokens,completion_tokens,total_tokens,cost_usd,run_date
2025-11-13T14:30:52Z,05,generate_newsletter,gpt-4o-mini,8543,1247,9790,0.0024,2025-11-13
```

### Cost Optimization

**Strategies to reduce costs:**

1. **Use gpt-4o-mini for generation** (default)
   - 15x cheaper than gpt-4o
   - Excellent quality for newsletters

2. **Adjust `max_content_tokens`**
   - Lower = fewer input tokens
   - Trade-off: Less context for LLM

3. **Reduce `top_with_content`**
   - Include fewer full articles
   - More headlines-only

4. **Use `skip_llm` for testing**
   - Validates everything except LLM call
   - Zero cost

**Example costs (approximate):**

| Config | Tokens | Cost (gpt-4o-mini) | Cost (gpt-4o) |
|--------|--------|-------------------|---------------|
| 5 articles, 500 tokens each | ~4,000 | $0.001 | $0.015 |
| 10 articles, 1000 tokens each | ~12,000 | $0.003 | $0.045 |
| 15 articles, 1000 tokens each | ~17,000 | $0.004 | $0.065 |

## 🚨 Error Handling

### Common Errors

#### 1. No Articles with Content

**Error:**
```
ERROR: No articles have full content. Did Stage 04 run successfully?
```

**Solution:**
- Verify Stage 04 completed successfully
- Check `extraction_status` in database
- Run Stage 04 with `--force` if needed

#### 2. Template Not Found

**Error:**
```
ERROR: Template my_template not found
```

**Solution:**
- Verify template file exists: `templates/prompts/my_template.json`
- Check JSON syntax is valid
- Falls back to `default` template

#### 3. LLM API Error

**Error:**
```
ERROR: Error calling LLM: Rate limit exceeded
```

**Solution:**
- Wait and retry (automatic rate limiting in LLMClient)
- Check OpenAI API key is valid
- Verify API quota/billing

#### 4. Output Already Exists

**Warning:**
```
Newsletter file already exists: data/newsletters/newsletter_tech_daily_2025-11-13_143052.md
Use --force to overwrite
```

**Solution:**
- Use `--force` flag to regenerate
- Or delete existing file manually

### Graceful Degradation

Stage 05 handles partial failures:

```python
# Article extraction failures
if len(articles_with_content) == 0:
    return error  # Cannot generate

if len(articles_with_content) < top_with_content:
    logger.warning(f"Only {len(articles_with_content)} articles have content")
    # Continue with available content

# Template not found
try:
    template = load_prompt_template(args.template)
except:
    logger.warning("Using default template")
    template = load_prompt_template('default')
```

## 📊 Context Reports - Debugging & Verification

### Overview

Every newsletter generation produces an **execution context report** saved alongside the newsletter. This JSON file contains comprehensive debugging and verification information.

**Purpose:**
- 🔍 **Debugging** - Identify why content wasn't extracted or newsletters are incomplete
- ✅ **Verification** - Ensure execution was correct (categories match, extraction rates, etc.)
- 📈 **Auditing** - Track what content was used and how

**Location:** `data/newsletters/context_report_{name}_{date}_{timestamp}.json`

### Report Contents

```json
{
  "metadata": {
    "newsletter_name": "noticias_diarias",
    "run_date": "2025-11-14",
    "generated_at": "2025-11-14T10:30:45+01:00"
  },
  "configuration": {
    "max_articles": 20,
    "top_with_content": 10,
    "expected_categories": ["Economía", "Política"],
    "ranked_file_categories": ["Economía", "Política"],
    "template": "default",
    "model_writer": "gpt-4o-mini",
    "success_rate": 80.0
  },
  "content_extraction": {
    "extraction_stats": {
      "total_requested": 10,
      "total_success": 8,
      "total_failed": 2,
      "success_rate": 80.0
    },
    "urls_successfully_extracted": [...],
    "urls_failed_extraction": [...]
  },
  "articles": [
    {
      "processing_rank": 1,
      "url": "https://...",
      "title": "Article Title",
      "category": "Economía",
      "has_full_content": true,
      "extraction_method": "xpath_cache",
      "word_count": 850,
      "full_content": "..."
    }
  ]
}
```

### Quick Verification Commands

```bash
# Check extraction success rate
cat context_report_*.json | jq '.content_extraction.extraction_stats'

# Verify categories match
cat context_report_*.json | jq '.configuration | {expected_categories, ranked_file_categories}'

# List failed extractions with errors
cat context_report_*.json | jq '.content_extraction.urls_failed_extraction'

# Count articles by category
cat context_report_*.json | jq '.articles | group_by(.category) | map({category: .[0].category, count: length})'

# View extraction methods used
cat context_report_*.json | jq '.articles | map(select(.extraction_method != null)) | group_by(.extraction_method) | map({method: .[0].extraction_method, count: length})'
```

### Verification Checklist

After generating a newsletter, check the context report for:

- [ ] **Category match:** `expected_categories` == `ranked_file_categories`
- [ ] **Extraction rate:** `success_rate` >= 70% (ideally >80%)
- [ ] **Configuration:** `total_requested` == `top_with_content`
- [ ] **Articles processed:** `max_articles` matches config
- [ ] **Valid categories:** All articles have assigned categories
- [ ] **Newsletter size:** `word_count` > 500
- [ ] **Content availability:** Articles with `has_full_content: true` have non-empty `full_content`
- [ ] **Error messages:** Failed extractions have descriptive `extraction_error`

### Common Issues Detected

#### Category Mismatch
```json
{
  "expected_categories": ["Economía", "Política"],
  "ranked_file_categories": ["Economía", "Política", "Sociedad"]
}
```
**Fix:** Re-run orchestrator with `--force`

#### Low Extraction Rate
```json
{
  "success_rate": 30.0
}
```
**Fix:** Check Stage 04 logs, update `xpath_cache.yml`, verify auth cookies

#### Missing Content
```json
{
  "extraction_status": "pending",
  "has_full_content": false
}
```
**Fix:** Stage 04 didn't run or failed - re-execute with `--force`

### Full Documentation

For complete documentation on the context report format and all available fields:

**See:** [`stages/CONTEXT_REPORT_FORMAT.md`](./CONTEXT_REPORT_FORMAT.md)

## 📈 Performance

### Execution Time

Typical execution times:

| Articles | LLM Model | Time |
|----------|-----------|------|
| 5 articles | gpt-4o-mini | 15-25s |
| 10 articles | gpt-4o-mini | 25-40s |
| 15 articles | gpt-4o-mini | 40-60s |
| 10 articles | gpt-4o | 40-80s |

**Bottleneck:** LLM API call (~90% of execution time)

### Optimization Tips

1. **Batch newsletters**
   - Run multiple newsletters sequentially
   - Amortize startup costs

2. **Adjust max_content_tokens**
   - Lower tokens = faster responses
   - Less context for LLM

3. **Use markdown format**
   - Faster than HTML rendering
   - Smaller file sizes

## 🧪 Testing

### Manual Testing

```bash
# Test with skip-llm (validate everything except LLM)
venv/bin/python stages/05_generate_newsletters.py \
  --input data/processed/ranked_2025-11-13_tech.json \
  --newsletter-name test \
  --skip-llm \
  --verbose

# Test specific template
venv/bin/python stages/05_generate_newsletters.py \
  --input data/processed/ranked_2025-11-13_tech.json \
  --newsletter-name test \
  --template tech_focus \
  --force

# Generate both formats
venv/bin/python stages/05_generate_newsletters.py \
  --input data/processed/ranked_2025-11-13_tech.json \
  --newsletter-name test \
  --output-format both
```

### Validation Checklist

✅ **Pre-run validation:**
- [ ] Ranked JSON exists and is valid
- [ ] Database has content for top N articles
- [ ] Template exists (or using default)
- [ ] OpenAI API key is set

✅ **Post-run validation:**
- [ ] Newsletter file created
- [ ] File size > 0 bytes
- [ ] Markdown syntax valid
- [ ] Links are functional
- [ ] Source citations present
- [ ] Database tracking updated

## 🎯 Integration with Orchestrator

### Orchestrator Execution

```bash
# Run complete pipeline (includes Stage 05)
venv/bin/python stages/orchestrator.py --config config/newsletters.yml
```

### Orchestrator Flow

```
Stage 01: Extract URLs (once for all newsletters)
  └─> For each newsletter:
      ├─> Stage 02: Filter & Classify
      ├─> Stage 03: Ranker
      ├─> Stage 04: Extract Content
      └─> Stage 05: Generate Newsletter ⬅️ NEW
```

### Stage 05 in Orchestrator

The orchestrator:
1. Checks if `stage05.enabled` (default: true)
2. Sets environment variables from newsletter config
3. Builds Stage 05 command
4. Tracks execution in `pipeline_runs`
5. Finds output file
6. Reports in execution summary

### Disabling Stage 05

```yaml
# In newsletters.yml
stage05:
  enabled: false  # Skip newsletter generation
```

## 📚 Examples

### Example 1: Basic Markdown Newsletter

**Config:**
```yaml
stage05:
  enabled: true
  output_format: "markdown"
  template: "default"
  top_with_content: 10
```

**Output:**
```markdown
# Tech Daily Digest

> Your daily dose of technology news

**Fecha:** 2025-11-13

---

Hoy el panorama tecnológico está dominado por tres grandes temas...

## Inteligencia Artificial: La nueva regulación europea

La Unión Europea ha dado un paso decisivo... Según [Financial Times](https://...),
el nuevo marco regulatorio... El artículo de [BBC](https://...) añade detalles...

[... more narrative prose ...]
```

### Example 2: HTML Executive Briefing

**Config:**
```yaml
stage05:
  enabled: true
  output_format: "html"
  template: "concise"
  top_with_content: 5
```

**Output:** Styled HTML with:
- Professional header
- Concise paragraphs
- Hyperlinked sources
- Mobile-responsive design
- Footer with metadata

### Example 3: Tech-Focused with GPT-4o

**Config:**
```yaml
stage05:
  enabled: true
  output_format: "both"
  template: "tech_focus"
  top_with_content: 15
  model_writer: "gpt-4o"  # Higher quality
  max_content_tokens: 1500  # More context
```

**Result:**
- Deeper technical analysis
- More nuanced insights
- Better narrative flow
- Higher cost (~$0.05 per newsletter)

## 🔍 Troubleshooting

### Issue: Newsletter quality is poor

**Possible causes:**
- Using gpt-4o-mini (good but not perfect)
- Too few articles with full content
- Content truncated too aggressively

**Solutions:**
- Upgrade to gpt-4o: `model_writer: "gpt-4o"`
- Increase `top_with_content`
- Increase `max_content_tokens`
- Try different template

### Issue: Generation is slow

**Possible causes:**
- Large context (many articles, long content)
- Using gpt-4o (slower than mini)

**Solutions:**
- Reduce `top_with_content`
- Reduce `max_content_tokens`
- Use gpt-4o-mini
- Check OpenAI API status

### Issue: Newsletter is too generic

**Possible causes:**
- Default template lacks personality
- Insufficient context

**Solutions:**
- Create custom template with specific personality
- Increase `max_content_tokens`
- Provide more articles with full content

## 📊 Metrics & Monitoring

### Key Metrics

Track these metrics for Stage 05:

| Metric | Location | What to Monitor |
|--------|----------|----------------|
| Execution time | `pipeline_runs.completed_at - started_at` | Should be < 60s |
| Token usage | `logs/token_usage.csv` | Cost per newsletter |
| Success rate | `pipeline_runs.status` | % completed |
| Output size | File size in bytes | Newsletter length |
| Articles with content | Log output | Coverage ratio |

### Dashboard Query Examples

```sql
-- Average Stage 05 execution time
SELECT AVG(
  (julianday(completed_at) - julianday(started_at)) * 86400
) as avg_seconds
FROM pipeline_runs
WHERE stage = 5 AND status = 'completed';

-- Success rate by newsletter
SELECT
  newsletter_name,
  COUNT(*) as total_runs,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
  ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 1) as success_rate
FROM pipeline_runs
WHERE stage = 5
GROUP BY newsletter_name;

-- Recent failures
SELECT newsletter_name, run_date, error_message, started_at
FROM pipeline_runs
WHERE stage = 5 AND status = 'failed'
ORDER BY started_at DESC
LIMIT 10;
```

## 🚀 Next Steps

### Planned Enhancements

- [ ] **Multi-language support** - Generate newsletters in multiple languages
- [ ] **Personalization** - User-specific newsletter customization
- [ ] **A/B testing** - Compare different templates/models
- [ ] **Email integration** - Direct sending via SMTP/SendGrid
- [ ] **Telegram bot** - Auto-posting to Telegram channels
- [ ] **Analytics** - Track open rates, click-throughs
- [ ] **Caching** - Cache LLM responses for similar content
- [ ] **Streaming** - Real-time newsletter generation
- [ ] **Voice narration** - Text-to-speech for podcast-style delivery

### Community Templates

Submit your custom templates via PR:
1. Create template in `templates/prompts/`
2. Test with multiple newsletters
3. Document use case and tone
4. Submit PR with examples

---

**Documentation Version:** 1.0
**Last Updated:** 2025-11-13
**Status:** ✅ Complete
