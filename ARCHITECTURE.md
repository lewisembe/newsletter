# Newsletter Bot - Arquitectura del Sistema 🏗️

## Visión General

El Newsletter Bot está diseñado usando una **arquitectura modular basada en stages independientes**. Cada stage es completamente autónomo, testeable y puede ser mejorado sin afectar a los demás.

## Filosofía de Diseño

### Principios Clave

1. **Separación de Responsabilidades**: Cada stage tiene una única responsabilidad bien definida
2. **Independencia**: Los stages no dependen entre sí directamente, solo a través de contratos de datos
3. **Testabilidad**: Cada stage puede ser probado de forma aislada con datos mock
4. **Validación**: Cada stage valida su entrada y salida
5. **Transparencia**: Logs detallados en cada etapa para debugging

### Ventajas de esta Arquitectura

- ✅ **Fácil de mantener**: Cambios en un stage no afectan otros
- ✅ **Fácil de testear**: Test unitarios por stage
- ✅ **Fácil de mejorar**: Focus en optimizar stages individuales
- ✅ **Fácil de debuggear**: Identifica exactamente dónde falla el pipeline
- ✅ **Escalable**: Agregar nuevos stages o modificar el orden fácilmente

---

## Pipeline de 7 Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                      NEWSLETTER BOT PIPELINE                     │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │   STAGE 1:       │
  │ Source Loading   │  → Carga fuentes y temas desde Google Sheets
  └────────┬─────────┘
           │ sources[], topics[]
           ↓
  ┌──────────────────┐
  │   STAGE 2:       │
  │ News Fetching    │  → Obtiene artículos de RSS y web crawling
  └────────┬─────────┘
           │ raw_articles[]
           ↓
  ┌──────────────────┐
  │   STAGE 3:       │
  │   Content        │  → Procesa, limpia, crea archive links
  │  Processing      │
  └────────┬─────────┘
           │ processed_articles[]
           ↓
  ┌──────────────────┐
  │   STAGE 4:       │
  │ Deduplication    │  → Filtra artículos duplicados
  └────────┬─────────┘
           │ unique_articles[]
           ↓
  ┌──────────────────┐
  │   STAGE 5:       │
  │ Classification   │  → Clasifica por tema con OpenAI
  └────────┬─────────┘
           │ classified_articles[]
           ↓
  ┌──────────────────┐
  │   STAGE 6:       │
  │   Newsletter     │  → Genera newsletter con OpenAI
  │   Generation     │
  └────────┬─────────┘
           │ newsletter_content
           ↓
  ┌──────────────────┐
  │   STAGE 7:       │
  │  Persistence     │  → Guarda todo en Google Sheets
  └──────────────────┘
