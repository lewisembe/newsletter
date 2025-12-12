# Stage 04: Extract Content

**Estado:** ✅ Implementado con Smart Substitution | **Última actualización:** 2025-11-16

## 🎯 Objetivo

Extraer contenido completo de artículos rankeados usando múltiples métodos de extracción con fallback inteligente, detección de paywalls y **sustitución automática** para garantizar N artículos con contenido.

## 🆕 Nueva Funcionalidad: Smart Substitution

**Problema anterior:** Si un artículo featured fallaba extracción → se quedaba sin contenido
**Solución nueva:** Sustituir automáticamente usando pool de artículos no-featured

### Prioridad de Sustitución (Dual Subset Format)

El sistema detecta automáticamente el formato del JSON de entrada y aplica la estrategia correcta:

#### **Para Dual Subset (formato actual - post clustering removal):**

1. **Featured article falla** → Intentar con artículos non-featured (en orden de rank)
2. **Mantener headlines originales** → El ranking visible (top 20) no cambia
3. **Sustituir solo contenido** → Los titulares se mantienen, pero el contenido se extrae del pool de backups
4. **Repetir hasta conseguir N artículos** o agotar candidatos

**Ventajas:**
- ✅ Los non-featured (ranks 11-20) sirven como pool de sustitución
- ✅ No requiere clustering
- ✅ Headlines siempre consistentes (top 20)
- ✅ Tracking completo de sustituciones

#### **Para Legacy/Clustering Format (retrocompatibilidad):**

1. **Artículo primary falla** → Intentar con sus `related_articles` específicos (mismo cluster)
2. **Todos los related fallan** → Sustituir con siguiente artículo primary de la lista
3. **Repetir hasta conseguir N artículos** o agotar candidatos

### Ejemplo de Ejecución (Dual Subset)

```
Target: 10 artículos con contenido
Input: 19 URLs (10 featured, 9 non-featured)

Candidate pool: [Featured #1-10, Non-Featured #11-19] (19 candidatos totales)

Featured #1 (rank 1) → ✓ Éxito
Featured #2 (rank 2) → ✗ Fallo (paywall NYT)
Featured #3 (rank 3) → ✗ Fallo (paywall)
Featured #4 (rank 4) → ✓ Éxito
Featured #5-10 → ✓ Todos exitosos (6 artículos)

✓ 8 featured exitosos, faltan 2 para llegar a 10
→ Continuar con pool de sustitución (non-featured):

Non-Featured #11 → ✓ Éxito (SUSTITUCIÓN para slot #2)
Non-Featured #12 → ✓ Éxito (SUSTITUCIÓN para slot #3)

Resultado: 10 artículos con contenido (2 sustituciones)
Headlines mostradas: Ranks 1-20 (sin cambios)
Contenido extraído: Featured #1,4-10 + Non-Featured #11,12
```

### Metadata de Sustitución

Cuando ocurre una sustitución, se añade metadata completa:

```json
{
  "rank": 2,
  "id": 4002,
  "title": "Non-featured article title",
  "was_substitution": true,
  "substitution_source_rank": 11,
  "original_target_rank": 2,
  "substituted_for_id": 3638,
  "candidate_type": "substitute"
}
```

**Campos:**
- `was_substitution`: true si el contenido proviene de un artículo diferente al headline
- `substitution_source_rank`: Rank original del artículo que proporcionó el contenido (ej: 11)
- `original_target_rank`: Rank del slot que necesitaba contenido (ej: 2)
- `substituted_for_id`: ID del artículo featured que falló extracción
- `candidate_type`: Tipo de candidato (`featured`, `substitute`, `primary`, `related`)

## 🏗️ Arquitectura

```
Input: ranked_YYYY-MM-DD_HHMMSS_*.json (del Stage 03)
  ↓
1. Construir candidate pool con prioridad:
   - Primary #1, Related #1.1, Related #1.2, ...
   - Primary #2, Related #2.1, Related #2.2, ...
   - Primary #3, ...
  ↓
2. Para cada candidato (hasta conseguir N con contenido):
   a. Fetch directo
   b. Detección de paywall (LLM)
   c. Archive.today si paywall detectado
   d. Extracción cascada:
      - XPath Cache (si existe) → GRATIS
      - newspaper3k → GRATIS
      - readability → GRATIS
      - LLM XPath Discovery → PAGO (~$0.0003)
   e. Limpieza de contenido
   f. Guardar en BD
   g. Si éxito → Siguiente target rank
   h. Si fallo → Siguiente candidato (sustitución)
  ↓
Output:
  - BD actualizada con full_content
  - JSON con execution_report detallado
```

## 🚀 Uso

### Básico (con sustitución automática)
```bash
# Extraer de un ranking específico
# Por defecto: intenta conseguir contenido para TODOS los artículos primarios
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_2025-11-13_143052_level_top25_all_cluster2x.json
```

