# Stage 02: Filter for Newsletters

## Descripción

Clasifica URLs en categorías temáticas y temporalidad para preparar la generación de newsletters personalizadas.

**Estado:** ✅ COMPLETADO E IMPLEMENTADO

---

## Tecnologías

- **LLM Batch Classification:** OpenAI API para clasificación masiva
- **SQLite:** Query y update in-place de base de datos
- **7 Categorías Consolidadas:** Sistema simplificado para mejor consistencia

---

## Proceso Detallado

### 1. Query de URLs por Fecha/Hora
- Filtra URLs de base de datos por `extracted_at` en rango especificado
- Filtra solo `content_type = 'contenido'` (descarta auxiliares)
- Soporte para rango de tiempo personalizable (no solo día completo)

### 2. Filtrado Opcional por Fuentes
- Puede filtrar por fuentes específicas antes de clasificar
- Ejemplo: solo procesar BBC, FT, El Confidencial

### 3. Clasificación Temática (Batch)
- **7 categorías consolidadas:**
  - `politica`: Política nacional, gobierno, justicia, educación
  - `economia`: Economía, finanzas, empresas, mercados, energía
  - `tecnologia`: Tecnología, ciencia, salud, medioambiente
  - `geopolitica`: Relaciones internacionales, conflictos
  - `sociedad`: Lifestyle, cultura, moda, entretenimiento, opinión
  - `deportes`: Deportes, competiciones
  - `otros`: Contenido inclasificable

- **Batch processing:** 30 URLs por llamada LLM (configurable)
- **Prompts con definiciones:** Cada categoría tiene definición detallada y ejemplos

### 4. Clasificación de Temporalidad (Opcional)
- **`temporal`:** Noticias sensibles al tiempo (eventos, breaking news)
- **`atemporal`:** Contenido intemporal (análisis, ensayos, reflexiones)
- Activable con `--no-temporality` flag (default: activo)

### 5. Update In-Place en SQLite
- Actualiza columnas:
  - `categoria_tematica`
  - `content_subtype` (temporal/atemporal)
  - `categorized_at` (timestamp de clasificación)
- No genera archivos intermedios

### 6. Post-Classification Filtering
- Puede filtrar por categorías objetivo después de clasificar
- Ejemplo: solo devolver política + economía

---

## Schema SQLite (Columnas Añadidas)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `categoria_tematica` | TEXT | Categoría temática (de `categories.yml`) |
| `content_subtype` | TEXT | `temporal` \| `atemporal` \| `NULL` |
| `categorized_at` | TIMESTAMP | Timestamp de clasificación |

**Índices nuevos:**
- `idx_categoria_tematica`: Para queries por categoría
- `idx_categorized_at`: Para queries por fecha de clasificación

---

## Configuración

### Variables .env

```env
# Modelo para clasificación
MODEL_CLASSIFIER=gpt-4o-mini

# Batch size para LLM
STAGE02_BATCH_SIZE=30

# Database path
DB_PATH=./data/news.db
```

---

## Ejecución

```bash
# Clasificar todas las URLs del día (00:00 a 23:59)
venv/bin/python stages/02_filter_for_newsletters.py --date 2025-11-10

# Rango de tiempo específico
venv/bin/python stages/02_filter_for_newsletters.py \
  --start "2025-11-10T08:00:00" \
  --end "2025-11-10T20:00:00"

# Filtrar por fuentes específicas
venv/bin/python stages/02_filter_for_newsletters.py \
  --date 2025-11-10 \
  --sources ft bbc elconfidencial

# Filtrar por categorías objetivo (post-clasificación)
venv/bin/python stages/02_filter_for_newsletters.py \
  --date 2025-11-10 \
  --categories politica economia tecnologia

# Solo clasificación temática (sin temporalidad, más rápido)
venv/bin/python stages/02_filter_for_newsletters.py \
  --date 2025-11-10 \
  --no-temporality

# Verbose logging
venv/bin/python stages/02_filter_for_newsletters.py \
  --date 2025-11-10 \
  --verbose
```

---

## Output

### Database Update
- Base de datos actualizada con nuevas columnas
- No genera archivos intermedios

### Logs
- **Path:** `logs/YYYY-MM-DD/02_filter_for_newsletters.log`
- Métricas de clasificación
- Token usage tracking

### Summary Output Ejemplo

```
STAGE 02 SUMMARY
================================================================================
Total content URLs retrieved: 450
URLs classified: 450
URLs after category filter: 450

Categories breakdown (7 categorías consolidadas):
  sociedad: 150      # lifestyle, cultura, entretenimiento, opinión
  politica: 110      # política nacional, gobierno, justicia, educación
  economia: 85       # economía, finanzas, empresas, mercados, energía
  tecnologia: 60     # tecnología, ciencia, salud, medioambiente
  geopolitica: 30    # relaciones internacionales
  deportes: 25       # deportes
  otros: 5           # contenido inclasificable

Temporality breakdown:
  temporal: 380
  atemporal: 70

Ready for Stage 03: 450 URL IDs
================================================================================
```

---

## Características Clave

### Batch Processing
- **30 URLs/llamada:** Reduce latencia y costo
- **Prompt optimizado:** Definiciones + ejemplos en contexto
- **Parsing robusto:** Manejo de errores en respuestas LLM

### Flexible Time Ranges
- No limitado a días completos (00:00-23:59)
- Soporta rangos de hora específicos
- Útil para análisis de franjas horarias

### Post-Classification Filtering
- Clasificar TODO primero
- Filtrar por categorías después
- Útil para newsletters temáticas

### Idempotente
- Re-ejecutar reclasifica URLs
- Actualiza `categorized_at` con nuevo timestamp
- No duplica registros

---

## Sistema de 7 Categorías

### Migración de 19 a 7 Categorías

**Fecha:** 2025-11-12

**Razón:** Mejorar consistencia de clasificación LLM

**Mapeo:**
- `politica`, `nacional`, `justicia`, `educacion` → **politica**
- `economia`, `empresas`, `mercados`, `energia` → **economia**
- `tecnologia`, `ciencia`, `salud`, `medioambiente` → **tecnologia**
- `internacional` → **geopolitica**
- `sociedad`, `cultura`, `entretenimiento`, `opinion` → **sociedad**
- `deportes` → **deportes** (sin cambios)
- Sin categoría → **otros**

**Script de migración:** `scripts/migrate_categories.py`

---

## Diferencias vs Diseño Original

| Aspecto | Diseño Original | Implementación Actual |
|---------|----------------|----------------------|
| Output | CSV intermedio | Update in-place en SQLite |
| Time ranges | Solo días completos | Rangos de hora personalizables |
| Categorías | 19 categorías | 7 categorías consolidadas |
| Filtering | Pre-classification solo | Pre + post classification |
| Temporalidad | No implementada | Clasificación temporal/atemporal |
| Batch size | No especificado | 30 URLs/llamada (configurable) |

---

## Próximos Pasos

**Stage 03 (Ranker):** Usa URLs clasificadas para ranking temático y selección de top headlines.

---

**Última actualización:** 2025-11-13
**Versión:** 1.0.0
**Estado:** Producción ✅
