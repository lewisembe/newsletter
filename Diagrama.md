# Pipeline de Newsletter Automatizada

> Estado: diagrama histórico basado en SQLite y stages pendientes. El pipeline actual usa PostgreSQL y etapas 2-5 están implementadas vía orquestador/webapp. Mantener solo como referencia visual.

```
                ┌─────────────────────────────┐
                │     INICIO / ORQUESTADOR    │
                │  orchestrator.py (.env)     │
                │      (pendiente)            │
                └──────────────┬──────────────┘
                               │
                               ▼
               ┌──────────────────────────────┐
               │ STAGE 01: extract_urls       │
               │ Selenium + Regex + LLM       │
               │ • Lee sources.yml            │
               │ • Extrae URLs                │
               │ • Clasificación híbrida      │
               │   (regex 60-85% + LLM)       │
               │ • Upsert incremental         │
               │ • Output: SQLite (news.db)   │
               └──────────────┬───────────────┘
                               │
                               ▼
               ┌──────────────────────────────┐
               │ STAGE 02: filter_newsletters │
               │ LLM Batch Classification     │
               │ • Query por fecha/hora       │
               │ • Filtra content_type        │
               │ • Clasifica categorías       │
               │   temáticas (7 categorías)   │
               │ • Clasifica temporalidad     │
               │ • Update: categoria_tematica │
               └──────────────┬───────────────┘
                               │
                               ▼
               ┌──────────────────────────────┐
               │ STAGE 03: ranker             │
               │ LLM Level Scoring            │
               │ • Level scoring (5 niveles)  │
               │ • Top-X absoluto             │
               │ • Redistribución equilibrada │
               │ • Sorting heurístico         │
               │ • Clustering semántico (opt) │
               │ • Output: ranked_*.json      │
               └──────────────┬───────────────┘
                               │
                               ▼
               ┌──────────────────────────────┐
               │ STAGE 04: extract_content    │
               │      (pendiente)             │
               │ Selenium + Requests + LLM    │
               │ • Extrae contenido completo  │
               │ • Detecta paywalls           │
               │ • Fallback archive.today     │
               │ • Guarda contenido extraído  │
               └──────────────┬───────────────┘
                               │
                               ▼
               ┌──────────────────────────────┐
               │ STAGE 05: generate_newsletter│
               │      (pendiente)             │
               │ OpenAI (modelo writer)       │
               │ • Redacta HTML/Markdown      │
               │ • Output: newsletters/*.json │
               └──────────────┬───────────────┘
                               │
                               ▼
                ┌─────────────────────────────┐
                │   LOGS + RESULTADOS         │
                │   /logs/YYYY-MM-DD/*.log    │
                │   Idempotencia diaria       │
                └─────────────────────────────┘
```

---

## Arquitectura de Datos

### SQLite Database (data/news.db)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Tabla: urls                                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ id (PK) │ url (UNIQUE) │ title │ source │ content_type │ extracted_at  │
│ categoria_tematica │ content_subtype │ categorized_at │ created_at    │
├─────────────────────────────────────────────────────────────────────────┤
│ Stage 01: Inserta URLs con clasificación (regex + LLM)                 │
│ Stage 02: Actualiza categoria_tematica, content_subtype                │
│ Stage 03: Solo lee, no modifica (output a JSON)                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Output Files

- `data/processed/ranked_YYYY-MM-DD.json` (Stage 03)
- `data/processed/newsletters/*.json` (Stage 05, pendiente)

### Configuración

- `config/sources.yml` - Fuentes de noticias
- `config/categories.yml` - 7 categorías temáticas consolidadas
- `config/url_classification_rules.yml` - Reglas regex auto-generadas
- `config/cached_no_content_urls.yml` - Caché de URLs no-contenido
- `.env` - Credenciales y parámetros por stage

---

## Optimizaciones Implementadas

### Stage 01: Extract URLs
- **Clasificación híbrida:** 60-85% cobertura regex (sin consumir tokens)
- **Caché de URLs no-contenido:** lookup O(1)
- **Upsert incremental:** commit por fuente (no batch final)
- **Auto-generación de reglas:** para fuentes nuevas

### Stage 02: Filter Newsletters
- **Batch classification:** 30 URLs/llamada LLM
- **Sistema consolidado:** 7 categorías (vs 19 originales)
- **In-place update:** no CSVs intermedios

### Stage 03: Ranker
- **Level Scoring:** 94% reducción de costo vs recursive
- **96% menos llamadas LLM:** 260 → 8 llamadas
- **5x más rápido:** 120s → 25s
- **Clustering semántico opcional:** sobre top 2*N URLs

---

## Referencias

Para detalles de implementación, ver:
- `/stages/README_STAGE01.md` - Stage 01: Extract URLs
- `/stages/README_STAGE02.md` - Stage 02: Filter Newsletters
- `/stages/README_STAGE03.md` - Stage 03: Ranker
