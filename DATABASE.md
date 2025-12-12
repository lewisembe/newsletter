# Estructura de la Base de Datos (LEGACY SQLite)

> Documento histórico basado en SQLite (`data/news.db`). La base activa ahora es PostgreSQL (ver `DB_SCHEMA_OVERVIEW.md` y `docker/schemas/schema.sql`). Mantener este archivo solo como referencia del esquema anterior.

## 📊 Visión General

El pipeline utiliza SQLite como almacén centralizado de datos, eliminando la necesidad de archivos JSON intermedios. Todas las operaciones (extracción, clasificación, ranking, generación) escriben y leen directamente de la base de datos.

**Características:**
- **Atomicidad:** Transacciones ACID garantizan consistencia
- **Trazabilidad:** Historia completa de ejecuciones
- **Performance:** Índices optimizados para queries frecuentes
- **Portabilidad:** Archivo único fácil de respaldar

---

## 🗂️ Tablas

### 1. `urls` - Contenido de Noticias

**Propósito:** Almacena URLs extraídas, titulares, clasificación y contenido completo.

| Columna | Tipo | NULL | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | INTEGER | NO | AUTOINCREMENT | ID único del artículo |
| `url` | TEXT | NO | - | URL del artículo (UNIQUE) |
| `title` | TEXT | YES | NULL | Titular extraído en Stage 01 |
| `source` | TEXT | YES | NULL | URL del medio (ej: `www.elpais.com`) |
| `content_type` | TEXT | YES | NULL | `contenido` \| `no_contenido` |
| `content_subtype` | TEXT | YES | NULL | `temporal` \| `atemporal` |
| `categoria_tematica` | TEXT | YES | NULL | Categoría asignada en Stage 02 |
| `extracted_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | Primera extracción (Stage 01) |
| `last_extracted_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | Última vez vista en Stage 01 |
| `categorized_at` | TIMESTAMP | YES | NULL | Timestamp de Stage 02 |
| `full_content` | TEXT | YES | NULL | Contenido completo (Stage 04) |
| `extraction_status` | TEXT | YES | `pending` | `pending` \| `success` \| `failed` |
| `extraction_error` | TEXT | YES | NULL | Mensaje de error si falló Stage 04 |
| `word_count` | INTEGER | YES | NULL | Cantidad de palabras del contenido |
| `content_extraction_method` | TEXT | YES | NULL | `xpath_cache` \| `newspaper` \| `readability` \| `llm_xpath` \| `archive` |
| `archive_url` | TEXT | YES | NULL | URL de archive.today si se usó |
| `relevance_level` | INTEGER | YES | NULL | **v3.1:** Nivel de relevancia 1-5 (Stage 03) |
| `scored_at` | TIMESTAMP | YES | NULL | **v3.1:** Timestamp de scoring |
| `scored_by_method` | TEXT | YES | NULL | **v3.1:** `level_scoring` \| `dual_subset` |

**Constraints:**
- `UNIQUE(url)` - No duplicados
- `CHECK(content_type IN ('contenido', 'no_contenido'))` - Valores válidos
- `CHECK(extraction_status IN ('pending', 'success', 'failed'))` - Estados válidos

**Índices:**
```sql
CREATE INDEX idx_urls_source ON urls(source);
CREATE INDEX idx_urls_categoria ON urls(categoria_tematica);
CREATE INDEX idx_urls_extracted_at ON urls(extracted_at);
CREATE INDEX idx_urls_extraction_status ON urls(extraction_status);
```

**Ejemplo de Registro:**
```json
{
  "id": 123,
  "url": "https://www.elpais.com/economia/2025-11-19/inflacion-eeuu.html",
  "title": "La inflación en EE.UU. se modera al 2.3% en octubre",
  "source": "www.elpais.com",
  "content_type": "contenido",
  "content_subtype": "temporal",
  "categoria_tematica": "economia",
  "extracted_at": "2025-11-19 10:30:00",
  "last_extracted_at": "2025-11-19 10:30:00",
  "categorized_at": "2025-11-19 10:35:00",
  "full_content": "El Departamento de Comercio...",
  "extraction_status": "success",
  "extraction_error": null,
  "word_count": 850,
  "content_extraction_method": "xpath_cache",
  "archive_url": null
}
```

