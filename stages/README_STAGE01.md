# Stage 01: Extract URLs - Documentación Técnica

> **Estado:** ✅ COMPLETADO e implementado con optimizaciones
> **Última actualización:** 2025-11-10

## 📋 Índice

1. [Visión General](#visión-general)
2. [Arquitectura](#arquitectura)
3. [Flujo de Ejecución](#flujo-de-ejecución)
4. [Sistema de Clasificación Híbrido](#sistema-de-clasificación-híbrido)
5. [Deduplicación y Upsert Incremental](#deduplicación-y-upsert-incremental)
6. [Configuración](#configuración)
7. [Ejecución](#ejecución)
8. [Outputs y Formato](#outputs-y-formato)
9. [Optimizaciones de Costo](#optimizaciones-de-costo)
10. [Troubleshooting](#troubleshooting)
11. [Métricas y Logs](#métricas-y-logs)

---

## 🎯 Visión General

El **Stage 01** es la primera etapa del pipeline de noticias. Su objetivo es:

1. **Extraer** todas las URLs de artículos desde fuentes de noticias configuradas usando Selenium
2. **Clasificar** URLs en 2 niveles (sintáctico y semántico) usando un sistema híbrido regex + LLM
3. **Deduplicar** URLs contra base de datos existente con tracking temporal dual
4. **Persistir** resultados incrementalmente en un CSV consolidado único

### Características Principales

- ✅ **Sistema híbrido de clasificación:** 60-85% cobertura con regex (sin consumir tokens API)
- ✅ **Clasificación en 2 niveles:** Separación clara entre análisis sintáctico y semántico
- ✅ **Upsert incremental:** Guarda después de cada fuente (no batch al final)
- ✅ **Tracking dual de timestamps:** `extracted_at` (primera vez) + `last_extracted_at` (última vez vista)
- ✅ **Caché de URLs no-contenido:** Lookup O(1) para URLs conocidas sin contenido
- ✅ **Backups automáticos:** Preserva versiones anteriores antes de modificar
- ✅ **Token tracking detallado:** Monitoreo de uso y costos de API
- ✅ **Optimización de costos:** ~60-70% reducción en llamadas a LLM vs enfoque naive
- ✅ **Clusterización semántica incremental:** tras cada ingesta se ejecuta el módulo `poc_clustering` hacia un
  índice FAISS persistente, asignando/actualizando `cluster_id` sin borrar históricos y almacenando embeddings para
  detección de duplicados entre días (activable/desactivable con `ENABLE_NEWS_CLUSTERING`)

---

## 🏗️ Arquitectura

### Componentes Principales

```
stages/01_extract_urls.py (script principal)
│
├── common/stage01_extraction/
│   ├── selenium_utils.py          # WebDriver + scraping de URLs
│   └── url_classifier.py          # Clasificador híbrido (regex + LLM)
│
├── common/
│   ├── llm.py                     # Cliente OpenAI con token tracking
│   ├── dedup.py                   # Deduplicación y merge de URLs
│   ├── file_utils.py              # Utilidades de archivos y timestamps
│   └── structure_manager.py       # Gestión de directorios
│
└── config/
    ├── sources.yml                # Configuración de fuentes
    ├── content_categories.yml     # Taxonomía de contenido (nivel 1 y 2)
    ├── url_classification_rules.yml      # Reglas regex por fuente
    └── cached_no_content_urls.yml        # Caché de URLs sin contenido
```

### Tablas en `data/news.db`

- `urls`: tabla principal con cada URL extraída, su clasificación, timestamps y ahora la columna `cluster_id`
- `clusters`: resumen por cluster semántico con `id` (clave primaria), `run_date`, `article_count`, métricas de
  similitud incremental y el `centroid_url_id` que referencia a `urls.id`. `urls.cluster_id` apunta a esta tabla, por lo
  que en ejecuciones siguientes ya sabemos cuántas noticias cubren ese mismo evento.
- `url_embeddings`: caché binaria de los embeddings normalizados para cada URL `contenido`. Almacenar los vectores
  permite que el índice FAISS se reanude al iniciar Stage 01 sin re-embeder todo cada vez.

> Si tu base existe desde antes de esta versión, ejecuta una vez
> `python scripts/migrate_add_cluster_id.py --db-path data/news.db` para añadir columnas y tablas (`clusters`,
> `url_embeddings`) junto con los índices correspondientes.

### Clustering incremental (Stage 01.5)

- Implementado en `poc_clustering/src/persistent_clusterer.py`; usa `sentence-transformers` + `faiss-cpu`.
- El archivo `poc_clustering/config.yml` controla `similarity_threshold`, `adaptive_k`, `max_neighbors` y **el nuevo
  bloque `state.directory`**, que indica dónde persistir el índice FAISS (`poc_clustering/state` por defecto).
- Stage 01 sólo embebe las URLs nuevas (sin `cluster_id`), las compara contra el índice histórico y decide si van a un
  cluster existente o si crean uno nuevo. No se borra ningún `cluster_id` previo.
- Las métricas (`article_count`, similitud promedio y su media/m2 para thresholds adaptativos) se actualizan en la
  tabla `clusters`, lo que permite analizar la evolución de cada evento.

### Dependencias

```python
# Core
selenium>=4.0.0
openai>=1.0.0
pyyaml>=6.0
python-dotenv>=1.0.0

# Utilities
pandas>=2.0.0  # (opcional, para análisis)
```

### Flujo de Datos

```
┌─────────────────┐
│  sources.yml    │
│  (fuentes)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Selenium Driver │  ← Extrae TODAS las URLs de cada fuente
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│         Sistema de Clasificación Híbrido            │
│                                                      │
│  1. Caché URLs no-contenido (O(1) lookup)          │
│  2. Reglas regex por fuente (~60-85% cobertura)    │
│  3. Fallback a LLM (solo URLs sin coincidencia)    │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Nivel 1: Type  │  ← Sintáctico: contenido vs no_contenido
│ (regex + LLM)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Nivel 2: Subtype│  ← Semántico: noticia vs otros (OPCIONAL)
│   (solo LLM)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deduplicación  │  ← Merge con data/raw/urls.csv existente
│  Incremental    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Backup + Save   │  ← Guarda después de cada fuente
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ data/raw/       │
│   urls.csv      │  ← CSV consolidado único (separador TAB)
└─────────────────┘
```

---

## 🔄 Flujo de Ejecución

### 1. Inicialización

```python
# 01_extract_urls.py

# Cargar configuración
load_dotenv()  # Variables de entorno desde .env
sources = load_yaml("config/sources.yml")
content_categories = load_yaml("config/content_categories.yml")

# Inicializar componentes
llm_client = LLMClient(api_key=os.getenv("OPENAI_API_KEY"))
classifier = URLClassifier(
    llm_client=llm_client,
    rules_path="config/url_classification_rules.yml",
    cache_path="config/cached_no_content_urls.yml"
)
driver = init_selenium_driver(headless=True)
```

### 2. Extracción por Fuente

```python
for source in sources['sources']:
    if not source['enabled']:
        continue

    # Navegar con Selenium
    driver.get(source['url'])
    wait_for_page_load(driver)

    # Extraer URLs usando selectores CSS con deduplicación intra-página
    # NOTA: Si una URL aparece múltiples veces, se queda con el título más largo
    raw_urls = extract_links_with_deduplication(
        driver=driver,
        selectors=source['selectors']
    )

    # raw_urls es una lista de {'url': ..., 'title': ...}
    # Ya deduplicada a nivel de página

    # Aplicar límite de testing si está configurado
    if TEST_MAX_RAW_LINKS:
        raw_urls = raw_urls[:TEST_MAX_RAW_LINKS]
```

**Deduplicación Intra-Página:**

Cuando una misma URL aparece múltiples veces en una página (común en portales de noticias), el sistema:

1. **Detecta duplicados** por URL exacta
2. **Compara longitudes** de los títulos extraídos
3. **Conserva el título más largo** (asumiendo que es más descriptivo)
4. **Filtra títulos cortos** (mínimo configurable con `MIN_TITLE_LENGTH`, default: 10 caracteres)

**Ejemplo:**
```
Página contiene:
  - <a href="/noticia-123">Ver más</a>           (título: 8 chars)
  - <a href="/noticia-123">Crisis económica</a>  (título: 16 chars)
  - <a href="/noticia-123">Crisis económica en Europa afecta...</a>  (título: 45 chars)

Resultado:
  - URL: /noticia-123
  - Título: "Crisis económica en Europa afecta..." (el más largo)
```

Esta lógica evita:
- Títulos genéricos como "Leer más", "Ver artículo"
- Duplicados innecesarios que consumirían tokens de clasificación
- Pérdida de información contextual del titular

Ver implementación en `common/stage01_extraction/selenium_utils.py:135-230`

### 3. Clasificación Híbrida

```python
classified_urls = []

for item in raw_urls:
    url = item['url']

    # Nivel 1: content_type (sintáctico)
    result = classifier.classify_url_level1(
        url=url,
        source_id=source['id'],
        source_url=source['url']
    )

    # result contiene:
    # - content_type: 'contenido' | 'no_contenido'
    # - classification_method: 'cached_url' | 'regex_rule' | 'llm_api'
    # - rule_name: nombre de regla regex (o None)

    if result['content_type'] == 'no_contenido':
        continue  # Descartar

    # Nivel 2: content_subtype (semántico, OPCIONAL)
    if CLASSIFY_CONTENT_SUBTYPE:
        subtype = classifier.classify_url_level2(url, title)
        # subtype: 'noticia' | 'otros'
    else:
        subtype = None

    classified_urls.append({
        'url': url,
        'title': item['title'],
        'source': source['url'],
        'content_type': result['content_type'],
        'content_subtype': subtype,
        'classification_method': result['classification_method'],
        'rule_name': result['rule_name'],
        'extracted_at': datetime.now(timezone.utc).isoformat()
    })
```

### 4. Deduplicación Incremental

```python
# Cargar URLs existentes
existing_df = load_existing_urls("data/raw/urls.csv")

# Deduplicar y merge
merged_df = deduplicate_and_merge(
    new_urls=classified_urls,
    existing_df=existing_df,
    preserve_original_timestamp=True  # Mantener extracted_at original
)

# merged_df contiene:
# - URLs nuevas: extracted_at = last_extracted_at = NOW
# - URLs duplicadas: extracted_at = ORIGINAL, last_extracted_at = NOW
```

### 5. Persistencia Incremental

```python
# Backup automático antes de modificar
if urls.csv exists:
    backup_path = create_backup("data/raw/urls.csv")
    # Crea: data/raw/urls_backup_20251110_123045.csv

# Guardar CSV consolidado
save_csv(
    df=merged_df,
    path="data/raw/urls.csv",
    separator="\t",  # TAB separator
    encoding="utf-8"
)

# Actualizar reglas si está configurado
if UPDATE_RULES_ON_RUN:
    classifier.update_rules(
        urls=classified_urls,
        source_id=source['id']
    )
```

### 6. Logging y Métricas

```python
# Generar log estructurado
log_entry = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "stage": "01_extract_urls",
    "source": source['id'],
    "stats": {
        "raw_urls_extracted": len(raw_urls),
        "urls_classified_contenido": len([u for u in classified_urls if u['content_type'] == 'contenido']),
        "urls_classified_no_contenido": len(raw_urls) - len(classified_urls),
        "urls_new": count_new_urls,
        "urls_duplicate": count_duplicate_urls,
        "classification_methods": {
            "cached_url": count_cached,
            "regex_rule": count_regex,
            "llm_api": count_llm
        },
        "tokens_used": llm_client.get_token_count(),
        "cost_usd": llm_client.get_cost()
    },
    "duration_seconds": elapsed_time,
    "status": "success"
}

write_log("logs/2025-11-10/01_extract_urls.log", log_entry)
```

---

## 🧠 Sistema de Clasificación Híbrido

### Niveles de Clasificación

El sistema clasifica URLs en **2 niveles independientes**:

#### Nivel 1: `content_type` (Sintáctico)
- **Objetivo:** Determinar si la URL apunta a contenido editorial o elementos auxiliares
- **Valores:** `contenido` | `no_contenido`
- **Optimizable:** ✅ Sí (con reglas regex)
- **Método:** Híbrido (caché → regex → LLM)

**Ejemplos:**
```
contenido:      https://elpais.com/internacional/2025-11-10/...
no_contenido:   https://elpais.com/suscripciones/
no_contenido:   https://elpais.com/newsletters/
no_contenido:   https://elpais.com/archivo/
```

#### Nivel 2: `content_subtype` (Semántico)
- **Objetivo:** Distinguir noticias de otros contenidos editoriales
- **Valores:** `noticia` | `otros` | `NULL`
- **Optimizable:** ❌ No (requiere análisis semántico)
- **Método:** Solo LLM
- **Activación:** `CLASSIFY_CONTENT_SUBTYPE=true` (default: false)

**Ejemplos:**
```
noticia:   https://bbc.com/news/world-europe-12345678
otros:     https://bbc.com/culture/article/best-films-2025
otros:     https://economist.com/the-economist-explains/...
```

### Métodos de Clasificación

El sistema usa **4 métodos** en orden de prioridad, aplicando el primero que coincida:

| Método | Prioridad | Consume tokens | Velocidad | Cobertura típica | Descripción |
|--------|-----------|----------------|-----------|------------------|-------------|
| `cached_url` | 1 | ❌ No | Instantáneo (O(1)) | 10-20% | URLs conocidas sin contenido (set lookup) |
| `heuristic` | 2 | ❌ No | Muy rápido | 5-15% | Detecta collection pages (autor, sección) por patrones |
| `regex_rule` | 3 | ❌ No | Muy rápido | 40-60% | Patrones regex aprendidos por fuente |
| `llm_api` | 4 (fallback) | ✅ Sí | Lento (~500ms) | 10-40% | Llamada a OpenAI GPT-4o-mini |

**Ahorro estimado:** 60-85% de URLs clasificadas SIN llamar a LLM.

### Diagrama de Decisión de Clasificación

```
┌─────────────────────┐
│  URL a clasificar   │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────────────────┐
    │ ¿En caché no_contenido?  │ → SÍ → ⚡ no_contenido (cached_url)
    └──────────┬───────────────┘
               │ NO
               ▼
    ┌──────────────────────────┐
    │ ¿Heurística detecta      │
    │ collection page?         │ → SÍ → ⚡ no_contenido (heuristic)
    └──────────┬───────────────┘         (path corto + título tipo nombre)
               │ NO
               ▼
    ┌──────────────────────────┐
    │ ¿Coincide con regex      │
    │ rule de fuente?          │ → SÍ → ⚡ contenido/no_contenido
    └──────────┬───────────────┘         (regex_rule: rulename)
               │ NO
               ▼
    ┌──────────────────────────┐
    │ Llamar a LLM             │
    │ (OpenAI GPT-4o-mini)     │ → 🤖 contenido/no_contenido
    └──────────┬───────────────┘         (llm_api)
               │
               ▼
    ┌──────────────────────────┐
    │ Si llm_api devuelve      │
    │ no_contenido → agregar   │
    │ a caché para futuro      │
    └──────────────────────────┘
```

**Notas:**
- ⚡ = Sin costo de tokens
- 🤖 = Consume tokens (~$0.00003 USD por URL)
- Métodos 1-3 completan en <1ms
- Método 4 (LLM) toma ~500ms por batch de 50 URLs

### Flujo de Clasificación Nivel 1

```python
def classify_url_level1(url, source_id, source_url):
    """
    Clasificación híbrida optimizada para costos.

    Orden de aplicación:
    1. Caché URLs no-contenido (O(1) lookup)
    2. Heurísticas de collection pages (path corto + nombres)
    3. Reglas regex por fuente (~40-60% cobertura)
    4. Fallback a LLM (solo URLs sin coincidencia)
    """

    # Paso 1: Verificar caché
    if url in cached_no_content_urls:
        return {
            'content_type': 'no_contenido',
            'classification_method': 'cached_url',
            'rule_name': None
        }

    # Paso 2: Aplicar reglas regex
    rules = get_rules_for_source(source_id)
    for rule in rules:
        if re.search(rule['pattern'], url):
            return {
                'content_type': rule['content_type'],
                'classification_method': 'regex_rule',
                'rule_name': rule['name']
            }

    # Paso 3: Fallback a LLM
    prompt = f"""Analiza esta URL y clasifica...
    URL: {url}
    Fuente: {source_url}

    Responde SOLO: contenido o no_contenido"""

    response = llm_client.call(
        model=MODEL_URL_FILTER,
        prompt=prompt,
        temperature=0.0
    )

    content_type = parse_llm_response(response)

    # Actualizar caché si es no_contenido
    if content_type == 'no_contenido':
        add_to_cache(url)

    return {
        'content_type': content_type,
        'classification_method': 'llm_api',
        'rule_name': None
    }
```

### Sistema de Reglas Regex

Las reglas se almacenan en `config/url_classification_rules.yml`:

```yaml
sources:
  elpais:
    rules:
      - name: "elpais_articles"
        pattern: "^https://elpais\\.com/[^/]+/\\d{4}-\\d{2}-\\d{2}/"
        content_type: "contenido"
        coverage: 145  # URLs cubiertas en entrenamiento
        confidence: 0.95

      - name: "elpais_subscriptions"
        pattern: "/suscripciones/"
        content_type: "no_contenido"
        coverage: 23
        confidence: 1.0

      - name: "elpais_newsletters"
        pattern: "/newsletters/"
        content_type: "no_contenido"
        coverage: 12
        confidence: 1.0

  bbc:
    rules:
      - name: "bbc_news_articles"
        pattern: "^https://www\\.bbc\\.com/news/[a-z-]+-\\d+$"
        content_type: "contenido"
        coverage: 89
        confidence: 0.92
```

### Generación Automática de Reglas

Activar con `UPDATE_RULES_ON_RUN=true`:

```bash
UPDATE_RULES_ON_RUN=true venv/bin/python stages/01_extract_urls.py --date 2025-11-10
```

**Proceso:**
1. Clasificar TODAS las URLs con LLM (sin usar reglas)
2. Agrupar URLs por resultado (`contenido` vs `no_contenido`)
3. Analizar patrones comunes en cada grupo
4. Generar reglas regex que cumplan:
   - Cobertura mínima: `MIN_PATTERN_COVERAGE` (default: 5 URLs)
   - Porcentaje mínimo: `RULE_COVERAGE_PERCENTAGE` (default: 10%)
   - Sin falsos positivos en el training set
5. Validar reglas contra ground truth
6. Guardar en `url_classification_rules.yml`

**Cuándo regenerar reglas:**
- Al agregar una nueva fuente
- Cambios en estructura de URLs de fuente existente
- Mensualmente (mantenimiento)
- Cuando cobertura regex cae <50%

**Costo de regeneración:**
- ~150-300 URLs por fuente
- ~$0.003-0.006 USD por fuente (con gpt-4o-mini)
- Recuperable en 2-3 ejecuciones normales

### Caché de URLs No-Contenido

Almacenado en `config/cached_no_content_urls.yml`:

```yaml
# URLs conocidas sin contenido (lookup O(1))
cached_urls:
  - "https://elpais.com/suscripciones/"
  - "https://elpais.com/newsletters/"
  - "https://elpais.com/archivo/"
  - "https://bbc.com/newsletters"
  - "https://ft.com/myft"
  # ... (actualizado automáticamente)

metadata:
  last_updated: "2025-11-10T10:23:45Z"
  total_urls: 347
```

**Ventajas:**
- Lookup instantáneo (O(1))
- Sin consumo de tokens
- Se actualiza automáticamente con cada ejecución
- Útil para URLs recurrentes (footers, headers, navegación)

---

## 🔁 Deduplicación y Upsert Incremental

### Estrategia de Deduplicación

```python
def deduplicate_and_merge(new_urls, existing_df, preserve_original_timestamp=True):
    """
    Merge incremental con tracking dual de timestamps.

    Lógica:
    - URL nueva → extracted_at = last_extracted_at = NOW
    - URL duplicada → extracted_at = ORIGINAL, last_extracted_at = NOW
    """

    # Crear DataFrame de URLs nuevas
    new_df = pd.DataFrame(new_urls)

    if existing_df.empty:
        # Primera ejecución
        new_df['last_extracted_at'] = new_df['extracted_at']
        return new_df

    # Identificar URLs nuevas vs duplicadas
    existing_urls = set(existing_df['url'])
    new_df['is_duplicate'] = new_df['url'].isin(existing_urls)

    # Procesar duplicadas
    duplicates_mask = new_df['is_duplicate']
    for idx in new_df[duplicates_mask].index:
        url = new_df.loc[idx, 'url']
        original_row = existing_df[existing_df['url'] == url].iloc[0]

        # Preservar extracted_at original
        new_df.loc[idx, 'extracted_at'] = original_row['extracted_at']
        new_df.loc[idx, 'last_extracted_at'] = datetime.now(timezone.utc).isoformat()

    # Procesar nuevas
    new_mask = ~duplicates_mask
    new_df.loc[new_mask, 'last_extracted_at'] = new_df.loc[new_mask, 'extracted_at']

    # Merge: Remover duplicadas del DF existente, agregar todas las nuevas
    non_duplicate_existing = existing_df[~existing_df['url'].isin(new_df['url'])]
    merged_df = pd.concat([non_duplicate_existing, new_df], ignore_index=True)

    # Ordenar por last_extracted_at descendente
    merged_df = merged_df.sort_values('last_extracted_at', ascending=False)

    return merged_df
```

### Tracking Temporal Dual

Cada URL tiene **2 timestamps**:

1. **`extracted_at`** (inmutable)
   - Primera vez que la URL fue extraída
   - No cambia en re-extracciones
   - Útil para: filtrar noticias del día, análisis histórico

2. **`last_extracted_at`** (actualizable)
   - Última vez que la URL fue vista
   - Se actualiza en cada re-extracción
   - Útil para: detección de URLs obsoletas, freshness

**Ejemplos:**

```csv
# Primera ejecución (2025-11-09)
url,extracted_at,last_extracted_at
https://elpais.com/noticia-1,2025-11-09T08:00:00Z,2025-11-09T08:00:00Z

# Segunda ejecución (2025-11-10) - URL reaparece
url,extracted_at,last_extracted_at
https://elpais.com/noticia-1,2025-11-09T08:00:00Z,2025-11-10T08:15:00Z
                             ↑ ORIGINAL              ↑ ACTUALIZADO

# Segunda ejecución (2025-11-10) - URL nueva
url,extracted_at,last_extracted_at
https://elpais.com/noticia-2,2025-11-10T08:15:00Z,2025-11-10T08:15:00Z
                             ↑ MISMO                ↑ MISMO
```

### Backups Automáticos

Antes de modificar `data/raw/urls.csv`, se crea backup automático:

```python
def create_backup(csv_path):
    """
    Crea backup con timestamp antes de modificar CSV.

    Formato: urls_backup_YYYYMMDD_HHMMSS.csv
    """
    if not os.path.exists(csv_path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = csv_path.replace(".csv", f"_backup_{timestamp}.csv")

    shutil.copy2(csv_path, backup_path)
    logger.info(f"Backup creado: {backup_path}")

    return backup_path
```

**Gestión de backups:**
```bash
# Listar backups
ls -lh data/raw/urls_backup_*.csv

# Restaurar backup
cp data/raw/urls_backup_20251110_080000.csv data/raw/urls.csv

# Limpiar backups antiguos (manual)
find data/raw -name "urls_backup_*.csv" -mtime +30 -delete
```

---

## ⚙️ Configuración

### Variables de Entorno (`.env`)

```env
# === OpenAI API ===
OPENAI_API_KEY=sk-xxxx

# === Modelos LLM ===
MODEL_URL_FILTER=gpt-4o-mini          # Clasificación nivel 1
MODEL_URL_SUBTYPE=gpt-4o-mini         # Clasificación nivel 2 (opcional)

# === Selenium ===
SELENIUM_HEADLESS=true
SELENIUM_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64)
SELENIUM_TIMEOUT=10                   # Timeout en segundos para carga de páginas y elementos

# === Stage 01: Extract URLs ===
MAX_LINKS_PER_SOURCE=250              # Límite de URLs por fuente (después de clasificar)
TEST_MAX_RAW_LINKS=                   # Límite para testing (vacío = sin límite)
MIN_TITLE_LENGTH=10                   # Mínimo caracteres para titular válido
# Nota: Límite hardcoded de 10000 enlaces raw antes de clasificación (no configurable)
ENABLE_NEWS_CLUSTERING=true           # Ejecuta clustering semántico tras cada ingesta
CLUSTERING_CONFIG_PATH=poc_clustering/config.yml  # Config de modelo/thresholds

# === URL Classification Rules ===
USE_CACHED_RULES=true                 # Usar reglas regex antes de LLM (recomendado)
UPDATE_RULES_ON_RUN=false             # Regenerar reglas automáticamente (usa más tokens)
MIN_PATTERN_COVERAGE=5                # Mínimo URLs que debe cubrir un patrón
RULE_COVERAGE_PERCENTAGE=10.0         # Porcentaje mínimo de cobertura

# === Content Classification Levels ===
CLASSIFY_CONTENT_SUBTYPE=false        # Nivel 2 (noticia vs otros) - false=más rápido
```

### Configuración de Clustering Semántico

El clustering semántico es **opcional** y se activa con `ENABLE_NEWS_CLUSTERING=true`.

**Variables de entorno:**
```env
ENABLE_NEWS_CLUSTERING=true                      # Activar clustering incremental
CLUSTERING_CONFIG_PATH=poc_clustering/config.yml # Path al config YAML
```

**Configuración del modelo (`poc_clustering/config.yml`):**

```yaml
model:
  # Modelo de embeddings (HuggingFace)
  name: intfloat/multilingual-e5-small
  cache_dir: ./models_cache
  batch_size: 100
  device: cpu  # o 'cuda' si tienes GPU

state:
  # Directorio para índice FAISS persistente
  directory: ./state

clustering:
  # Threshold de similitud base (0.94 = muy estricto, solo noticias casi idénticas)
  # Reduce falsos positivos en patrones estructurales similares
  similarity_threshold: 0.94

  # Threshold adaptativo por cluster (μ - k*σ)
  adaptive_threshold: true
  adaptive_k: 1.1

  # Tamaño mínimo de cluster para reportes
  min_cluster_size: 2

  # Vecinos a revisar en búsqueda FAISS
  max_neighbors: 3
```

**¿Qué hace el clustering?**

1. **Tras Stage 01**, se ejecuta automáticamente `PersistentClusterer`
2. **Embebe solo URLs nuevas** (sin `cluster_id`) usando `sentence-transformers`
3. **Busca en índice FAISS** persistente para encontrar vecinos similares
4. **Asigna cluster existente** si similitud ≥ threshold adaptativo, o **crea cluster nuevo**
5. **Actualiza estadísticas** en tabla `clusters` (article_count, similitud promedio)
6. **Persiste embeddings** en `url_embeddings` y actualiza índice FAISS

**Tablas DB creadas:**

- `urls.cluster_id` → FK a `clusters.id`
- `urls.cluster_assigned_at` → Timestamp de asignación
- `clusters` → Metadata por cluster (centroid, count, stats)
- `url_embeddings` → Cache de vectores para índice FAISS

**Migración requerida** (solo una vez):

```bash
venv/bin/python scripts/migrate_add_cluster_id.py
```

**Outputs:**

```
INFO: Clustering: 45 new URLs processed (3 clusters created)
INFO: Total clusters: 127 | Index vectors: 1523
```

**Consultar clusters:**

```bash
# Ver distribución de clusters
sqlite3 data/news.db "
SELECT cluster_id, COUNT(*) as size
FROM urls
WHERE cluster_id IS NOT NULL
GROUP BY cluster_id
ORDER BY size DESC
LIMIT 10;
"

# URLs de un cluster específico
sqlite3 data/news.db "
SELECT title, url, extracted_at
FROM urls
WHERE cluster_id = '20251121_a3f8b2c4'
ORDER BY extracted_at;
"
```

**Costos:**

- **Primera ejecución:** ~2-3 segundos para embeding (CPU)
- **Subsiguientes:** Solo embebe URLs nuevas (incremental)
- **Sin costos LLM:** Usa embeddings locales (sentence-transformers)

### Configuración de Fuentes (`config/sources.yml`)

```yaml
sources:
  - id: "elpais"
    url: "https://elpais.com/"
    selectors:
      - "article a"
      - ".headline a"
      - "h2 a"
      - "h3 a"
    enabled: true
    notes: "Portada principal de El País"

  - id: "bbc"
    url: "https://www.bbc.com/news"
    selectors:
      - "a.gs-c-promo-heading"
      - "h3 a"
    enabled: true

  - id: "ft"
    url: "https://www.ft.com/"
    selectors:
      - "a.js-teaser-heading-link"
      - ".o-teaser__heading a"
    enabled: false  # Temporalmente deshabilitada
    notes: "Requiere cookies acceptance"
```

**Campos:**
- `id`: Identificador único (usado para nombrar reglas)
- `url`: URL de la página a scrapear
- `selectors`: Lista de selectores CSS para extraer enlaces (se prueban todos)
- `enabled`: Si está activa (false = se saltea)
- `notes`: Comentarios opcionales

### Categorías de Contenido (`config/content_categories.yml`)

```yaml
# Nivel 1: content_type (sintáctico)
level1:
  contenido:
    description: "URLs que apuntan a contenido editorial (artículos, noticias, análisis)"
    examples:
      - "https://elpais.com/internacional/2025-11-10/noticia"
      - "https://bbc.com/news/world-europe-12345678"

  no_contenido:
    description: "URLs auxiliares sin contenido editorial"
    subcategories:
      navegacion:
        - "Secciones"
        - "Categorías"
        - "Tags"
      utilidades:
        - "Búsqueda"
        - "Archivo/hemeroteca"
        - "Mi cuenta"
      marketing:
        - "Suscripciones"
        - "Newsletters signup"
        - "Publicidad"

# Nivel 2: content_subtype (semántico, OPCIONAL)
level2:
  noticia:
    description: "Contenido noticioso con carácter informativo"
    characteristics:
      - "Reporta hechos actuales"
      - "Tono neutral/objetivo"
      - "Estructura piramidal invertida"

  otros:
    description: "Otros contenidos editoriales"
    subcategories:
      - "Opinión/editorial"
      - "Análisis"
      - "Reportajes/features"
      - "Entrevistas"
      - "Reseñas (cultura, tecnología)"
```

---

## 🚀 Ejecución

### Modo Normal (Producción)

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar con fecha específica
python stages/01_extract_urls.py --date 2025-11-10

# O usar directamente el intérprete del venv (recomendado)
venv/bin/python stages/01_extract_urls.py --date 2025-11-10

# Usar fecha actual (se toma de system time)
venv/bin/python stages/01_extract_urls.py
```

**Configuración recomendada para producción:**
```env
USE_CACHED_RULES=true
UPDATE_RULES_ON_RUN=false
CLASSIFY_CONTENT_SUBTYPE=false
MAX_LINKS_PER_SOURCE=250
TEST_MAX_RAW_LINKS=
```

**Características:**
- ✅ Usa reglas regex cacheadas (máxima eficiencia)
- ✅ No regenera reglas (sin costo adicional)
- ✅ Solo clasificación nivel 1 (más rápido)
- ✅ Límite de 250 URLs por fuente

### Modo Testing

```bash
# Procesar solo primeras 50 URLs de cada fuente
TEST_MAX_RAW_LINKS=50 venv/bin/python stages/01_extract_urls.py --date 2025-11-10

# Sin límite pero solo una fuente (editar sources.yml)
venv/bin/python stages/01_extract_urls.py --date 2025-11-10
```

### Regenerar Reglas (Mantenimiento Mensual)

```bash
# ⚠️ ATENCIÓN: Usa MUCHOS más tokens (clasifica TODAS las URLs con LLM)
UPDATE_RULES_ON_RUN=true venv/bin/python stages/01_extract_urls.py --date 2025-11-10

# Con límite de testing (para probar generación de reglas)
UPDATE_RULES_ON_RUN=true TEST_MAX_RAW_LINKS=100 venv/bin/python stages/01_extract_urls.py --date 2025-11-10
```

**Cuándo usar:**
- Después de agregar nueva fuente
- Mensualmente (mantenimiento)
- Si cobertura de reglas cae <50%
- Cambios en estructura de URLs de fuente existente

**Costo aproximado:**
- ~$0.003-0.006 USD por fuente
- Recuperable en 2-3 ejecuciones normales

### Clasificación Nivel 2 (Semántica)

```bash
# Activar clasificación semántica (noticia vs otros)
CLASSIFY_CONTENT_SUBTYPE=true venv/bin/python stages/01_extract_urls.py --date 2025-11-10
```

**Cuándo usar:**
- Si necesitas distinguir noticias de otros contenidos editoriales
- Para análisis más granular
- Stages posteriores requieren esta información

**Trade-offs:**
- ❌ Más lento (~50% más tiempo)
- ❌ Más costoso (100% de URLs de contenido pasan por LLM)
- ✅ Clasificación más precisa para stages posteriores

### Ejecución en Producción (Cron)

```bash
# Crontab: ejecutar diariamente a las 8:00 AM
0 8 * * * cd /home/user/newsletter_utils && venv/bin/python stages/01_extract_urls.py >> logs/cron.log 2>&1

# Con fecha explícita
0 8 * * * cd /home/user/newsletter_utils && venv/bin/python stages/01_extract_urls.py --date $(date +\%Y-\%m-\%d) >> logs/cron.log 2>&1
```

### Argumentos CLI

```bash
python stages/01_extract_urls.py --help

usage: 01_extract_urls.py [-h] [--date DATE]

Extract URLs from news sources (Stage 01)

optional arguments:
  -h, --help            show this help message and exit
  --date DATE           Run date (YYYY-MM-DD format). Default: today
```

**Ejemplos:**
```bash
# Fecha específica
venv/bin/python stages/01_extract_urls.py --date 2025-11-09

# Fecha actual (default)
venv/bin/python stages/01_extract_urls.py

# Combinar con variables de entorno inline
UPDATE_RULES_ON_RUN=true venv/bin/python stages/01_extract_urls.py --date 2025-11-10
```

**Nota:** Para procesar solo una fuente o forzar actualización de reglas, usar variables de entorno:
```bash
# Forzar regeneración de reglas
UPDATE_RULES_ON_RUN=true venv/bin/python stages/01_extract_urls.py

# Procesar solo fuentes específicas (editar config/sources.yml: enabled: false)
```

---

## 📄 Outputs y Formato

### CSV Principal: `data/raw/urls.csv`

**Características:**
- Separador: TAB (`\t`)
- Encoding: UTF-8
- Headers: ✅ Sí (primera línea)
- Formato: CSV estándar compatible con pandas, Excel, Google Sheets

**Esquema:**

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| `url` | TEXT | NO | URL completa del artículo (clave única) |
| `title` | TEXT | SÍ | Título extraído del elemento `<a>` |
| `source` | TEXT | NO | URL de la fuente (ej: https://elpais.com) |
| `content_type` | TEXT | NO | `contenido` \| `no_contenido` |
| `content_subtype` | TEXT | SÍ | `noticia` \| `otros` \| `NULL` |
| `classification_method` | TEXT | NO | `cached_url` \| `regex_rule` \| `llm_api` |
| `rule_name` | TEXT | SÍ | Nombre de regla regex aplicada (o `NULL`) |
| `extracted_at` | TIMESTAMP | NO | Primera vez extraída (ISO 8601, UTC) |
| `last_extracted_at` | TIMESTAMP | NO | Última vez vista (ISO 8601, UTC) |

**Ejemplo:**

```tsv
url	title	source	content_type	content_subtype	classification_method	rule_name	extracted_at	last_extracted_at
https://elpais.com/internacional/2025-11-10/crisis-europa	Crisis en Europa	https://elpais.com	contenido	NULL	regex_rule	elpais_articles	2025-11-10T08:00:00Z	2025-11-10T08:00:00Z
https://bbc.com/news/world-europe-67890123	UK Election Results	https://bbc.com/news	contenido	noticia	llm_api	NULL	2025-11-10T08:05:12Z	2025-11-10T08:05:12Z
https://ft.com/content/abc123def456	Markets rally	https://ft.com	contenido	NULL	cached_url	NULL	2025-11-09T08:00:00Z	2025-11-10T08:05:45Z
```

**Notas:**
- `title` puede ser `NULL` si no se pudo extraer del HTML
- `content_subtype` es `NULL` si `CLASSIFY_CONTENT_SUBTYPE=false`
- `rule_name` es `NULL` si se usó LLM o caché
- Timestamps en formato ISO 8601 con timezone UTC (sufijo `Z`)

### Backups: `data/raw/urls_backup_*.csv`

**Formato:** Idéntico a `urls.csv`

**Naming convention:** `urls_backup_YYYYMMDD_HHMMSS.csv`

**Ejemplos:**
```
data/raw/urls_backup_20251110_080000.csv
data/raw/urls_backup_20251110_120030.csv
data/raw/urls_backup_20251109_080000.csv
```

**Gestión:**
- Se crean automáticamente antes de cada modificación
- No se eliminan automáticamente (gestión manual)
- Útil para rollback en caso de error

### Logs: `logs/YYYY-MM-DD/01_extract_urls.log`

**Formato:** JSON Lines (una línea JSON por log entry)

**Ejemplo:**

```json
{"timestamp":"2025-11-10T08:00:05Z","stage":"01_extract_urls","event":"start","config":{"use_cached_rules":true,"update_rules_on_run":false,"classify_subtype":false,"max_links_per_source":250}}
{"timestamp":"2025-11-10T08:00:10Z","stage":"01_extract_urls","source":"elpais","event":"extraction_start","url":"https://elpais.com"}
{"timestamp":"2025-11-10T08:00:45Z","stage":"01_extract_urls","source":"elpais","event":"extraction_complete","raw_urls_extracted":312}
{"timestamp":"2025-11-10T08:01:30Z","stage":"01_extract_urls","source":"elpais","event":"classification_complete","stats":{"contenido":245,"no_contenido":67,"methods":{"cached_url":89,"regex_rule":156,"llm_api":67}}}
{"timestamp":"2025-11-10T08:01:35Z","stage":"01_extract_urls","source":"elpais","event":"dedup_complete","urls_new":198,"urls_duplicate":47}
{"timestamp":"2025-11-10T08:01:37Z","stage":"01_extract_urls","source":"elpais","event":"save_complete","csv_path":"data/raw/urls.csv","total_urls":1247}
{"timestamp":"2025-11-10T08:01:37Z","stage":"01_extract_urls","source":"elpais","event":"source_complete","duration_seconds":87.3,"tokens_used":3420,"cost_usd":0.00051}
{"timestamp":"2025-11-10T08:15:22Z","stage":"01_extract_urls","event":"complete","status":"success","sources_processed":3,"total_duration_seconds":922.8,"total_tokens_used":12845,"total_cost_usd":0.00192}
```

---

## 💰 Optimizaciones de Costo

### Comparación: Naive vs Optimizado

#### Escenario: Extraer 1000 URLs de una fuente

**Enfoque Naive (solo LLM):**
```
1000 URLs × clasificación nivel 1 (LLM) = 1000 llamadas API
Tokens promedio por llamada: ~200 (input) + 10 (output) = 210 tokens
Total tokens: 1000 × 210 = 210,000 tokens

Costo (gpt-4o-mini):
- Input: 200,000 × $0.15/1M = $0.030
- Output: 10,000 × $0.60/1M = $0.006
- TOTAL: $0.036 USD
```

**Enfoque Optimizado (híbrido):**
```
1. Caché (20% cobertura): 200 URLs × 0 tokens = 0 tokens
2. Regex (65% cobertura): 650 URLs × 0 tokens = 0 tokens
3. LLM fallback (15%): 150 URLs × 210 tokens = 31,500 tokens

Costo (gpt-4o-mini):
- Input: 30,000 × $0.15/1M = $0.0045
- Output: 1,500 × $0.60/1M = $0.0009
- TOTAL: $0.0054 USD

AHORRO: $0.036 - $0.0054 = $0.0306 USD (85% reducción)
```

#### Escenario: Ejecución diaria con 5 fuentes

**Naive:**
- 5 fuentes × 1000 URLs × $0.036 = $0.18 USD/día
- Mensual: $0.18 × 30 = $5.40 USD/mes
- Anual: $5.40 × 12 = $64.80 USD/año

**Optimizado:**
- 5 fuentes × 1000 URLs × $0.0054 = $0.027 USD/día
- Mensual: $0.027 × 30 = $0.81 USD/mes
- Anual: $0.81 × 12 = $9.72 USD/año

**AHORRO ANUAL: $55.08 USD (85% reducción)**

### Optimización Adicional: Heurísticas de Collection Pages

Además del sistema regex + caché, existe una **capa adicional de optimización** que detecta páginas de autor/sección SIN llamar al LLM:

**Heurísticas implementadas:**

1. **Path corto + Título tipo nombre**
   ```
   URL: https://elpais.com/autor/john-smith/
   Título: "John Smith"
   → Detecta: página de autor (NO artículo)
   ```

2. **Patrones comunes de collection pages**
   ```python
   patterns = [
       '/author/', '/columnist/', '/writers/',
       '/by/', '/perfil/', '/profile/',
       '/category/', '/section/', '/tema/'
   ]
   ```

3. **Título con nombre propio sin verbos**
   - Detecta nombres (mayúsculas consecutivas)
   - Verifica ausencia de verbos comunes
   - Si coincide → `no_contenido (heuristic)`

**Impacto:**
- **Ahorro adicional:** 5-15% de URLs (varía por fuente)
- **Sin costo:** Cero tokens consumidos
- **Velocidad:** <1ms por URL
- **Aplicación:** Antes de regex rules

**Ejemplo real:**
```
# Portada de BBC con 200 enlaces
- 25 URLs → cached_url (10%)
- 30 URLs → heuristic (15%)  ← OPTIMIZACIÓN ADICIONAL
- 100 URLs → regex_rule (50%)
- 45 URLs → llm_api (25%)

Total sin LLM: 155/200 (77.5%)
Tokens ahorrados: 155 × 210 = 32,550 tokens (~$0.005 USD)
```

Ver implementación en `common/llm.py:378-468`

### Recomendaciones de Optimización

1. **Mantener reglas actualizadas:**
   - Regenerar mensualmente con `UPDATE_RULES_ON_RUN=true`
   - Revisar fuentes con baja cobertura

2. **Desactivar nivel 2 en producción:**
   - `CLASSIFY_CONTENT_SUBTYPE=false` (default)
   - Activar solo si stages posteriores lo requieren

3. **Ajustar límites por fuente:**
   - `MAX_LINKS_PER_SOURCE=250` es razonable
   - Reducir si hay muchas fuentes

4. **Usar modelo más barato:**
   - `MODEL_URL_FILTER=gpt-4o-mini` (recomendado)
   - No usar `gpt-4o` salvo necesidad específica

5. **Monitorear métricas:**
   - Revisar logs de costo diariamente
   - Establecer alertas si costo >$X/día

---

## 📊 Token Usage Tracking

Stage 01 incluye un sistema completo de tracking de consumo de tokens OpenAI, implementado en `common/token_tracker.py`.

### Métricas Rastreadas

```python
{
    "prompt_tokens": 1234,        # Tokens enviados a OpenAI
    "completion_tokens": 567,     # Tokens recibidos de OpenAI
    "total_tokens": 1801,         # Suma de ambos
    "cost_usd": 0.000123,         # Costo estimado en USD
    "model": "gpt-4o-mini",       # Modelo usado
    "task": "url_filter"          # Tarea específica
}
```

### Ubicación de Logs

Los tokens se registran en **dos ubicaciones**:

1. **Console output:**
   ```
   [2025-11-10 08:15:32] Completed source: elpais (120 contenido, 85 no_contenido)
   [2025-11-10 08:15:32] Tokens used: 12,450 prompt + 3,200 completion = 15,650 total (~$0.0045 USD)
   ```

2. **Archivo de log:**
   ```
   logs/2025-11-10/01_extract_urls.log
   ```

   Ejemplo de entrada:
   ```
   [2025-11-10 08:15:32] INFO - Token usage for source 'elpais':
     - Prompt tokens: 12,450
     - Completion tokens: 3,200
     - Total tokens: 15,650
     - Estimated cost: $0.0045 USD
     - Model: gpt-4o-mini
   ```

### Cálculo de Costos

**Precios actuales (Enero 2025):**
```python
# gpt-4o-mini
prompt_cost = $0.150 / 1M tokens
completion_cost = $0.600 / 1M tokens

# gpt-4o (NO recomendado para Stage 01)
prompt_cost = $2.50 / 1M tokens
completion_cost = $10.00 / 1M tokens
```

**Fórmula:**
```python
cost_usd = (prompt_tokens / 1_000_000) * prompt_price + \
           (completion_tokens / 1_000_000) * completion_price
```

### Consumo Típico por Fuente

**Sin optimizaciones (100% LLM):**
```
Fuente: BBC News (200 URLs)
- Prompt tokens: ~42,000 (210 tokens/URL × 200)
- Completion tokens: ~10,000 (50 tokens/URL × 200)
- Total: 52,000 tokens
- Costo: ~$0.012 USD
```

**Con optimizaciones (25% LLM):**
```
Fuente: BBC News (200 URLs)
- URLs clasificadas sin LLM: 150 (75%)
  - Cached URLs: 20 (10%)
  - Heuristics: 30 (15%)
  - Regex rules: 100 (50%)
- URLs clasificadas con LLM: 50 (25%)
  - Prompt tokens: ~10,500
  - Completion tokens: ~2,500
  - Total: 13,000 tokens
  - Costo: ~$0.003 USD

Ahorro: $0.009 USD (75% reducción)
```

### Tracking en el Código

**Inicialización:**
```python
from common.token_tracker import TokenTracker

tracker = TokenTracker()
```

**Registrar uso:**
```python
# Después de cada llamada a OpenAI
response = client.chat.completions.create(...)

tracker.track(
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    model="gpt-4o-mini",
    task="url_classification_level1"
)
```

**Obtener resumen:**
```python
summary = tracker.get_summary()
print(f"Total tokens: {summary['total_tokens']:,}")
print(f"Total cost: ${summary['cost_usd']:.4f} USD")
```

### Alertas de Costo

Para establecer alertas automáticas, agregar al `.env`:

```env
# Alertas de costo (futuro - no implementado aún)
MAX_COST_PER_RUN_USD=0.50          # Cancelar si costo > $0.50
WARN_COST_PER_SOURCE_USD=0.05      # Warning si fuente > $0.05
EMAIL_ALERTS=true
ALERT_EMAIL=admin@example.com
```

**Nota:** Las alertas están diseñadas pero **NO implementadas** en Stage 01 actual.

### Análisis de Eficiencia

Para analizar la eficiencia del sistema de clasificación:

```bash
# Ver logs de token usage
cat logs/2025-11-10/01_extract_urls.log | grep "Token usage"

# Sumar tokens totales del día
cat logs/2025-11-10/01_extract_urls.log | grep "total_tokens" | awk '{sum+=$NF} END {print sum}'

# Calcular costo total del día
cat logs/2025-11-10/01_extract_urls.log | grep "cost_usd" | awk '{sum+=$NF} END {printf "%.4f\n", sum}'
```

### Métricas de Clasificación

Además del tracking de tokens, Stage 01 registra métricas de clasificación:

```
[2025-11-10 08:15:32] Classification breakdown for source 'elpais':
  - cached_url: 20 URLs (10.0%)
  - heuristic: 30 URLs (15.0%)
  - regex_rule: 100 URLs (50.0%)
  - llm_api: 50 URLs (25.0%)

  Total without LLM: 150/200 (75.0%)
  Tokens saved: ~39,000 tokens (~$0.009 USD)
```

Estas métricas permiten:
- Identificar fuentes con baja cobertura de reglas
- Calcular ROI del sistema de optimización
- Detectar oportunidades de mejora

Ver `common/llm.py:800-850` para implementación completa.

---

## 🐛 Troubleshooting

### Errores Comunes

#### 1. Selenium WebDriver no inicia

**Síntomas:**
```
selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH
```

**Solución:**
```bash
# Verificar que Chrome/Chromium está instalado
google-chrome --version

# Instalar chromedriver manualmente
sudo apt-get install chromium-chromedriver  # Linux
brew install chromedriver                  # macOS

# O usar webdriver-manager (instalado con requirements.txt)
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
```

#### 2. OpenAI API Key inválida

**Síntomas:**
```
openai.error.AuthenticationError: Incorrect API key provided
```

**Solución:**
```bash
# Verificar que .env contiene la key correcta
cat .env | grep OPENAI_API_KEY

# Probar key manualmente
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

#### 3. CSV corrupto o mal formateado

**Síntomas:**
```
pandas.errors.ParserError: Error tokenizing data
```

**Solución:**
```bash
# Verificar encoding
file data/raw/urls.csv

# Contar columnas
head -1 data/raw/urls.csv | awk -F'\t' '{print NF}'

# Restaurar desde backup
cp data/raw/urls_backup_20251110_080000.csv data/raw/urls.csv
```

#### 4. Timeout en extracción de URLs

**Síntomas:**
```
selenium.common.exceptions.TimeoutException: Message:
```

**Solución:**
```python
# Aumentar timeouts en selenium_utils.py
WAIT_TIMEOUT = 30  # Default: 10
PAGE_LOAD_TIMEOUT = 60  # Default: 30
```

#### 5. URLs duplicadas con títulos diferentes

**Síntomas:**
```
# Misma URL aparece múltiples veces en logs
Skipped link with short title (8 chars): /noticia-123 → 'Ver más'
Replacing link for /noticia-123: new title longer (45 vs 16 chars)
```

**Explicación:**
Esto es **comportamiento esperado**. El sistema deduplica URLs dentro de una misma página y conserva el título más largo. Ver sección "Deduplicación Intra-Página" en stages/README_STAGE01.md:183.

**Ajustes:**
```env
# Cambiar longitud mínima de título (default: 10)
MIN_TITLE_LENGTH=15  # Más estricto
MIN_TITLE_LENGTH=5   # Más permisivo
```

#### 6. Muchos enlaces descartados por título corto

**Síntomas:**
```
Skipped link with short title (5 chars): https://... → 'Más'
Skipped link with short title (7 chars): https://... → 'Leer ++'
```

**Solución:**
```bash
# Reducir el mínimo de caracteres requerido
MIN_TITLE_LENGTH=5 venv/bin/python stages/01_extract_urls.py

# O revisar selectores CSS en sources.yml para ser más específico
```

---

## ⚠️ Limitaciones y Restricciones Conocidas

### 1. **Manejo de Cookies NO Implementado**

**Descripción:**
El sistema NO maneja automáticamente banners de cookies o aceptación de términos.

**Fuentes afectadas:**
- Financial Times (requiere aceptar cookies)
- Algunos sitios de BBC (ocasionalmente)
- Sitios con GDPR compliance obligatorio

**Solución actual:**
```yaml
# config/sources.yml
- id: "ft"
  url: "https://www.ft.com/"
  enabled: false  # Deshabilitada por cookies
  notes: "Requiere cookies acceptance"
```

**Workaround manual:**
1. Abrir el sitio manualmente en navegador
2. Aceptar cookies
3. Copiar cookies del navegador al script (NO implementado)
4. O implementar lógica custom de click en banner (futuro)

### 2. **Límite Hardcoded de 10,000 Enlaces**

**Descripción:**
Antes de clasificar, hay un límite hardcoded de 10,000 enlaces raw por fuente.

**Ubicación:** `stages/01_extract_urls.py:156` → `max_links=10000`

**NO configurable** vía `.env` o argumentos CLI.

**Impacto:**
Si una fuente tiene >10,000 enlaces (raro), se procesarán solo los primeros 10,000.

**Razón del límite:**
- Protección contra scraping infinito
- Prevención de out-of-memory
- Control de costos de API

**Configuración recomendada:**
```env
# Límites efectivos por fuente (en orden de aplicación):
# 1. Hardcoded: 10000 enlaces raw (antes de clasificación)
# 2. TEST_MAX_RAW_LINKS: opcional, para testing (antes de clasificación)
# 3. MAX_LINKS_PER_SOURCE: 250 (después de clasificación)
```

### 3. **Batch Size de LLM NO Configurable**

**Descripción:**
El sistema clasifica URLs en batches de 50 (hardcoded).

**Ubicación:** `common/llm.py:116`, `llm.py:478`, `llm.py:752`

**Problema:**
Usuarios con rate limits estrictos de OpenAI no pueden reducir el batch size sin editar código.

**Workaround:**
```bash
# Reducir URLs totales procesadas
TEST_MAX_RAW_LINKS=25 venv/bin/python stages/01_extract_urls.py
```

### 4. **Precios de Tokens Hardcoded**

**Descripción:**
Los costos estimados usan precios de OpenAI hardcoded en `token_tracker.py:103-120`.

**Actualización:** Precios de 2025-01

**Riesgo:**
Si OpenAI cambia precios, los costos reportados estarán desactualizados.

**Recomendación:**
Verificar costos reales en dashboard de OpenAI mensualmente.

### 5. **Separador TAB Obligatorio**

**Descripción:**
Los CSV usan separador TAB (`\t`) hardcoded, NO configurable.

**Razón:**
Títulos de noticias suelen contener comas, lo que rompería CSV con separador `,`.

**Implicación:**
- Compatible con Excel, Google Sheets, pandas
- NO compatible con herramientas que esperan comas
- Conversión manual requerida si se necesita formato diferente

### 6. **Condiciones de Parada del Scrolling**

**Descripción:**
El scroll automático se detiene en 2 condiciones:

1. **Límite alcanzado:** 10,000 enlaces (o `TEST_MAX_RAW_LINKS`)
2. **Sin nuevos enlaces:** 3 iteraciones consecutivas sin encontrar URLs nuevas

**Implicación:**
Sitios con lazy-loading lento pueden detener el scroll prematuramente.

**Ajuste:**
```env
# Aumentar timeout para sitios lentos
SELENIUM_TIMEOUT=30  # Default: 10
```

### 7. **Sin Soporte para JavaScript-heavy Sites**

**Descripción:**
Sitios que cargan TODO el contenido vía JavaScript asíncrono pueden no funcionar.

**Ejemplos problemáticos:**
- SPAs (Single Page Applications) con routing client-side
- Infinite scroll sin URLs estáticas
- Contenido protegido por anti-scraping

**Detección:**
```bash
# Si logs muestran 0 enlaces extraídos consistentemente
Found 0 elements with selector: article a
```

**Solución:**
Revisar selectores CSS en `sources.yml` o descartar la fuente.

---

## 📚 Referencias

### Documentación Relacionada

- **[CLAUDE.md](../CLAUDE.md)** - Documentación completa del proyecto
- **[URL_CLASSIFICATION_RULES.md](../URL_CLASSIFICATION_RULES.md)** - Detalles del sistema de reglas
- **[README.md](../README.md)** - Guía de inicio rápido

### Archivos Clave

- `stages/01_extract_urls.py` - Script principal (stages/01_extract_urls.py:1)
- `common/stage01_extraction/selenium_utils.py` - Utilidades Selenium
- `common/stage01_extraction/url_classifier.py` - Clasificador híbrido
- `common/llm.py` - Cliente LLM (common/llm.py:1)
- `common/dedup.py` - Deduplicación (common/dedup.py:1)
- `config/sources.yml` - Configuración de fuentes
- `config/url_classification_rules.yml` - Reglas regex
- `config/cached_no_content_urls.yml` - Caché de URLs

---

**Última actualización:** 2025-11-10
**Versión:** 1.0.0
**Estado:** Producción ✅
