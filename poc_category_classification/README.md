# PoC: Clasificación de Categorías con Embeddings

> **Versión:** 1.0 | **Estado:** ✅ Completo | **Fecha:** 2025-11-20

## 🎯 Objetivo

Proof of Concept (PoC) para evaluar el uso de **embeddings semánticos** en la clasificación de titulares por categorías temáticas, comparando su rendimiento con el método actual basado en **LLM (gpt-4o-mini)**.

**Preguntas clave a responder:**
- ¿Qué tan precisa es la clasificación con embeddings vs LLM?
- ¿Cuánto más rápida y económica es la alternativa con embeddings?
- ¿En qué categorías funciona mejor/peor?
- ¿Es viable integrar embeddings en el pipeline de producción?

## 🏗️ Arquitectura

```
poc_category_classification/
├── README.md                          # Este archivo
├── requirements.txt                   # Dependencias Python
├── config.yml                         # Configuración principal
├── run_classification.py              # Script principal (ejecutable)
├── src/
│   ├── __init__.py
│   ├── db_loader.py                   # Carga URLs clasificadas desde news.db
│   ├── category_classifier.py         # Clasificador basado en embeddings
│   └── comparison_analyzer.py         # Análisis y métricas de comparación
└── output/                            # Informes generados (Markdown + CSV)
```

**Dependencias externas:**
- `poc_clustering/src/embedder.py` - Reutiliza generador de embeddings

## 🚀 Quick Start

### 1. Setup

```bash
# Navegar al directorio del PoC
cd poc_category_classification

# Crear entorno virtual (opcional)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# NOTA: El modelo de embeddings se descargará automáticamente
# en la primera ejecución (~100MB) y se cachea en:
# ../poc_clustering/models_cache/
```

### 2. Configuración

Editar `config.yml` para ajustar parámetros:

```yaml
database:
  filters:
    max_urls: 200  # Limitar para test rápido (null = todas)

classification:
  method: cosine_similarity
  similarity_threshold: 0.5
  use_examples: true
  examples_per_category: 3

output:
  export_csv: true
  include_performance_comparison: true
```

### 3. Ejecución

```bash
# Ejecutar con configuración por defecto
./run_classification.py

# Especificar config custom
./run_classification.py --config mi_config.yml

# Especificar output path
./run_classification.py --output mi_informe.md
```

### 4. Resultados

El script genera dos archivos en `output/`:
- `classification_report_YYYYMMDD_HHMMSS.md` - Informe completo en Markdown
- `classification_report_YYYYMMDD_HHMMSS.csv` - Datos crudos en CSV

## 📊 Funcionamiento

### Flujo del PoC

```
1. CARGAR DATOS
   ├─ Leer URLs clasificadas desde news.db (ground truth LLM)
   └─ Aplicar filtros (fecha, categorías, límite)

2. INICIALIZAR MODELO
   ├─ Cargar modelo de embeddings (intfloat/multilingual-e5-small)
   └─ Generar embeddings de categorías (descripción + ejemplos)

3. CLASIFICAR
   ├─ Generar embeddings de titulares (batch)
   └─ Calcular similitud coseno con cada categoría

4. COMPARAR
   ├─ Contrastar predicciones con ground truth LLM
   └─ Calcular métricas (accuracy, precision, recall, F1)

5. ANALIZAR
   ├─ Matriz de confusión
   ├─ Patrones de errores
   └─ Estadísticas de confianza

6. REPORTAR
   └─ Generar informe Markdown + exportar CSV
```

### Método de Clasificación

**Embeddings de categorías:**
- Se generan embeddings para la **descripción** de cada categoría
- Opcionalmente se incluyen **ejemplos** (3 por defecto)
- Se combinan usando una estrategia (`mean`, `max`, `weighted_mean`)

**Clasificación de titulares:**
1. Generar embedding del titular
2. Calcular **similitud coseno** con cada categoría
3. Asignar categoría con mayor similitud
4. Si similitud < threshold → `otros`