---

### 2. `ranking_runs` - Historial de Rankings

**Propósito:** Registra cada ejecución de Stage 03 (ranker) con metadatos.

| Columna | Tipo | NULL | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | INTEGER | NO | AUTOINCREMENT | ID único del ranking |
| `newsletter_name` | TEXT | NO | - | Nombre de la newsletter |
| `run_date` | TEXT | NO | - | Fecha YYYY-MM-DD |
| `ranker_method` | TEXT | NO | - | `level_scoring` \| `dual_subset` |
| `categories_filter` | TEXT | YES | NULL | Categorías JSON (ej: `["economia", "politica"]`) |
| `articles_count` | INTEGER | NO | - | Número de artículos rankeados |
| `execution_time_seconds` | REAL | YES | NULL | Duración del ranking en segundos |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | Timestamp de ejecución |

**Constraints:**
- `UNIQUE(newsletter_name, run_date)` - Un ranking por newsletter/día
- `CHECK(ranker_method IN ('level_scoring', 'dual_subset'))` - Métodos válidos

**Índices:**
```sql
CREATE UNIQUE INDEX idx_ranking_runs_unique ON ranking_runs(newsletter_name, run_date);
CREATE INDEX idx_ranking_runs_created ON ranking_runs(created_at);
```

**Ejemplo de Registro:**
```json
{
  "id": 42,
  "newsletter_name": "noticias_diarias",
  "run_date": "2025-11-19",
  "ranker_method": "level_scoring",
  "categories_filter": "[\"economia\", \"politica\", \"geopolitica\"]",
  "articles_count": 20,
  "execution_time_seconds": 15.8,
  "created_at": "2025-11-19 10:40:00"
}
```

---

### 3. `ranked_urls` - URLs Rankeadas (v3.1 Minimalista)

**Propósito:** Almacena los artículos seleccionados por el ranker **solo con su posición ordinal**.

| Columna | Tipo | NULL | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | INTEGER | NO | AUTOINCREMENT | ID único del registro |
| `ranking_run_id` | INTEGER | NO | - | FK → `ranking_runs.id` |
| `url_id` | INTEGER | NO | - | FK → `urls.id` |
| `rank` | INTEGER | NO | - | Posición en el ranking (1-N) |

**Nota v3.1:** Las columnas `score` y `level` fueron eliminadas. El `relevance_level` está ahora en la tabla `urls` (fuente única de verdad).

**Constraints:**
- `FOREIGN KEY(ranking_run_id) REFERENCES ranking_runs(id)` - Relación con ranking
- `FOREIGN KEY(url_id) REFERENCES urls(id)` - Relación con artículo

**Índices:**
```sql
CREATE INDEX idx_ranked_urls_ranking ON ranked_urls(ranking_run_id, rank);
CREATE INDEX idx_ranked_urls_url ON ranked_urls(url_id, ranking_run_id);
```

**Ejemplo de Registros:**
```json
[
  {
    "id": 501,
    "ranking_run_id": 42,
    "url_id": 123,
    "rank": 1
  },
  {
    "id": 502,
    "ranking_run_id": 42,
    "url_id": 128,
    "rank": 2
  }
]
```

**Para obtener relevance_level de un ranking:**
```sql
SELECT ru.rank, u.relevance_level, u.title
FROM ranked_urls ru
JOIN urls u ON ru.url_id = u.id
WHERE ru.ranking_run_id = 42
ORDER BY ru.rank;
```

---

### 4. `debug_reports` - Informes de Ejecución

