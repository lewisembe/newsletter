# Stage 03: Ranker

## Descripción

Rankea URLs clasificadas usando LLM para generar una lista ordenada de los titulares más relevantes según criterio editorial.

**Estado:** ✅ COMPLETADO E IMPLEMENTADO

---

## Métodos Disponibles

### 1. Level Scoring (RECOMENDADO) ⭐
- Clasificación por niveles de relevancia absoluta
- **94% reducción de costo** vs recursive
- **96% menos llamadas LLM** (260 → 8)
- **5x más rápido** (120s → 25s)

### 2. Recursive Ranking (Original)
- Ranking recursivo con clustering semántico
- Útil para validación de calidad
- Mayor costo pero con agrupación de eventos relacionados

---

## Método 1: Level Scoring (RECOMENDADO)

### Proceso Detallado

#### PASO 1: Clasificación por Niveles
- **Batch LLM:** 60 URLs por llamada
- **5 niveles de relevancia:**
  - **Nivel 5:** Máxima relevancia - Crucial
  - **Nivel 4:** Alta relevancia - Contexto completo
  - **Nivel 3:** Relevancia media - Interesante
  - **Nivel 2:** Relevancia baja - Opcional
  - **Nivel 1:** Mínima relevancia - Prescindible

- **Criterio absoluto:** NO forzar distribución
- **Prompt:** "El lector solo leerá lo que selecciones, no debe perderse nada importante"

#### PASO 2: Extracción Top-X
- Extraer URLs clasificadas como Nivel 5
- Si >X URLs nivel 5 → LLM re-rank para seleccionar exactamente top X
- Criterio: "El lector SOLO leerá estos X, debe captar lo esencial del día"

#### PASO 3: Redistribución Equilibrada
- Remaining URLs (N-X) → redistribuir en 4 niveles (4,3,2,1)
- Split en percentiles equilibrados (25% cada nivel)
- Sort por nivel original antes de redistribuir

#### PASO 4: Sorting Heurístico
- Dentro de cada nivel, ordenar por:
  - **Primary:** Recency (`extracted_at` DESC)
  - **Secondary:** Source authority (FT > BBC > Economist > ...)
  - **Tertiary:** Original level
- Output final: Level 5 → 4 → 3 → 2 → 1

#### PASO 5: Clustering Semántico (OPCIONAL)
- Si `RANKER_ENABLE_CLUSTERING=true`
- Clustering solo sobre top 2*N URLs (ej: top 50 si N=25)
- Identifica artículos que cubren el MISMO evento específico
- Agrupa en clusters: artículo principal + related_articles
- Selecciona artículo más reciente como representante
- Output final: top N clusters con artículos relacionados adjuntos

### Configuración

```env
# Method Selection
RANKER_METHOD=level_scoring

# Level Scoring Config
RANKER_SCORING_MODE=top_x_absolute
RANKER_TOP_X=25
RANKER_SCORING_LEVELS=5
RANKER_SCORING_BATCH_SIZE=60
RANKER_TIEBREAK_BY_RECENCY=true
RANKER_TIEBREAK_BY_SOURCE=true
RANKER_TIEBREAK_SOURCES_ORDER=ft.com,bbc.com,economist.com,elpais.com

# Clustering (OPTIONAL)
RANKER_ENABLE_CLUSTERING=true
RANKER_CLUSTERING_MULTIPLIER=2

# General
MODEL_RANKER=gpt-4o-mini
MAX_HEADLINES=25
RANKER_TEMPERATURE=0.3
```

### Performance Metrics

```
Input URLs: 433
LLM calls: 8
Total tokens: 29,061 (23K input + 6K output)
Cost: $0.0069 USD
Latency: ~25 seconds

vs Recursive method:
- 96.9% less LLM calls (260 → 8)
- 95.0% less tokens (585K → 29K)
- 94.3% cost reduction ($0.12 → $0.007)
- 79% faster (120s → 25s)
```

---

## Método 2: Recursive Ranking (Original)

### Proceso Detallado

#### 1. Query Database
- Filtrar URLs por fecha/hora
- Solo URLs con `categoria_tematica` (clasificadas en Stage 02)

#### 2. Clustering por Categoría
- Agrupar URLs por categoría temática
- Ranking recursivo dentro de cada categoría
- Seleccionar Top N por categoría

#### 3. Consolidación Global
- Aplicar ranking recursivo sobre tops de todas las categorías
- Seleccionar Top M final

#### 4. Deduplicación Técnica (Post-processing)
- Safety net: eliminar DB IDs duplicados
- Loggear warnings si se detectan

#### 5. Clustering Semántico
- LLM identifica artículos del MISMO evento específico
- Agrupa en clusters: primary + related articles
- Selecciona artículo más reciente como principal

### Algoritmo Recursivo

```
rank_recursive(urls, target_size):
  SI len(urls) <= BATCH_SIZE (30):
    # Caso base: ranking directo
    RETURN llm_rank_and_deduplicate(urls, target_size)

  SINO:
    # Caso recursivo: dividir, rankear, consolidar
    batches = dividir_en_batches(urls, BATCH_SIZE)

    ranked_batches = []
    PARA CADA batch:
      top = llm_rank_and_deduplicate(batch, TOP_PER_BATCH)
      ranked_batches.append(top)

    consolidated = flatten(ranked_batches)
    RETURN rank_recursive(consolidated, target_size)
```