```

---

## Descripción Detallada de Cada Stage

### STAGE 1: Source Loading

**Archivo**: `stages/stage1_source_loading.py`

**Propósito**: Cargar fuentes de noticias activas y temas predefinidos desde Google Sheets.

**Input**:
- Conexión a Google Sheets (via `GoogleSheetsClient`)

**Output**:
```python
{
    'sources': [
        {
            'nombre': 'Financial Times',
            'url': 'https://www.ft.com/rss/home',
            'tipo': 'rss',
            'activo': 'si'
        },
        ...
    ],
    'topics': ['Economía y Finanzas', 'Tecnología', ...],
    'topic_details': [...],
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ Al menos una fuente activa
- ✓ Al menos un tema
- ✓ Estructura correcta de fuentes

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage1_source_loading
```

**Mejoras Potenciales**:
- [ ] Caché de fuentes para reducir llamadas a Google Sheets
- [ ] Validación de URLs de fuentes
- [ ] Priorización de fuentes

---

### STAGE 2: News Fetching

**Archivo**: `stages/stage2_news_fetching.py`

**Propósito**: Obtener artículos desde todas las fuentes configuradas (RSS y web crawling).

**Input**:
```python
sources = [...]  # De Stage 1
```

**Output**:
```python
{
    'articles': [
        {
            'title': 'Article Title',
            'url': 'https://...',
            'source': 'Financial Times',
            'published_date': '2025-11-05',
            'summary': '...',
            'content': '...'
        },
        ...
    ],
    'articles_by_source': {'Financial Times': [...]},
    'total_articles': 15,
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ Lista de artículos válida
- ✓ Cada artículo tiene título, URL y fuente

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage2_news_fetching
```

**Mejoras Potenciales**:
- [ ] Paralelizar fetching de múltiples fuentes
- [ ] Mejorar detección de fechas en crawling
- [ ] Agregar soporte para APIs de noticias
- [ ] Rate limiting más sofisticado
- [ ] Caché de artículos ya fetcheados

---

### STAGE 3: Content Processing

**Archivo**: `stages/stage3_content_processing.py`

**Propósito**: Procesar y limpiar contenido, crear archive links, generar hashes.

**Input**:
```python
articles = [...]  # De Stage 2
```

**Output**:
```python
{
    'processed_articles': [
        {
            'title': '...',
            'url': '...',
            'source': '...',
            'content': 'Full cleaned content',
            'content_truncated': 'First 1000 tokens',
            'content_length': 5000,
            'url_sin_paywall': 'https://archive.ph/...',
            'hash_contenido': 'abc123...',
            'published_date': '...'
        },
        ...
    ],
    'total_processed': 15,
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ Todos los artículos procesados tienen contenido
- ✓ Archive links creados
- ✓ Hashes generados

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage3_content_processing
```

**Mejoras Potenciales**:
- [ ] Mejorar extracción de fechas (usar más patrones)
- [ ] Probar diferentes servicios de archive
- [ ] Optimizar truncado de contenido (por oraciones completas)
- [ ] Extraer imágenes y metadatos adicionales
- [ ] Detección automática de idioma

---

### STAGE 4: Deduplication

**Archivo**: `stages/stage4_deduplication.py`

**Propósito**: Filtrar artículos duplicados comparando con el historial.

**Input**:
```python
articles = [...]  # De Stage 3
```

**Output**:
```python
{
    'unique_articles': [...],
    'duplicates_removed': 5,
    'total_input': 15,
    'total_output': 10,
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ total_input = total_output + duplicates_removed
- ✓ Sin duplicados en la salida

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage4_deduplication
```

**Mejoras Potenciales**:
- [ ] Usar embeddings para similaridad semántica
- [ ] Mejorar fuzzy matching de títulos
- [ ] Caché en memoria de hashes recientes
- [ ] Configurar umbral de similitud
- [ ] Detección de artículos actualizados vs duplicados

---

### STAGE 5: Classification

**Archivo**: `stages/stage5_classification.py`

**Propósito**: Clasificar artículos en temas predefinidos usando OpenAI.

**Input**:
```python
articles = [...]  # De Stage 4
topics = [...]    # De Stage 1
```

**Output**:
```python
{
    'classified_articles': [
        {
            ...  # Artículo original
            'tema': 'Economía y Finanzas'
        },
        ...
    ],
    'classification_stats': {
        'Economía y Finanzas': 5,
        'Tecnología': 3,
        ...
    },
    'total_classified': 10,
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ Todos los artículos tienen campo 'tema'
- ✓ Temas asignados están en la lista predefinida
- ✓ Estadísticas suman correctamente

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage5_classification
```

**Mejoras Potenciales**:
- [ ] Batch requests a OpenAI (varios artículos a la vez)
- [ ] Clasificación de respaldo con keywords si OpenAI falla
- [ ] Confianza de clasificación (score)
- [ ] Multi-etiquetado (un artículo en varios temas)
- [ ] Fine-tuning del modelo con ejemplos históricos

---

### STAGE 6: Newsletter Generation

**Archivo**: `stages/stage6_newsletter_generation.py`

**Propósito**: Generar newsletter elegante y narrativa con OpenAI.

**Input**:
```python
classified_articles = [...]  # De Stage 5
topics = [...]               # De Stage 1
```

**Output**:
```python
{
    'newsletter_content': '# Newsletter Title\n\n...',
    'word_count': 1500,
    'topics_covered': ['Economía', 'Tecnología'],
    'article_count': 10,
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ Newsletter generada tiene contenido
- ✓ Word count razonable

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage6_newsletter_generation
```

**Mejoras Potenciales**:
- [ ] Templates personalizables de newsletter
- [ ] Múltiples formatos (HTML, plain text, etc.)
- [ ] Generación de imágenes destacadas
- [ ] Resumen ejecutivo al inicio
- [ ] Links relacionados entre artículos
- [ ] Generación multiidioma

---

### STAGE 7: Persistence

**Archivo**: `stages/stage7_persistence.py`

**Propósito**: Guardar artículos procesados y newsletter en Google Sheets.

**Input**:
```python
classified_articles = [...]  # De Stage 5
newsletter_content = "..."   # De Stage 6
topics_covered = [...]
```

**Output**:
```python
{
    'articles_saved': 10,
    'newsletter_saved': True,
    'success': True,
    'error': None
}
```

**Validación**:
- ✓ Número correcto de artículos guardados
- ✓ Newsletter guardada si había contenido

**Testing Independiente**:
```bash
./venv/bin/python -m stages.stage7_persistence
```

**Mejoras Potenciales**:
- [ ] Guardar en múltiples destinos (DB, archivos, etc.)
- [ ] Versionado de newsletters
- [ ] Backup automático
- [ ] Exportación a otros formatos
- [ ] Webhooks para notificar cuando se guarda

---

## Flujo de Datos

### Contratos de Datos entre Stages

```python
# Stage 1 → Stage 2
sources: List[Dict[str, str]]

# Stage 2 → Stage 3
articles: List[Dict[str, Any]]
# Keys: title, url, source, published_date, summary, content

# Stage 3 → Stage 4
processed_articles: List[Dict[str, Any]]
# Keys: + content_truncated, url_sin_paywall, hash_contenido

# Stage 4 → Stage 5
unique_articles: List[Dict[str, Any]]
# Same as processed_articles

# Stage 5 → Stage 6
classified_articles: List[Dict[str, Any]]
# Keys: + tema

# Stage 6 → Stage 7
newsletter_content: str
topics_covered: List[str]
```

---

## Testing Individual de Stages

Cada stage puede ser testeado independientemente:

### Ejemplo: Testing Stage 3

```python
from stages.stage3_content_processing import ContentProcessingStage

# Mock articles
test_articles = [
    {
        'title': 'Test Article',
        'url': 'https://example.com/test',
        'source': 'Test Source',
        'content': 'Test content'
    }
]

# Initialize stage
stage = ContentProcessingStage()

# Execute
result = stage.execute(test_articles)

# Validate
assert result['success'] == True
assert len(result['processed_articles']) > 0
assert stage.validate_output(result)
```

---

## Debugging

### Activar Logs Detallados

```python
# En .env
LOG_LEVEL=DEBUG
```

### Ver Logs de un Stage Específico

```bash
tail -f logs/newsletter_bot.log | grep "stage3"
```

### Ejecutar Solo un Stage

```bash
# Stage 1
./venv/bin/python -m stages.stage1_source_loading

# Stage 2 con mock data
./venv/bin/python -m stages.stage2_news_fetching
```

---

## Extensibilidad

### Agregar un Nuevo Stage

1. Crear archivo en `stages/stageN_nombre.py`
2. Implementar clase `NombreStage` con:
   - `__init__(self, dependencies=None)`
   - `execute(self, input_data) -> Dict[str, Any]`
   - `validate_output(self, output) -> bool`
3. Agregar al pipeline en `main.py`
4. Documentar en este archivo

### Modificar un Stage Existente

1. Editar el stage individual
2. Mantener el contrato de entrada/salida
3. Actualizar validación si es necesario
4. Testear el stage aisladamente
5. Testear el pipeline completo

---

## Métricas y Monitoreo

Cada stage reporta:

- ✓ **Éxito/Fallo**: `success` boolean
- ✓ **Tiempo de ejecución**: Calculado automáticamente
- ✓ **Estadísticas**: Contadores específicos del stage
- ✓ **Errores**: Mensaje de error detallado

### Dashboard de Métricas (futuro)

```
PIPELINE METRICS
================
Stage 1: ✓ 0.5s  | 1 sources, 5 topics
Stage 2: ✓ 2.3s  | 15 articles fetched
Stage 3: ✓ 9.1s  | 15 processed
Stage 4: ✓ 0.2s  | 5 duplicates removed
Stage 5: ✓ 12.4s | 10 classified
Stage 6: ✓ 18.2s | 1500 words generated
Stage 7: ✓ 1.1s  | Data saved

Total: ✓ 43.8s
```

---

## Comparación: Antes vs Después

### Antes (Monolítico)

```python
class NewsletterPipeline:
    def run(self):
        # Todo mezclado en un método gigante
        sources = self.sheets.get_sources()
        articles = self.fetch_news(sources)
        # ... 200 líneas más
```

**Problemas:**
- ❌ Difícil de testear
- ❌ Difícil de debuggear
- ❌ Cambios riesgosos
- ❌ No reutilizable

### Después (Modular)

```python
class NewsletterPipeline:
    def run(self):
        stage1_result = self.stage1.execute()
        stage2_result = self.stage2.execute(stage1_result['sources'])
        stage3_result = self.stage3.execute(stage2_result['articles'])
        # ... cada stage independiente
```

**Ventajas:**
- ✅ Fácil de testear
- ✅ Fácil de debuggear
- ✅ Cambios seguros
- ✅ Reutilizable

---

## Conclusión

Esta arquitectura modular permite:

1. **Desarrollo iterativo**: Mejorar stages uno a la vez
2. **Testing robusto**: Test unitarios por stage
3. **Mantenimiento fácil**: Cambios aislados
4. **Escalabilidad**: Agregar stages sin romper nada
5. **Claridad**: Código auto-documentado

Para más detalles de implementación, ver los archivos individuales de cada stage.