**Propósito:** Almacena métricas completas del pipeline (timing, tokens, errores).

| Columna | Tipo | NULL | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | INTEGER | NO | AUTOINCREMENT | ID único del report |
| `newsletter_name` | TEXT | NO | - | Nombre de la newsletter |
| `run_date` | TEXT | NO | - | Fecha YYYY-MM-DD |
| `report_data` | TEXT | NO | - | JSON con métricas completas |
| `total_duration_seconds` | REAL | YES | NULL | Duración total del pipeline |
| `total_tokens_used` | INTEGER | YES | NULL | Tokens LLM consumidos |
| `created_at` | TIMESTAMP | YES | CURRENT_TIMESTAMP | Timestamp del report |

**Constraints:**
- `UNIQUE(newsletter_name, run_date)` - Un report por newsletter/día

**Índices:**
```sql
CREATE UNIQUE INDEX idx_debug_reports_unique ON debug_reports(newsletter_name, run_date);
CREATE INDEX idx_debug_reports_created ON debug_reports(created_at);
```

**Estructura `report_data` JSON:**
```json
{
  "stages": {
    "stage_01": {
      "duration": 120.5,
      "urls_scraped": 250,
      "urls_valid": 180,
      "sources_processed": 15
    },
    "stage_02": {
      "duration": 30.2,
      "urls_classified": 180,
      "tokens": 1500,
      "categories": {
        "economia": 80,
        "politica": 50,
        "geopolitica": 30,
        "tecnologia": 20
      }
    },
    "stage_03": {
      "duration": 15.8,
      "urls_ranked": 20,
      "tokens": 800,
      "ranker_method": "level_scoring"
    },
    "stage_04": {
      "duration": 90.3,
      "urls_extracted": 20,
      "success": 18,
      "failed": 2,
      "methods": {
        "xpath_cache": 15,
        "newspaper": 2,
        "readability": 1,
        "archive": 2
      },
      "failed_urls": [
        "https://paywalled-site.com/article",
        "https://404-error.com/missing"
      ]
    },
    "stage_05": {
      "duration": 25.1,
      "newsletter_generated": true,
      "tokens": 500,
      "output_format": "markdown",
      "template": "default"
    }
  },
  "summary": {
    "total_duration": 281.9,
    "total_tokens": 2800,
    "total_urls_processed": 20,
    "successful_extractions": 18,
    "failed_extractions": 2,
    "output_files": [
      "data/newsletters/newsletter_noticias_diarias_2025-11-19_002119_economia-geopolitica-politica_default.md"
    ]
  }
}
```

**Ejemplo de Registro:**
```json
{
  "id": 15,
  "newsletter_name": "noticias_diarias",
  "run_date": "2025-11-19",
  "report_data": "{...}",  // JSON completo arriba
  "total_duration_seconds": 281.9,
  "total_tokens_used": 2800,
  "created_at": "2025-11-19 11:00:00"
}
```

---

### 5. `newsletters` - Newsletters Generadas (v3.1 NUEVA)

**Propósito:** Almacena newsletters completas con metadata y contenido.