**Ejemplo:**
```
Titular: "Banco Central sube tipos de interés al 4.5%"

Similitudes:
  economia:    0.892 ← GANADOR
  finanzas:    0.764
  politica:    0.612
  tecnologia:  0.301
  ...

Predicción: economia (confianza: 0.892)
Ground truth: economia
Resultado: ✓ CORRECTO
```

## 📈 Métricas Reportadas

### Métricas Globales
- **Accuracy:** % de clasificaciones correctas
- **Precision (macro):** Promedio de precisión por categoría
- **Recall (macro):** Promedio de recall por categoría
- **F1-Score (macro):** Media armónica de precision/recall

### Métricas por Categoría
- Precision, Recall, F1, Support para cada categoría individual

### Matriz de Confusión
- Tabla cruzada: verdadero vs predicho
- Identifica pares de categorías que se confunden frecuentemente

### Análisis de Errores
- Ejemplos concretos de clasificaciones incorrectas
- Patrones de confusión más frecuentes (ej: "economia → finanzas")
- Estadísticas de confianza (similarity scores) para correctos vs incorrectos

### Comparación de Rendimiento
- **Tiempo:** Embeddings vs LLM
- **Costo:** $0 (local) vs ~$0.02-0.04 (API)
- **Memoria:** Uso pico de RAM
- **Latencia:** Clasificación batch

## ⚙️ Configuración Detallada

### Database Filters

```yaml
database:
  path: ../data/news.db

  filters:
    # Solo URLs con categoría asignada (LLM ground truth)
    require_categoria: true

    # Rango de fechas (opcional)
    date_from: "2025-11-01"
    date_to: "2025-11-20"

    # Límite de URLs (null = todas)
    max_urls: 500

    # Filtrar categorías específicas (null = todas)
    categories_filter: ['economia', 'politica', 'tecnologia']
```

### Model Configuration

```yaml
model:
  # Modelo de HuggingFace
  name: intfloat/multilingual-e5-small

  # Cache compartido con poc_clustering
  cache_dir: ../poc_clustering/models_cache

  # Batch size (ajustar según RAM)
  batch_size: 100

  # Device: 'cpu' o 'cuda'
  device: cpu
```

**Modelos alternativos:**
- `intfloat/multilingual-e5-base` (768 dims, más preciso, más lento)
- `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- `hiiamsid/sentence_similarity_spanish_es`

### Classification Strategy

```yaml
classification:
  # Método: 'cosine_similarity', 'knn', 'threshold'
  method: cosine_similarity

  # K para KNN (si method = 'knn')
  knn_k: 5

  # Threshold mínimo de similitud
  similarity_threshold: 0.5

  # Usar ejemplos además de descripción
  use_examples: true

  # Número de ejemplos por categoría
  examples_per_category: 3

  # Estrategia de combinación de embeddings
  # Options: 'mean', 'max', 'weighted_mean'
  category_embedding_strategy: mean
```

**Recomendaciones:**
- `use_examples: true` + `strategy: mean` → Balance precisión/generalización
- `use_examples: false` → Más rápido, puede perder matices
- `strategy: weighted_mean` → Da más peso a la descripción vs ejemplos
- `threshold > 0.6` → Más estricto, más casos clasificados como "otros"

### Categories Configuration

```yaml
categories:
  # Path al archivo de categorías
  config_path: ../config/categories.yml

  # Categorías a excluir del análisis
  exclude: ['otros']
```

### Output Options

```yaml
output:
  format: markdown

  # Métricas detalladas por categoría
  include_per_category_metrics: true

  # Tabla de comparación LLM vs Embeddings
  include_comparison_table: true

  # Análisis de costos y latencia
  include_performance_comparison: true

  # Exportar CSV además de Markdown
  export_csv: true

  # Directorio de salida
  output_dir: ./output
```

## 🧪 Testing y Validación

### Test Básico

```bash
# Test rápido con subset pequeño
# Editar config.yml:
#   database.filters.max_urls: 50

./run_classification.py

