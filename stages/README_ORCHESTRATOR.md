# Pipeline Orchestrator

> **Versión:** 3.1 (Resume & Replay)
> **Última actualización:** 2025-11-20

## 📋 Índice

1. [Descripción](#descripción)
2. [Funcionalidades](#funcionalidades)
3. [Arquitectura](#arquitectura)
4. [Configuración](#configuración)
5. [Uso](#uso)
6. [Tracking de Estado](#tracking-de-estado)
7. [Gestión de Errores](#gestión-de-errores)
8. [Ejemplos](#ejemplos)
9. [Troubleshooting](#troubleshooting)

---

## Descripción

El **Pipeline Orchestrator** (`stages/orchestrator.py`) coordina la ejecución completa del pipeline de generación de newsletters (stages 01-04) para múltiples newsletters definidas en `config/newsletters.yml`.

### Flujo de Ejecución

```
┌─────────────────────────────────────────┐
│ 1. Cargar config/newsletters.yml        │
│    - Parsear configuraciones             │
│    - Validar parámetros                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 2. Stage 01 (común para todas)          │
│    - Extracción de URLs                  │
│    - Se ejecuta UNA VEZ por fecha        │
└──────────────┬──────────────────────────┘
               │
               ▼
         ┌─────────────┐
         │ Por cada    │
         │ newsletter  │
         └──────┬──────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ 3. Stage 02: Filter & Classify          │
│    - Clasificación temática              │
│    - Temporalidad (opcional)             │
│    - Idempotente (skip si ya clasificado)│
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 4. Stage 03: Ranker                      │
│    - Ranking con LLM                     │
│    - Deduplicación semántica             │
│    - Reutiliza ranking si existe         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 5. Stage 04: Extract Content             │
│    - Extracción de contenido completo    │
│    - Bypass de paywalls                  │
│    - Idempotente (skip si ya extraído)   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 6. Tracking en BD (pipeline_runs)       │
│    - Estado por newsletter/stage         │
│    - Errores y outputs                   │
└─────────────────────────────────────────┘
```

---

## Funcionalidades

### ✅ Características Principales

1. **Ejecución Secuencial por Newsletter**
   - Stage 01 se ejecuta una vez (común)
   - Stages 02-04 se ejecutan por cada newsletter
   - Continúa aunque una newsletter falle

2. **Configuración Completa por Newsletter**
   - Cada newsletter puede configurar **TODOS** los parámetros de stages 02-04
   - Valores omitidos usan defaults de `.env`

3. **Idempotencia**
   - Stage 02: Solo clasifica URLs nuevas (sin `categoria_tematica`)
   - Stage 03: Reutiliza ranking existente con mismos parámetros
   - Stage 04: Solo extrae contenido nuevo (sin `full_content`)

4. **Tracking de Estado**
   - Tabla `pipeline_runs` en SQLite
   - Estado por newsletter/stage: `pending`, `running`, `completed`, `failed`
   - Outputs y errores almacenados

5. **Manejo de Errores**
   - Logs detallados por fecha
   - Continúa con siguiente newsletter si una falla
   - Resumen final con todos los estados

6. **Dry-Run Mode**
   - Muestra qué comandos se ejecutarían sin correrlos
   - Útil para validar configuración

7. **Force Mode**
   - Sobrescribe idempotencia en todos los stages
   - Regenera todo desde cero

---

## Arquitectura

### Tabla `pipeline_runs`

```sql
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY,
    newsletter_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    stage INTEGER NOT NULL,  -- 1, 2, 3, 4, 5
    status TEXT NOT NULL,    -- 'pending', 'running', 'completed', 'failed'
    output_file TEXT,        -- Path al archivo generado
    error_message TEXT,      -- Mensaje de error si falló
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP
);
```

### Flujo de Variables de Entorno

El orchestrator sobrescribe temporalmente variables de `.env` basándose en la configuración de cada newsletter:

| Etapa | Variables Configurables |
|-------|------------------------|
| **Stage 02** | `STAGE02_BATCH_SIZE`, `MODEL_CLASSIFIER` |
| **Stage 03** | `RANKER_METHOD`, `RANKER_TOP_X`, `RANKER_ENABLE_CLUSTERING`, `RANKER_CLUSTERING_MULTIPLIER`, `MODEL_RANKER` |
| **Stage 04** | `STAGE04_TIMEOUT`, `STAGE04_MIN_WORD_COUNT`, `STAGE04_MAX_WORD_COUNT`, `MODEL_PAYWALL_VALIDATOR`, `MODEL_XPATH_DISCOVERY`, `STAGE04_ARCHIVE_WAIT_TIME`, `STAGE04_MAX_RETRIES` |

---

## Configuración

### Archivo `config/newsletters.yml`

Ejemplo completo:

```yaml
newsletters:
  - name: "tech_daily"
    date: "2025-11-13"
    # sources: ["ft", "bbc"]  # Opcional

    stage02:
      categories: ["Tecnología", "IA"]
      no_temporality: false
      batch_size: 30
      # model_classifier: "gpt-4o-mini"
      force: false

    stage03:
      ranker_method: "level_scoring"
      ranker_top_x: 25
      max_headlines: 25
      enable_clustering: true
      clustering_multiplier: 2
      # model_ranker: "gpt-4o-mini"
      force: false

    stage04:
      max_articles: 10
      force: false
      skip_paywall_check: false
      timeout: 30

    verbose: false
```

### Parámetros Disponibles

#### **Global** (todas las newsletters)

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `name` | `str` | ✅ | Nombre único de la newsletter |
| `date` | `str` | ✅* | Fecha (YYYY-MM-DD) o usar `start`/`end` |
| `start` | `str` | ✅* | Datetime inicio (ISO format) |
| `end` | `str` | ✅* | Datetime fin (ISO format) |
| `sources` | `list[str]` | ❌ | IDs de fuentes (de `sources.yml`) |
| `verbose` | `bool` | ❌ | Logging verbose |
| `db_path` | `str` | ❌ | Path custom a DB |

\* Requiere `date` **o** (`start` + `end`)

#### **Stage 02: Filter & Classify**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `categories` | `list[str]` | `None` | Post-filtro de categorías |
| `no_temporality` | `bool` | `false` | Skip clasificación temporalidad |
| `batch_size` | `int` | `30` | Tamaño de batch LLM |
| `model_classifier` | `str` | `gpt-4o-mini` | Modelo LLM |
| `force` | `bool` | `false` | Reclasificar URLs ya categorizadas |

#### **Stage 03: Ranker**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `ranker_method` | `str` | `recursive` | `'level_scoring'` o `'recursive'` |
| `ranker_top_x` | `int` | `25` | Top X URLs (level_scoring) |
| `max_headlines` | `int` | `25` | Max headlines finales |
| `top_per_category` | `int` | `None` | Top N por categoría (diversidad) |
| `enable_clustering` | `bool` | `true` | Deduplicación semántica |
| `clustering_multiplier` | `int` | `2` | Cluster top N*multiplier |
| `model_ranker` | `str` | `gpt-4o-mini` | Modelo LLM |
| `force` | `bool` | `false` | Regenerar aunque exista ranking |

#### **Stage 04: Extract Content**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `max_articles` | `int` | `None` | Limitar a top N artículos |
| `force` | `bool` | `false` | Re-extraer contenido existente |
| `skip_paywall_check` | `bool` | `false` | Skip detección paywall |
| `timeout` | `int` | `30` | Timeout HTTP (segundos) |
| `min_word_count` | `int` | `100` | Mínimo palabras viables |
| `max_word_count` | `int` | `10000` | Máximo palabras |
| `model_paywall_validator` | `str` | `gpt-4o-mini` | Modelo validación paywall |
| `model_xpath_discovery` | `str` | `gpt-4o-mini` | Modelo descubrimiento XPath |
| `archive_wait_time` | `int` | `15` | Espera archive.today (segundos) |
| `max_retries` | `int` | `2` | Reintentos archive |

---

## Uso

### Comando Básico

```bash
venv/bin/python stages/orchestrator.py --config config/newsletters.yml
```

### Opciones

| Flag | Descripción |
|------|-------------|
| `--config PATH` | Path al YAML de configuración (requerido) |
| `--dry-run` | Muestra qué se ejecutaría sin correr nada |
| `--force-all` | Fuerza re-ejecución de todos los stages (override idempotency) |
| `--skip-stage-01` | Omite Stage 01 (asume URLs ya extraídas) |
| `--only-newsletter NAME` | Solo procesa una newsletter específica |
| `--debug` | Genera debug reports para todas las newsletters |
| `--resume [DATE\|ID]` | **v3.1** Continuar ejecución fallida (auto, fecha, o exec_id) |
| `--replay DATE\|ID` | **v3.1** Re-ejecutar con configuración original |
| `--exec-id ID` | **v3.1** Especificar execution_id (usar con --resume/--replay) |

### Ejemplos de Comandos

```bash
# 1. Ejecución completa
venv/bin/python stages/orchestrator.py --config config/newsletters.yml

# 2. Dry-run (validar config)
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --dry-run

# 3. Forzar regeneración completa
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --force-all

# 4. Solo una newsletter
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --only-newsletter tech_daily

# 5. Skip Stage 01 (URLs ya extraídas)
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --skip-stage-01
```

---

## Resume & Replay

> **Nuevo en v3.1:** Sistema de continuación y reproducción de ejecuciones.

El orchestrator ahora guarda automáticamente los parámetros de cada ejecución en la base de datos, permitiendo:

1. **Resume:** Continuar ejecuciones fallidas desde el último stage exitoso
2. **Replay:** Re-ejecutar newsletters completas con la configuración original

### Tabla `pipeline_executions`

Cada ejecución del orchestrator crea un registro en `pipeline_executions`:

| Campo | Descripción |
|-------|-------------|
| `id` | ID único de la ejecución |
| `newsletter_name` | Nombre de la newsletter |
| `run_date` | Fecha (YYYY-MM-DD) |
| `config_snapshot` | Configuración completa (JSON) |
| `status` | `running`, `completed`, `partial`, `failed` |
| `last_successful_stage` | Último stage que completó (1-5) |
| `created_at` | Timestamp de inicio |
| `completed_at` | Timestamp de fin |

### --resume: Continuar Ejecuciones Fallidas

Detecta automáticamente el último stage exitoso y continúa desde ahí, invalidando stages posteriores.

```bash
# 1. Resume última ejecución fallida (auto-detect)
venv/bin/python stages/orchestrator.py --resume

# 2. Resume ejecución específica por fecha
venv/bin/python stages/orchestrator.py --resume 2025-11-19

# 3. Resume por execution_id
venv/bin/python stages/orchestrator.py --resume --exec-id 42

# 4. Resume con dry-run (ver qué se ejecutaría)
venv/bin/python stages/orchestrator.py --resume --dry-run
```

**Comportamiento:**
- Busca la última ejecución con `status='failed'` o `status='partial'`
- Identifica el `last_successful_stage` (ej: Stage 02 completó, Stage 03 falló)
- Invalida stages >= `last_successful_stage + 1` (marca como `pending`)
- Re-ejecuta Stage 03 → 04 → 05 en secuencia
- Detiene si algún stage falla nuevamente

**Ejemplo:**

```bash
$ venv/bin/python stages/orchestrator.py --resume
================================================================================
RESUMING FAILED PIPELINE EXECUTION
================================================================================
Execution ID: 15
Newsletter: noticias_diarias
Date: 2025-11-19
Status: failed
Last successful stage: 2
================================================================================
Resuming execution 15 from stage 3
Invalidated 3 stages for re-execution
--------------------------------------------------------------------------------
STAGE 03: RANKER
--------------------------------------------------------------------------------
Executing: venv/bin/python stages/03_ranker.py ...
Stage 03 completed successfully
...
```

### --replay: Re-ejecutar con Configuración Original

Re-ejecuta TODO el pipeline (stages 02-05) con los parámetros exactos de una ejecución anterior.

```bash
# 1. Replay por execution_id
venv/bin/python stages/orchestrator.py --replay --exec-id 42

# 2. Replay última ejecución de una fecha
venv/bin/python stages/orchestrator.py --replay 2025-11-19

# 3. Replay con debug activado
venv/bin/python stages/orchestrator.py --replay --exec-id 42 --debug
```

**Comportamiento:**
- Recupera `config_snapshot` de la ejecución original
- Fuerza `--force-all` para sobrescribir datos existentes
- Ejecuta stages 02 → 03 → 04 → 05 completos
- Crea una NUEVA `pipeline_execution` con la config replicada

**Casos de uso:**
- Reproducir newsletter histórica con exactamente los mismos parámetros
- Debugging: ver si el problema persiste con la misma configuración
- Validar cambios: comparar output antes/después de un bugfix

### Consultar Ejecuciones en BD

```bash
# Ver todas las ejecuciones
sqlite3 data/news.db "
SELECT id, newsletter_name, run_date, status, last_successful_stage
FROM pipeline_executions
ORDER BY created_at DESC
LIMIT 10;
"

# Ver ejecuciones fallidas
sqlite3 data/news.db "
SELECT id, newsletter_name, run_date, status, last_successful_stage,
       datetime(created_at) as created
FROM pipeline_executions
WHERE status IN ('failed', 'partial')
ORDER BY created_at DESC;
"

# Ver configuración de una ejecución
sqlite3 data/news.db "
SELECT config_snapshot
FROM pipeline_executions
WHERE id = 42;
" | jq .

# Ver stages de una ejecución
sqlite3 data/news.db "
SELECT stage, status, error_message,
       datetime(started_at) as started,
       datetime(completed_at) as completed
FROM pipeline_runs
WHERE execution_id = 42
ORDER BY stage;
"
```

### Migración a v3.1

Si ya tienes una base de datos existente, ejecuta:

```bash
venv/bin/python scripts/migrate_add_executions.py
```

Esto crea:
- Tabla `pipeline_executions`
- Columna `execution_id` en `pipeline_runs`
- Índices para búsqueda rápida

---

## Tracking de Estado

### Consultar Estado en BD

```python
from common.db import SQLiteURLDatabase

db = SQLiteURLDatabase("data/news.db")

# Ver estado de una newsletter
status = db.get_pipeline_run_status(
    newsletter_name="tech_daily",
    run_date="2025-11-13",
    stage=3
)

print(status)
# {
#   'id': 42,
#   'status': 'completed',
#   'output_file': 'data/processed/ranked_2025-11-13_*.json',
#   'started_at': '2025-11-13T10:00:00',
#   'completed_at': '2025-11-13T10:05:23'
# }
```

### Ver Logs

Los logs se guardan por fecha:

```bash
# Ver log del orchestrator
cat logs/2025-11-13/orchestrator.log

# Ver logs de stages individuales
cat logs/2025-11-13/02_filter_for_newsletters.log
cat logs/2025-11-13/03_ranker.log
```

---

## Gestión de Errores

### Comportamiento ante Errores

1. **Error en Stage 01**: Continúa con otras fechas
2. **Error en Stage 02**: Detiene newsletter actual, continúa con siguiente
3. **Error en Stage 03**: Detiene newsletter actual, continúa con siguiente
4. **Error en Stage 04**: Detiene newsletter actual, continúa con siguiente

### Ejemplo de Output con Errores

```
================================================================================
ORCHESTRATOR SUMMARY
================================================================================
Total newsletters processed: 3

tech_daily:
  Stage 2: completed
  Stage 3: completed
    Output: data/processed/ranked_2025-11-13_120534_level_scoring_top25_all_cluster2x.json
  Stage 4: failed
    Error: Stage 04 failed with exit code 1

finance_weekly:
  Stage 2: completed
  Stage 3: completed
  Stage 4: completed

general_morning:
  ERROR: Unexpected error processing newsletter: ...
```

---

## Ejemplos

### Ejemplo 1: Newsletter Tech Diaria

**Config:**

```yaml
newsletters:
  - name: "tech_daily"
    date: "2025-11-13"

    stage02:
      categories: ["Tecnología", "IA", "Ciencia"]
      force: false

    stage03:
      ranker_method: "level_scoring"
      max_headlines: 20
      enable_clustering: true
      force: false

    stage04:
      max_articles: 10
      force: false
```

**Ejecución:**

```bash
venv/bin/python stages/orchestrator.py --config config/tech_daily.yml
```

**Resultado:**
- Stage 01: Extrae URLs de 2025-11-13
- Stage 02: Clasifica solo URLs nuevas en categorías Tech/IA/Ciencia
- Stage 03: Rankea con level_scoring, genera `ranked_2025-11-13_*.json`
- Stage 04: Extrae contenido de top 10 artículos

---

### Ejemplo 2: Múltiples Newsletters con Parámetros Diferentes

**Config:**

```yaml
newsletters:
  - name: "morning_brief"
    date: "2025-11-13"
    sources: ["ft", "bbc", "economist"]

    stage02:
      no_temporality: true
      force: false

    stage03:
      max_headlines: 15
      top_per_category: 3  # Diversidad
      force: false

    stage04:
      max_articles: 10

  - name: "tech_deep_dive"
    date: "2025-11-13"

    stage02:
      categories: ["Tecnología"]
      force: false

    stage03:
      ranker_method: "recursive"
      max_headlines: 25
      force: false

    stage04:
      max_articles: 20
      timeout: 60  # Más tiempo para artículos largos
```

**Ejecución:**

```bash
venv/bin/python stages/orchestrator.py --config config/multi.yml
```

**Resultado:**
- Stage 01 se ejecuta **una vez** para 2025-11-13
- `morning_brief`: 15 headlines (3 por categoría), fuentes premium
- `tech_deep_dive`: 25 headlines tech, ranking recursivo, 20 artículos

---

## Troubleshooting

### Problema: "No URLs found for specified criteria"

**Causa:** Stage 02 no encuentra URLs para clasificar.

**Soluciones:**
1. Verificar que Stage 01 completó correctamente
2. Revisar filtros de `sources` y `categories`
3. Verificar fecha en config

```bash
# Verificar Stage 01
sqlite3 data/news.db "SELECT COUNT(*) FROM urls WHERE date(extracted_at) = '2025-11-13' AND content_type = 'contenido'"
```

---

### Problema: "Ranking file already exists"

**Causa:** Stage 03 encontró ranking existente (idempotencia).

**Soluciones:**
1. Usar `--force-all` para regenerar
2. Añadir `force: true` en `stage03` del YAML
3. Borrar archivo ranked existente manualmente

```bash
# Ver rankings existentes
ls -lh data/processed/ranked_2025-11-13_*

# Forzar regeneración
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --force-all
```

---

### Problema: Stage 04 falla con timeout

**Causa:** Extracción toma más tiempo del configurado.

**Soluciones:**
1. Aumentar `timeout` en `stage04`
2. Reducir `max_articles`

```yaml
stage04:
  timeout: 60  # Aumentar a 60s
  max_articles: 5  # Reducir cantidad
```

---

### Problema: Newsletter se salta stages

**Causa:** URLs ya procesadas (idempotencia).

**Soluciones:**
1. Verificar estado en `pipeline_runs`
2. Usar `--force-all` si necesitas reprocesar

```python
# Verificar estado
from common.db import SQLiteURLDatabase
db = SQLiteURLDatabase()

status = db.get_pipeline_run_status("tech_daily", "2025-11-13", 2)
print(status)
```

---

## Resumen de Comandos Útiles

```bash
# Ejecución normal
venv/bin/python stages/orchestrator.py --config config/newsletters.yml

# Validar configuración (dry-run)
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --dry-run

# Forzar regeneración
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --force-all

# Solo una newsletter
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --only-newsletter tech_daily

# Skip Stage 01
venv/bin/python stages/orchestrator.py --config config/newsletters.yml --skip-stage-01

# Ver logs
cat logs/2025-11-13/orchestrator.log

# Ver estado en BD
sqlite3 data/news.db "SELECT * FROM pipeline_runs WHERE newsletter_name = 'tech_daily' ORDER BY created_at DESC LIMIT 10"
```

---

## Próximos Pasos

- [ ] Añadir Stage 05 al orchestrator (generación de newsletters)
- [ ] Implementar retry automático con backoff
- [ ] Añadir notificaciones (email/Slack) cuando pipeline completa
- [ ] Dashboard web para visualizar estado de pipelines
- [ ] Programación con cron para ejecución diaria automática

---

**Última actualización:** 2025-11-13
**Versión:** 1.0