| Columna | Tipo | NULL | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | INTEGER | NO | AUTOINCREMENT | ID único de la newsletter |
| `newsletter_name` | TEXT | NO | - | Nombre de la newsletter |
| `run_date` | TEXT | NO | - | Fecha YYYY-MM-DD |
| `template_name` | TEXT | NO | - | Template usado (`default`, `chief_economist`, etc.) |
| `output_format` | TEXT | NO | - | Formato (`markdown`, `html`, `both`) |
| `categories` | TEXT | YES | NULL | Categorías JSON (ej: `["economia", "politica"]`) |
| `content_markdown` | TEXT | NO | - | **Newsletter completo en Markdown** |
| `content_html` | TEXT | YES | NULL | Newsletter en HTML (opcional) |
| `articles_count` | INTEGER | NO | - | Número total de artículos |
| `articles_with_content` | INTEGER | NO | - | Artículos con contenido completo |
| `ranking_run_id` | INTEGER | YES | NULL | FK → `ranking_runs.id` |
| `generation_method` | TEXT | YES | `4-step` | Método de generación |
| `model_summarizer` | TEXT | YES | `gpt-4o-mini` | Modelo de resúmenes |
| `model_writer` | TEXT | YES | `gpt-4o` | Modelo de escritura |
| `total_tokens_used` | INTEGER | YES | NULL | Tokens LLM consumidos |
| `generation_duration_seconds` | REAL | YES | NULL | Duración de generación |
| `output_file_md` | TEXT | YES | NULL | Path al archivo .md |
| `output_file_html` | TEXT | YES | NULL | Path al archivo .html |
| `context_report_file` | TEXT | YES | NULL | Path al context_report.json |
| `generated_at` | TIMESTAMP | NO | CURRENT_TIMESTAMP | Timestamp de generación |

**Constraints:**
- `UNIQUE(newsletter_name, run_date)` - Una newsletter por nombre/día
- `FOREIGN KEY(ranking_run_id) REFERENCES ranking_runs(id) ON DELETE SET NULL`

**Índices:**
```sql
CREATE INDEX idx_newsletters_name ON newsletters(newsletter_name);
CREATE INDEX idx_newsletters_date ON newsletters(run_date);
CREATE INDEX idx_newsletters_ranking ON newsletters(ranking_run_id);
CREATE INDEX idx_newsletters_generated_at ON newsletters(generated_at);
```

**Ejemplo de Registro:**
```json
{
  "id": 15,
  "newsletter_name": "noticias_diarias",
  "run_date": "2025-11-20",
  "template_name": "default",
  "output_format": "markdown",
  "categories": "[\"economia\", \"politica\", \"geopolitica\"]",
  "content_markdown": "# Noticias Diarias del 20 de Noviembre...",
  "content_html": null,
  "articles_count": 20,
  "articles_with_content": 18,
  "ranking_run_id": 42,
  "generation_method": "4-step",
  "model_summarizer": "gpt-4o-mini",
  "model_writer": "gpt-4o",
  "total_tokens_used": 2800,
  "generation_duration_seconds": 25.1,
  "output_file_md": "data/newsletters/newsletter_noticias_diarias_2025-11-20.md",
  "output_file_html": null,
  "context_report_file": "data/newsletters/context_report_noticias_diarias_2025-11-20.json",
  "generated_at": "2025-11-20 12:00:00"
}
```

---

### 6. `pipeline_runs` - Tracking del Orchestrator

**Propósito:** Rastrea cada ejecución del orchestrator por stage.

| Columna | Tipo | NULL | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | INTEGER | NO | AUTOINCREMENT | ID único de la ejecución |
| `newsletter_name` | TEXT | NO | - | Nombre de la newsletter |
| `run_date` | TEXT | NO | - | Fecha YYYY-MM-DD |
| `stage` | INTEGER | NO | - | Stage ejecutado (1-5) |
| `status` | TEXT | NO | `pending` | `pending` \| `running` \| `completed` \| `failed` |
| `output_file` | TEXT | YES | NULL | Path al archivo generado |
| `error_message` | TEXT | YES | NULL | Mensaje de error si falló |
| `started_at` | TIMESTAMP | YES | NULL | Inicio de ejecución |
| `completed_at` | TIMESTAMP | YES | NULL | Fin de ejecución |

**Constraints:**
- `CHECK(stage IN (1, 2, 3, 4, 5))` - Stages válidos
- `CHECK(status IN ('pending', 'running', 'completed', 'failed'))` - Estados válidos

**Índices:**
```sql
CREATE INDEX idx_pipeline_runs_newsletter ON pipeline_runs(newsletter_name, run_date);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
```