# Revisar output/classification_report_*.md
```

### Test de Módulos Individuales

```bash
# Test DBLoader
cd src/
python db_loader.py

# Test CategoryClassifier
python category_classifier.py

# Test ComparisonAnalyzer
python comparison_analyzer.py
```

### Validación de Resultados

**Checklist:**
- [ ] Accuracy > 70% (mínimo aceptable)
- [ ] Precision/Recall balanceado (no sesgado a categorías mayoritarias)
- [ ] Confusión entre categorías similares es esperada (ej: economia ↔ finanzas)
- [ ] Confidencias altas para correctos, bajas para incorrectos
- [ ] Tiempo de ejecución < 30s para 200 URLs

## 📊 Ejemplo de Output

### Console Output

```
============================================================
PoC Category Classification - Embeddings vs LLM
============================================================

📄 Loading config: config.yml

📦 Step 1: Loading classified URLs from database...
  Total URLs in DB: 1247
  Classified URLs: 856
  Classification rate: 68.6%
  Loaded 200 URLs for analysis

  Category distribution:
    economia: 58
    politica: 42
    tecnologia: 31
    finanzas: 27
    geopolitica: 24
    sociedad: 12
    deportes: 6

🤖 Step 2: Loading embedding model...
Loading embedding model: intfloat/multilingual-e5-small
Model loaded. Embedding dimension: 384
  Model loaded in 2.3s

🎯 Step 3: Initializing category classifier...
Generating category embeddings...
  politica: 4 texts → embedding
  economia: 4 texts → embedding
  finanzas: 4 texts → embedding
  tecnologia: 4 texts → embedding
  geopolitica: 4 texts → embedding
  sociedad: 4 texts → embedding
  deportes: 4 texts → embedding
CategoryClassifier initialized with 7 categories
Method: cosine_similarity, Strategy: mean

🔍 Step 4: Classifying 200 URLs with embeddings...
100%|███████████████████████████████| 200/200 [00:01<00:00, 145.23it/s]
  Classification completed in 1.4s

📊 Step 5: Analyzing results...
Total samples: 200
Correct: 167 (83.5%)
Incorrect: 33 (16.5%)

Overall Metrics:
  Accuracy: 0.835
  Precision (macro): 0.812
  Recall (macro): 0.798
  F1 (macro): 0.804

📝 Step 6: Generating report...

✅ Informe generado: output/classification_report_20251120_143052.md
✅ CSV exported: output/classification_report_20251120_143052.csv

============================================================
✅ COMPLETED
Total execution time: 5.8s
Peak memory usage: 287.4 MB
============================================================
```

### Markdown Report (excerpt)

```markdown
# 📊 Informe de Clasificación por Categorías

**Método:** Embeddings vs LLM (ground truth)
**Modelo:** intfloat/multilingual-e5-small
**Generado:** 2025-11-20 14:30:52

---

## 📈 Resumen Ejecutivo

- **Total de URLs analizadas:** 200
- **Accuracy:** 83.50%
- **Precision (macro):** 0.812
- **Recall (macro):** 0.798
- **F1-Score (macro):** 0.804

- **Correctos:** 167 (83.5%)
- **Incorrectos:** 33 (16.5%)

---

## 📊 Métricas por Categoría

| Categoría | Precision | Recall | F1-Score | Support |
|-----------|-----------|--------|----------|---------|
| deportes     | 1.000 | 1.000 | 1.000 |    6 |
| economia     | 0.864 | 0.862 | 0.863 |   58 |
| finanzas     | 0.704 | 0.704 | 0.704 |   27 |
| geopolitica  | 0.875 | 0.875 | 0.875 |   24 |
| politica     | 0.750 | 0.810 | 0.779 |   42 |
| sociedad     | 0.833 | 0.833 | 0.833 |   12 |
| tecnologia   | 0.857 | 0.774 | 0.814 |   31 |

---

## ⚠️ Patrones de Confusión Más Frecuentes