### Target N artículos con contenido
```bash
# Intentar conseguir exactamente 10 artículos con contenido
# Si alguno falla → sustituye automáticamente con related/siguientes
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_X.json \
    --max-articles 10
```

### Deshabilitar sustitución
```bash
# Solo intentar artículos primarios (sin sustituciones)
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_X.json \
    --disable-substitution
```

### Opciones Avanzadas
```bash
# Re-extraer aunque ya exista contenido
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_X.json \
    --force

# Skip paywall check (útil para testing)
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_X.json \
    --skip-paywall-check

# Modo verbose
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_X.json \
    --verbose

# Combinaciones
venv/bin/python stages/04_extract_content.py \
    --input data/processed/ranked_X.json \
    --max-articles 15 \
    --force \
    --verbose
```

## 📊 Métodos de Extracción

### 1. XPath Cache (Prioridad 1)
- **Cómo funciona:** Reutiliza selectores CSS/XPath descubiertos previamente
- **Cache:** `config/xpath_cache.yml`
- **Ventaja:** Instantáneo, gratis, ~95% éxito después de poblado
- **Costo:** $0

**Ejemplo de cache:**
```yaml
www.elconfidencial.com:
  content_selector: "article.news-body p"
  selector_type: "css"
  confidence: 95
  success_rate: 0.96
```

### 2. newspaper3k (Fallback 1)
- **Cómo funciona:** Heurísticas automáticas para detectar contenido
- **Detecta:** `<article>`, `<main>`, `.post-content`, densidad de texto
- **Éxito:** ~70-80%
- **Costo:** $0

### 3. readability-lxml (Fallback 2)
- **Cómo funciona:** Algoritmo de Mozilla (Firefox Reader Mode)
- **Calcula:** Scores por nodo basado en texto/HTML ratio
- **Éxito:** ~60-70%
- **Costo:** $0

### 4. LLM XPath Discovery (Fallback 3)
- **Cómo funciona:** LLM analiza HTML y descubre selector óptimo
- **Prompt:** Primeros 8000 chars del HTML
- **Ventaja:** Inteligente, adapta a cualquier estructura
- **Cache:** Guarda selector descubierto para próximas veces
- **Costo:** ~$0.0003 por artículo (~600 tokens)

## 🛡️ Detección de Paywall

### Estrategia: LLM con optimización de tokens
```python
# En lugar de pasar HTML completo (8000 chars = ~2000 tokens):
inicio = html[:500]    # Primeros 500 chars
final = html[-1000:]   # Últimos 1000 chars

# Pasar solo inicio + final (~600 tokens)
# Ahorro: 70% tokens
```

**Señales de paywall:**
- "Suscríbete para continuar"
- "Este contenido es exclusivo"
- "Register to read"
- Contenido cortado abruptamente

**Costo:** ~$0.00009 por validación (600 tokens in + 5 out)

### Fallback: archive.today
Si paywall detectado:
1. Fetch con Selenium (anti-bot measures)
2. Wait 8 segundos (JavaScript execution)
3. Detectar CAPTCHA (<5000 bytes)
4. Retry con backoff (max 2 intentos)

**Éxito:** ~90% con Selenium

## 🔧 Configuración (.env)

```env
# Stage 04: Extract Content
STAGE04_TIMEOUT=30                      # HTTP timeout (segundos)
STAGE04_ARCHIVE_WAIT_TIME=15            # Selenium wait (segundos)
STAGE04_MAX_RETRIES=2                   # Reintentos para archive
STAGE04_MIN_WORD_COUNT=100              # Mínimo palabras válidas
STAGE04_MAX_WORD_COUNT=10000            # Máximo (trunca)

# Models
MODEL_PAYWALL_VALIDATOR=gpt-4o-mini    # Detección paywall
MODEL_XPATH_DISCOVERY=gpt-4o-mini      # Descubrimiento XPath

# Cache
XPATH_CACHE_PATH=config/xpath_cache.yml
```

## 📁 Estructura de Archivos

```
common/stage04_extraction/
├── __init__.py              # Exports públicos
├── xpath_cache.py           # Gestión de cache de selectores
├── paywall_validator.py     # Detección de paywalls con LLM
├── archive_fetcher.py       # Fetch desde archive.today
├── extractors.py            # Métodos de extracción (newspaper, readability, LLM)
└── content_cleaner.py       # Limpieza de boilerplate
```

## 💰 Costos

**Escenario: 25 artículos**

| Operación | Frecuencia | Costo Unitario | Total |
|-----------|------------|----------------|-------|
| Paywall validation (LLM) | 25x (siempre) | $0.00009 | $0.00225 |
| XPath Cache | 10x (40%) | $0 | $0 |
| newspaper3k | 8x (30%) | $0 | $0 |
| readability | 2x (10%) | $0 | $0 |
| LLM XPath Discovery | 5x (20%) | $0.0003 | $0.0015 |
| **TOTAL** | | | **~$0.004** |