**Ejemplo de Registros:**
```json
[
  {
    "id": 201,
    "newsletter_name": "noticias_diarias",
    "run_date": "2025-11-19",
    "stage": 1,
    "status": "completed",
    "output_file": null,
    "error_message": null,
    "started_at": "2025-11-19 10:30:00",
    "completed_at": "2025-11-19 10:32:30"
  },
  {
    "id": 205,
    "newsletter_name": "noticias_diarias",
    "run_date": "2025-11-19",
    "stage": 5,
    "status": "completed",
    "output_file": "data/newsletters/newsletter_noticias_diarias_2025-11-19_002119.md",
    "error_message": null,
    "started_at": "2025-11-19 10:59:30",
    "completed_at": "2025-11-19 11:00:00"
  }
]
```

---

## 🔍 Queries Útiles

### Ver artículos rankeados de una newsletter (v3.1)

```sql
SELECT
    ru.rank,
    u.relevance_level,
    u.title,
    u.source,
    u.categoria_tematica,
    u.word_count,
    u.content_extraction_method,
    u.scored_at
FROM ranked_urls ru
JOIN urls u ON ru.url_id = u.id
JOIN ranking_runs rr ON ru.ranking_run_id = rr.id
WHERE rr.newsletter_name = 'noticias_diarias'
  AND rr.run_date = '2025-11-20'
ORDER BY ru.rank;
```

### Ver últimos debug reports

```sql
SELECT
    newsletter_name,
    run_date,
    total_duration_seconds,
    total_tokens_used,
    json_extract(report_data, '$.summary.successful_extractions') as extractions,
    created_at
FROM debug_reports
ORDER BY created_at DESC
LIMIT 10;
```

### Ver tasa de éxito de extracción por método

```sql
SELECT
    content_extraction_method,
    COUNT(*) as total,
    SUM(CASE WHEN extraction_status = 'success' THEN 1 ELSE 0 END) as success,
    ROUND(100.0 * SUM(CASE WHEN extraction_status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM urls
WHERE content_extraction_method IS NOT NULL
GROUP BY content_extraction_method
ORDER BY success_rate DESC;
```

### Ver artículos por categoría (últimas 24h)

```sql
SELECT
    categoria_tematica,
    COUNT(*) as total,
    AVG(word_count) as avg_words
FROM urls
WHERE categorized_at >= datetime('now', '-1 day')
  AND categoria_tematica IS NOT NULL
GROUP BY categoria_tematica
ORDER BY total DESC;
```

### Ver pipeline runs por estado

```sql
SELECT
    newsletter_name,
    run_date,
    stage,
    status,
    ROUND((julianday(completed_at) - julianday(started_at)) * 86400, 2) as duration_seconds,
    error_message
FROM pipeline_runs
WHERE run_date = '2025-11-19'
ORDER BY newsletter_name, stage;
```

### Ver URLs con errores de extracción

```sql
SELECT
    url,
    title,
    source,
    extraction_error,
    last_extracted_at
FROM urls
WHERE extraction_status = 'failed'
  AND last_extracted_at >= date('now', '-7 days')
ORDER BY last_extracted_at DESC
LIMIT 20;
```

---

## 📊 Diagramas de Relaciones

### Flujo de Datos por Stage

```
Stage 01: Extract URLs
  ↓
  INSERT INTO urls (url, title, source, extracted_at)

Stage 02: Filter & Classify
  ↓
  UPDATE urls SET categoria_tematica, categorized_at

Stage 03: Ranker
  ↓
  INSERT INTO ranking_runs (newsletter_name, run_date, ...)
  INSERT INTO ranked_urls (ranking_run_id, url_id, rank, level, score)

Stage 04: Extract Content
  ↓
  UPDATE urls SET full_content, extraction_status, word_count, content_extraction_method

Stage 05: Generate Newsletter
  ↓
  SELECT FROM ranked_urls + urls (JOIN)
  INSERT INTO debug_reports (report_data, total_duration, ...)
```

### Relaciones Entre Tablas

