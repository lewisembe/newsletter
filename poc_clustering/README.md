# PoC: Clustering de Noticias Relacionadas

## Objetivo

Este Proof of Concept (PoC) implementa un sistema de clustering para agrupar noticias relacionadas sobre el mismo evento o historia, utilizando embeddings semánticos y búsqueda de similitud.

**Casos de uso:**
- Detectar noticias sobre el mismo evento cubiertas por distintos medios
- Identificar la evolución temporal de una historia (ej: anuncio → aprobación → controversia)
- Deduplicación inteligente de contenido

**Ejemplo:**
```
Cluster #ReformaFiscalSanchez:
  - "Sánchez anuncia nueva reforma fiscal" (El País, 08:23)
  - "El Gobierno presenta plan tributario" (ABC, 09:15)
  - "Hacienda aprueba cambios en IRPF" (El Confidencial, 10:42)
```

## Arquitectura

```
poc_clustering/
├── README.md                    # Este archivo
├── requirements.txt             # Dependencias Python
├── config.yml                   # Configuración
├── src/
│   ├── __init__.py
│   ├── embedder.py              # Generación de embeddings (multilingual-e5-small)
│   ├── cluster_manager.py       # Clustering con FAISS + threshold adaptativo
│   ├── hashtag_generator.py     # Generación de hashtags con LLM
│   └── db_loader.py             # Carga desde ../data/news.db
├── run_clustering.py            # Script principal
└── output/
    └── clustering_report_*.md   # Informes generados
```

## Tecnologías

- **Embeddings:** `intfloat/multilingual-e5-small` (100MB, 384 dims, multilingüe)
- **Búsqueda:** FAISS (Facebook AI Similarity Search) - índice vectorial
- **Clustering:** Threshold adaptativo (μ - k*σ) + Union-Find (DSU)
- **Hashtags:** GPT-4o-mini para síntesis

## Quick Start

### 1. Instalación

```bash
cd poc_clustering

# Crear entorno virtual (opcional pero recomendado)
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

**Nota:** La primera ejecución descargará el modelo de embeddings (~100MB).

### 2. Configuración

Editar `config.yml` si es necesario (valores por defecto están optimizados para Raspberry Pi 5).

```yaml
clustering:
  similarity_threshold: 0.75  # Ajustar según necesidad
  min_cluster_size: 2         # Mínimo artículos por cluster
```

### 3. Ejecución

```bash
# Clustering de noticias de hoy
python run_clustering.py

# Clustering de una fecha específica
python run_clustering.py --date 2025-11-17

# Filtrar por categoría
python run_clustering.py --date 2025-11-17 --category economia

# Modo verbose
python run_clustering.py --date 2025-11-17 --verbose
```

### 4. Ver resultados

```bash
cat output/clustering_report_2025-11-17.md
```

## Algoritmo de Clustering

### Paso 1: Generación de Embeddings
Cada titular se convierte en un vector de 384 dimensiones usando `multilingual-e5-small`.

### Paso 2: Índice FAISS
Los vectores se almacenan en un índice FAISS para búsqueda eficiente de vecinos más cercanos.

### Paso 3: Clustering Incremental
```
Para cada titular (en orden cronológico):
  1. Buscar vecino más cercano en el índice FAISS
  2. Calcular similitud coseno
  3. Si similitud > threshold adaptativo del cluster:
     → Añadir titular al cluster existente
  4. Si no:
     → Crear nuevo cluster
  5. Actualizar índice FAISS
```

### Paso 4: Threshold Adaptativo
Cada cluster tiene un threshold dinámico calculado como:
```
threshold = μ - k * σ
```
Donde:
- `μ` = similitud promedio dentro del cluster
- `σ` = desviación estándar
- `k` = factor configurable (default: 0.8)

**Ventaja:** Clusters densos (muy similares) requieren mayor similitud para añadir miembros. Clusters dispersos son más permisivos.

### Paso 5: Generación de Hashtags
Para cada cluster con ≥ 2 artículos:
- Seleccionar hasta 5 titulares representativos
- Enviar a GPT-4o-mini con prompt especializado
- Generar hashtag descriptivo (ej: `#ReformaFiscal`)

## Configuración Detallada

### `config.yml`