**Después de 10 ejecuciones:** Cache poblado → $0.0025 por ejecución

## 🗄️ Base de Datos

**Columnas actualizadas:**
- `full_content` - Contenido extraído limpio
- `extraction_status` - `success`/`failed`/`pending`
- `extraction_error` - Mensaje de error
- `word_count` - Palabras extraídas
- `content_extraction_method` - Método usado
- `content_extracted_at` - Timestamp
- `archive_url` - URL de archive si se usó

## 📊 Salida

### 1. Logs
```
logs/YYYY-MM-DD/04_extract_content.log
```

### 2. JSON con Execution Report
```json
{
  "run_date": "2025-11-13",
  "generated_at": "2025-11-13T14:30:52Z",
  "input_file": "data/processed/ranked_2025-11-13_143052.json",
  "execution_report": {
    "target_articles_count": 25,
    "final_articles_with_content": 23,
    "total_attempts": 28,
    "successful_extractions": 23,
    "failed_extractions": 5,
    "substitutions_made": 3,
    "status": "partial_success_with_substitutions",
    "details": [
      {
        "target_rank": 1,
        "url_id": 123,
        "title": "Breaking news...",
        "candidate_type": "primary",
        "extraction_status": "success",
        "word_count": 847,
        "method": "xpath_cache"
      },
      {
        "target_rank": 5,
        "url_id": 456,
        "title": "Primary article...",
        "candidate_type": "primary",
        "extraction_status": "failed",
        "error": "Paywall cannot be bypassed"
      },
      {
        "target_rank": 5,
        "url_id": 457,
        "title": "Related article...",
        "candidate_type": "related",
        "parent_id": 456,
        "extraction_status": "success",
        "word_count": 623,
        "method": "newspaper",
        "substitution_reason": "Primary article extraction failed"
      }
    ]
  },
  "articles": [
    {
      "rank": 1,
      "id": 123,
      "url": "https://...",
      "title": "...",
      "source": "ft.com",
      "categoria_tematica": "economia",
      "word_count": 847,
      "extraction_method": "xpath_cache",
      "was_substitution": false,
      "original_rank": 1
    }
  ]
}
```

**Archivo:** `data/processed/content_YYYY-MM-DD_HHMMSS.json`

### 3. Resumen en logs
```
STAGE 04 SUMMARY
================================================================================
Total URLs processed: 28
  ✓ Successfully extracted: 23
  → Skipped (already extracted): 0
  ✗ Failed: 5
  📦 Used archive.today: 5

Extraction methods used:
  xpath_cache: 10
  newspaper: 8
  readability: 3
  llm_xpath: 2

Average word count: 847 words

SUBSTITUTION REPORT:
  Target articles: 25
  Final with content: 23
  Substitutions made: 3
  Status: partial_success_with_substitutions
================================================================================
```

### Interpretación de Status

| Status | Significado |
|--------|-------------|
| `success` | Alcanzó target sin sustituciones |
| `success_with_substitutions` | Alcanzó target con sustituciones |
| `partial_success` | No alcanzó target pero tiene artículos |
| `partial_success_with_substitutions` | No alcanzó target, usó sustituciones |
| `failed` | No consiguió ningún artículo |

## 🐛 Troubleshooting

### Error: "Direct fetch failed"
```bash
# Verificar conectividad
curl -I https://www.example.com

# Revisar timeout
STAGE04_TIMEOUT=60 venv/bin/python stages/04_extract_content.py ...
```

### Error: "All extraction methods failed"
```bash
# Probar con LLM más potente
MODEL_XPATH_DISCOVERY=gpt-4o venv/bin/python stages/04_extract_content.py ...

# Ver logs detallados
venv/bin/python stages/04_extract_content.py ... --verbose
```

### XPath Cache con baja tasa de éxito
```bash
# Limpiar entradas malas
venv/bin/python -c "
from common.stage04_extraction import cleanup_xpath_cache
cleanup_xpath_cache(min_success_rate=0.7)
"
```

### Archive.today bloqueado (CAPTCHA)
- Aumentar `STAGE04_ARCHIVE_WAIT_TIME=20`
- Reducir frecuencia de requests
- Considerar usar proxy/VPN

## 🔄 Próximos Pasos

- [ ] **Testing:** Unit tests para extractors
- [ ] **Optimización:** Parallel fetching con asyncio
- [ ] **Métricas:** Dashboard de success rates por dominio
- [ ] **Stage 05:** Usar `full_content` para generar newsletters

---

**Ver también:**
- `config/xpath_cache.yml` - Cache de selectores por dominio
- `common/stage04_extraction/` - Código fuente de utilities
- `CLAUDE.md` - Overview completo del proyecto