```
urls (1) ←─── (N) ranked_urls (N) ───→ (1) ranking_runs
                                              ↓
                                         newsletter_name
                                              ↓
                                      debug_reports (1:1)
                                              ↓
                                      pipeline_runs (1:N)
```

---

## 🛠️ Mantenimiento

### Vaciar base de datos (mantener estructura)

```sql
DELETE FROM ranked_urls;
DELETE FROM ranking_runs;
DELETE FROM debug_reports;
DELETE FROM pipeline_runs;
DELETE FROM urls;
VACUUM;
```

### Limpiar datos antiguos (>30 días)

```sql
-- Eliminar rankings antiguos
DELETE FROM ranked_urls
WHERE ranking_run_id IN (
    SELECT id FROM ranking_runs
    WHERE run_date < date('now', '-30 days')
);

DELETE FROM ranking_runs
WHERE run_date < date('now', '-30 days');

-- Eliminar URLs antiguas no rankeadas
DELETE FROM urls
WHERE extracted_at < date('now', '-30 days')
  AND id NOT IN (SELECT url_id FROM ranked_urls);

VACUUM;
```

### Crear backup

```bash
# Backup completo
sqlite3 data/news.db ".backup data/news_backup_$(date +%Y%m%d).db"

# Export SQL
sqlite3 data/news.db .dump > data/news_backup_$(date +%Y%m%d).sql

# Export CSV (tabla específica)
sqlite3 data/news.db -header -csv "SELECT * FROM urls;" > urls_export.csv
```

### Verificar integridad

```bash
sqlite3 data/news.db "PRAGMA integrity_check;"
sqlite3 data/news.db "PRAGMA foreign_key_check;"
```

---

## 📈 Estadísticas de Uso

### Tamaño de la base de datos

```sql
-- Tamaño por tabla
SELECT
    name,
    SUM(pgsize) / 1024.0 / 1024.0 as size_mb
FROM dbstat
GROUP BY name
ORDER BY size_mb DESC;
```

### Registros totales

```sql
SELECT
    'urls' as table_name, COUNT(*) as total FROM urls
UNION ALL
SELECT 'ranking_runs', COUNT(*) FROM ranking_runs
UNION ALL
SELECT 'ranked_urls', COUNT(*) FROM ranked_urls
UNION ALL
SELECT 'debug_reports', COUNT(*) FROM debug_reports
UNION ALL
SELECT 'pipeline_runs', COUNT(*) FROM pipeline_runs;
```

---

## 🔧 Migración de Esquema

Si necesitas modificar la estructura de la base de datos:

### Ejemplo: Agregar nueva columna

```sql
-- Agregar columna
ALTER TABLE urls ADD COLUMN sentiment_score REAL;

-- Crear índice si es necesario
CREATE INDEX idx_urls_sentiment ON urls(sentiment_score);
```

### Ejemplo: Crear nueva tabla

```sql
CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    newsletter_name TEXT NOT NULL,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

CREATE INDEX idx_subscriptions_email ON newsletter_subscriptions(email);
CREATE INDEX idx_subscriptions_newsletter ON newsletter_subscriptions(newsletter_name);
```

---

## ✅ Checklist de Integridad

Antes de ejecutar el pipeline, verifica:

- [ ] Base de datos existe: `ls -lh data/news.db`
- [ ] Tablas creadas: `sqlite3 data/news.db ".tables"`
- [ ] Índices activos: `sqlite3 data/news.db ".indexes urls"`
- [ ] Claves foráneas habilitadas: `sqlite3 data/news.db "PRAGMA foreign_keys;"`
- [ ] Sin corrupciones: `sqlite3 data/news.db "PRAGMA integrity_check;"`

---

**Nota:** Esta documentación refleja la versión v3.0 DB-Centric del pipeline. Para detalles de implementación, consulta `CLAUDE.md` y los README específicos de cada stage en `/stages/`.