- **politica → economia:** 5 casos
- **economia → finanzas:** 4 casos
- **finanzas → economia:** 3 casos
- **tecnologia → sociedad:** 2 casos
```

## 💡 Hallazgos Esperados

### Ventajas de Embeddings
✅ **Velocidad:** 5-10x más rápido que LLM (batch processing)
✅ **Costo:** $0 vs ~$0.02-0.04 por ejecución
✅ **Determinístico:** Mismo input → mismo output (reproducible)
✅ **Escalable:** Sin límites de API rate, sin tokens
✅ **Local:** No dependencia de servicios externos

### Desventajas de Embeddings
❌ **Precisión menor:** ~75-85% accuracy vs ~90-95% LLM
❌ **Confusión entre categorías similares:** economia ↔ finanzas, politica ↔ economia
❌ **Menos interpretable:** No "razonamiento" explícito
❌ **Requiere calibración:** Threshold y estrategia de embeddings
❌ **No maneja excepciones complejas:** LLM mejor para casos edge

### Categorías Críticas
- **Fáciles:** deportes, tecnologia (vocabulario distintivo)
- **Difíciles:** economia/finanzas, politica/economia (solapamiento semántico)
- **Problemáticas:** sociedad (muy amplia), otros (indefinida)

## 🔄 Próximos Pasos

### Mejoras Potenciales
- [ ] **Hybrid approach:** Embeddings para categorías fáciles, LLM para difíciles
- [ ] **Fine-tuning:** Entrenar clasificador supervisado con datos históricos
- [ ] **Ensemble:** Combinar embeddings + LLM con voting
- [ ] **Threshold dinámico:** Ajustar por categoría según distribución
- [ ] **Aumentar ejemplos:** Más ejemplos por categoría mejora separabilidad

### Integración en Pipeline
- [ ] **Stage 02 alternativo:** Opción `--use-embeddings` en `02_filter_for_newsletters.py`
- [ ] **Modo híbrido:** Embeddings primary, LLM fallback para confidencia baja
- [ ] **A/B testing:** Ejecutar ambos métodos en paralelo y comparar
- [ ] **Monitoring:** Dashboard para comparar métricas en producción

### Experimentos Adicionales
- [ ] **Modelos alternativos:** Probar `multilingual-e5-base` (768 dims)
- [ ] **Dimensionality reduction:** PCA/t-SNE para visualizar clusters
- [ ] **Category tuning:** Optimizar descripciones y ejemplos por categoría
- [ ] **Temporal analysis:** ¿Cambia accuracy con el tiempo?

## 🛠️ Troubleshooting

### Error: "Model not found"
```bash
# Descargar modelo manualmente
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', cache_folder='../poc_clustering/models_cache')"
```

### Error: "Database not found"
```bash
# Verificar path en config.yml
ls -la ../data/news.db

# O ajustar path absoluto
database:
  path: /home/user/newsletter_utils/data/news.db
```

### Memoria insuficiente (Raspberry Pi)
```yaml
# Reducir batch_size en config.yml
model:
  batch_size: 32  # En vez de 100

# O limitar dataset
database:
  filters:
    max_urls: 100
```

### Baja accuracy (<70%)
```yaml
# Ajustar configuración
classification:
  use_examples: true
  examples_per_category: 5  # Aumentar ejemplos
  category_embedding_strategy: weighted_mean

# O probar modelo más grande
model:
  name: intfloat/multilingual-e5-base
```

## 📚 Referencias

- **Modelo de embeddings:** [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- **sentence-transformers:** [Documentation](https://www.sbert.net/)
- **Semantic similarity:** [Cosine Similarity](https://en.wikipedia.org/wiki/Cosine_similarity)
- **Pipeline principal:** `../CLAUDE.md`
- **PoC Clustering:** `../poc_clustering/README.md`

## 📝 Changelog

- **2025-11-20:** v1.0 - Initial release

---

**Autor:** Generado automáticamente por Claude Code
**Licencia:** Mismo que proyecto principal
**Contacto:** Ver README principal del proyecto