```yaml
database:
  path: ../data/news.db  # Ruta a la base de datos principal

model:
  name: intfloat/multilingual-e5-small
  cache_dir: ./models_cache
  batch_size: 100  # Ajustar según RAM disponible

clustering:
  similarity_threshold: 0.75     # Threshold base (0-1)
  adaptive_threshold: true       # Usar threshold adaptativo
  adaptive_k: 0.8                # Factor μ - k*σ
  min_cluster_size: 2            # Mínimo para incluir en reporte

hashtag:
  llm_model: gpt-4o-mini
  max_titles_for_context: 5
  temperature: 0.3

output:
  format: markdown
  include_metrics: true
  include_urls: true
```

## Output: Informe Markdown

El informe generado incluye:

1. **Resumen ejecutivo:** Estadísticas generales
2. **Clusters principales:** Detalle de cada agrupación
3. **Métricas de ejecución:** Tiempo, memoria, tokens consumidos
4. **Distribución:** Histograma de tamaños de clusters

Ejemplo:
```markdown
## 🎯 Clusters Principales

### Cluster #1: #ReformaFiscalSanchez
**Tamaño:** 12 artículos | **Similitud promedio:** 0.85

**Artículos:**
1. [El País] Sánchez anuncia nueva reforma fiscal...
2. [ABC] El Gobierno presenta su plan tributario...
...
```

## Rendimiento Esperado

**Raspberry Pi 5 (8GB RAM):**
- **Carga de modelo:** ~5 segundos (primera vez)
- **Embedding de 500 titulares:** ~10-15 segundos
- **Clustering:** ~2-3 segundos
- **Generación de hashtags:** ~3-5 segundos (depende de # clusters)
- **Total:** ~20-25 segundos para 500 artículos

**Memoria:**
- Modelo: ~200MB
- Embeddings (500 × 384): ~0.7MB
- FAISS índice: ~1MB
- **Peak:** ~300-400MB

## Validación Manual

Para evaluar la calidad del clustering:

1. Ejecutar con datos reales de 1 día
2. Revisar manualmente 10-15 clusters aleatorios
3. Verificar:
   - ✅ ¿Artículos del cluster hablan del mismo evento?
   - ✅ ¿Hashtag es descriptivo y relevante?
   - ❌ Detectar falsos positivos (artículos agrupados incorrectamente)
   - ❌ Detectar falsos negativos (artículos que deberían estar juntos)
4. Ajustar `similarity_threshold` en `config.yml` según resultados

## Troubleshooting

### Error: "No module named 'faiss'"
```bash
pip install faiss-cpu
```

### Error: "Model not found"
Verificar conexión a internet. El modelo se descarga automáticamente en la primera ejecución.

### Clustering demasiado agresivo (muchos artículos en pocos clusters)
Aumentar `similarity_threshold` en `config.yml`:
```yaml
clustering:
  similarity_threshold: 0.80  # Mayor = más estricto
```

### Clustering demasiado fragmentado (muchos clusters pequeños)
Reducir `similarity_threshold`:
```yaml
clustering:
  similarity_threshold: 0.70  # Menor = más permisivo
```

### Hashtags poco descriptivos
Aumentar `max_titles_for_context` para dar más contexto al LLM:
```yaml
hashtag:
  max_titles_for_context: 8  # Más contexto = mejor hashtag
```

## Próximos Pasos

Si el PoC demuestra buenos resultados:

1. **Integración en pipeline:** Crear Stage 3.5 (post-ranker, pre-content extraction)
2. **Persistencia:** Guardar clusters en base de datos (nueva tabla)
3. **Clustering incremental:** Añadir nuevos artículos sin recomputar todo
4. **Dashboard web:** Visualización interactiva de clusters
5. **API REST:** Endpoint para consultar clusters por fecha/categoría

## Estructura de Datos

### Input (desde news.db)
```python
{
  "id": 123,
  "url": "https://elpais.com/...",
  "title": "Sánchez anuncia nueva reforma fiscal",
  "source": "elpais.com",
  "extracted_at": "2025-11-17 08:23:15",
  "categoria_tematica": "economia"
}
```

### Output (informe markdown)
```markdown
### Cluster #1: #ReformaFiscalSanchez
**Tamaño:** 12 artículos | **Similitud promedio:** 0.85
...
```

## Dependencias

Ver `requirements.txt` para lista completa:
- `sentence-transformers` - Generación de embeddings
- `faiss-cpu` - Búsqueda de similitud vectorial
- `torch` - Backend para transformers
- `openai` - Generación de hashtags
- `pyyaml` - Configuración
- `python-dotenv` - Variables de entorno

## Licencia

Este PoC es parte del proyecto `newsletter_utils`. Ver LICENSE en la raíz del proyecto.

## Contacto

Para preguntas o sugerencias, consultar documentación del proyecto principal en `/CLAUDE.md`.