### Configuración

```env
# Method Selection
RANKER_METHOD=recursive

# Recursive Config
STAGE03_BATCH_SIZE=30
STAGE03_TOP_PER_BATCH=10
STAGE03_TOP_PER_CATEGORY=8

# Clustering
RANKER_ENABLE_CLUSTERING=true
RANKER_USE_TIMESTAMPS=true

# General
MODEL_RANKER=gpt-4o-mini
MAX_HEADLINES=25
RANKER_TEMPERATURE=0.3
```

---

## Output

### JSON Único: `data/processed/ranked_YYYY-MM-DD.json`

```json
{
  "run_date": "2025-11-10",
  "generated_at": "2025-11-13T10:29:42+00:00",
  "total_primary": 25,
  "total_related": 0,
  "ranking_method": "level_scoring",
  "config": {
    "scoring_mode": "top_x_absolute",
    "top_x": 25,
    "scoring_levels": 5
  },
  "ranked_urls": [
    {
      "rank": 1,
      "id": 801,
      "url": "https://...",
      "title": "Fight fake news, defeat climate deniers - Lula",
      "categoria_tematica": "geopolitica",
      "source": "bbc.com",
      "extracted_at": "2025-11-10T18:06:45Z",
      "score": 100,
      "reason": "Nivel de relevancia: 5",
      "related_articles": []
    }
  ]
}
```

---

## Ejecución

```bash
# Método por defecto (level_scoring configurado en .env)
venv/bin/python stages/03_ranker.py --date 2025-11-10

# Especificar límite custom
venv/bin/python stages/03_ranker.py --date 2025-11-10 --max-headlines 50

# Filtrar por categorías
venv/bin/python stages/03_ranker.py --date 2025-11-10 --categories politica economia

# Desactivar clustering
RANKER_ENABLE_CLUSTERING=false venv/bin/python stages/03_ranker.py --date 2025-11-10

# Rango de tiempo específico
venv/bin/python stages/03_ranker.py --start "2025-11-10T08:00" --end "2025-11-10T20:00"

# Verbose logging
venv/bin/python stages/03_ranker.py --date 2025-11-10 --verbose
```

---

## Características Clave

### Level Scoring
- **Criterio absoluto:** No forzar distribución en niveles
- **Top-X garantizado:** Extracción exacta de N titulares más relevantes
- **Redistribución equilibrada:** Resto de URLs distribuidas uniformemente
- **Sorting heurístico:** Recency + source authority
- **Ultra eficiente:** 94% reducción de costo vs recursive

### Recursive Ranking
- **Divide and conquer:** Maneja listas grandes sin JSONs rotos
- **Deduplicación multi-capa:** Técnica + semántica
- **Clustering semántico:** Agrupa eventos relacionados
- **Timestamp-based selection:** Artículo más reciente como principal

### Clustering Semántico (Ambos Métodos)
- Identifica artículos del MISMO evento específico
- Agrupa en clusters con representante principal
- Preserva artículos relacionados en campo `related_articles`
- Evita duplicación temática en lista final

---

## Bug Fix: Deduplicación en Clustering

**Fecha:** 2025-11-13

**Problema:** LLM devolvía IDs duplicados causando expansión de clusters (30 URLs → 55 clusters)

**Solución:** Implementado sistema de tracking con `processed_ids` set

**Ubicación:** `stages/03_ranker.py:268-369`

**Resultado:** Clustering correcto (50 URLs → 50 clusters ✅)

---

## Diferencias vs Diseño Original

| Aspecto | Diseño Original | Implementación Actual |
|---------|----------------|----------------------|
| Método | Solo recursive | Level scoring (nuevo) + recursive |
| Costo | $0.12 USD/run | $0.007 USD/run (level scoring) |
| Llamadas LLM | ~260 | 8 (level scoring) |
| Velocidad | 120s | 25s (level scoring) |
| Output | CSV doble lista | JSON único con related_articles |
| Clustering | No implementado | Opcional en ambos métodos |
| Deduplicación | Solo técnica | Técnica + semántica |

---

## Troubleshooting

### Clustering expansion bug
```bash
# Síntoma: N URLs → >N clusters
# Verificar que fix esté implementado (stages/03_ranker.py:268-369)
# Logs deberían mostrar "Convergence reached"
```

### Alto consumo de tokens
```bash
# Cambiar a level_scoring si usas recursive
RANKER_METHOD=level_scoring venv/bin/python stages/03_ranker.py --date 2025-11-10
```

### JSONs rotos en recursive
```bash
# Reducir batch size
STAGE03_BATCH_SIZE=20 venv/bin/python stages/03_ranker.py --date 2025-11-10
```

---

## Próximos Pasos

**Stage 04 (Extract Content):** Extracción de contenido completo de URLs rankeadas.

---

**Última actualización:** 2025-11-13
**Versión:** 1.0.0 (con level scoring + clustering fix)
**Estado:** Producción ✅
