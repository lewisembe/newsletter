# 📊 Informe de Clasificación por Categorías
**Método:** Embeddings vs LLM (ground truth)
**Modelo:** intfloat/multilingual-e5-small
**Generado:** 2025-11-20 16:06:57

---

## 📈 Resumen Ejecutivo

- **Total de URLs analizadas:** 100
- **Accuracy:** 59.00%
- **Precision (macro):** 0.484
- **Recall (macro):** 0.606
- **F1-Score (macro):** 0.476

- **Correctos:** 59 (59.0%)
- **Incorrectos:** 41 (41.0%)

---

## 📊 Métricas por Categoría

| Categoría | Precision | Recall | F1-Score | Support |
|-----------|-----------|--------|----------|---------|
| deportes     | 0.111 | 1.000 | 0.200 |    1 |
| economia     | 0.333 | 0.333 | 0.333 |    9 |
| finanzas     | 0.886 | 0.646 | 0.747 |   48 |
| geopolitica  | 0.500 | 0.600 | 0.545 |    5 |
| otros        | 0.333 | 0.333 | 0.333 |    3 |
| politica     | 0.727 | 0.471 | 0.571 |   17 |
| sociedad     | 0.250 | 0.800 | 0.381 |    5 |
| tecnologia   | 0.727 | 0.667 | 0.696 |   12 |

---

## 🔍 Matriz de Confusión

| Verdadero \ Predicho | deportes | economia | finanzas | geopolitica | otros | politica | sociedad | tecnologia |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| deportes     |    1 |    0 |    0 |    0 |    0 |    0 |    0 |    0 |
| economia     |    0 |    3 |    2 |    0 |    0 |    2 |    2 |    0 |
| finanzas     |    2 |    3 |   31 |    0 |    1 |    1 |    8 |    2 |
| geopolitica  |    1 |    0 |    0 |    3 |    0 |    0 |    0 |    1 |
| otros        |    1 |    0 |    0 |    0 |    1 |    0 |    1 |    0 |
| politica     |    4 |    3 |    1 |    1 |    0 |    8 |    0 |    0 |
| sociedad     |    0 |    0 |    0 |    1 |    0 |    0 |    4 |    0 |
| tecnologia   |    0 |    0 |    1 |    1 |    1 |    0 |    1 |    8 |

---

## ⚠️ Patrones de Confusión Más Frecuentes

- **finanzas → sociedad:** 8 casos
- **politica → deportes:** 4 casos
- **politica → economia:** 3 casos
- **finanzas → economia:** 3 casos
- **finanzas → tecnologia:** 2 casos
- **economia → sociedad:** 2 casos
- **economia → finanzas:** 2 casos
- **economia → politica:** 2 casos
- **finanzas → deportes:** 2 casos
- **politica → geopolitica:** 1 casos

---

## 📝 Ejemplos de Errores de Clasificación

### economia → finanzas

1. **La brecha de precios con el euro, una amenaza para las exportaciones españolas**
   Confianza: 0.851

2. **La londinense Bond Street tiene el alquiler más caro del mundo**
   Confianza: 0.847

---

### economia → politica

1. **Hacienda prorroga el sistema de módulos para autónomos, pero deja los límites en el aire**
   Confianza: 0.862

2. **Cuánto subirán las pensiones a partir del 1 de enero de 2026**
   Confianza: 0.858

---

### economia → sociedad

1. **Mahou transformará bares**
   Confianza: 0.878

2. **Euríbor hoy**
   Confianza: 0.864

---

### finanzas → deportes

1. **Meta deberá pagar 479 millones a los medios españoles por competencia desleal**
   Confianza: 0.863

2. **Banco Sabadell**
   Confianza: 0.858

---

### finanzas → economia

1. **Santander dividendos**
   Confianza: 0.880

2. **ETF renta fija**
   Confianza: 0.878

3. **Bankinter modifica la cúpula para crecer en pagos digitales**
   Confianza: 0.862

---

### finanzas → otros

1. **Ceuta irrumpe con Endesa, REE y Templus en 'data center'**
   Confianza: 0.864

---

### finanzas → politica

1. **Redeia negociará con Iberdrola y Endesa el plan antiapagones**
   Confianza: 0.855

---

### finanzas → sociedad

1. **Cuáles son las profesiones del futuro, con Juanjo Amorín.**
   Confianza: 0.879

2. **Inditex bate a LVMH como líder mundial de la moda**
   Confianza: 0.871

3. **Así gestiona su fortuna Amancio Ortega**
   Confianza: 0.865

4. **Amancio Ortega compra The Post en Canadá por cerca de 700 millones**
   Confianza: 0.857

5. **Santander First Brands**
   Confianza: 0.853

---

### finanzas → tecnologia

1. **Deloitte incorpora a 1.500 recién graduados, un 30% más**
   Confianza: 0.868

2. **KPMG lanza un nuevo negocio para 'start up' y se refuerza con el fichaje de Marta Echarri**
   Confianza: 0.843

---

### geopolitica → deportes

1. **Europa y la carrera por los recursos naturales**
   Confianza: 0.858

---

## 📊 Estadísticas de Confianza (Similarity Scores)

| Métrica | Correctos | Incorrectos | Todos |
|---------|-----------|-------------|-------|
| mean    | 0.872 | 0.860 | 0.867 |
| median  | 0.872 | 0.861 | 0.866 |
| std     | 0.016 | 0.010 | 0.015 |
| min     | 0.837 | 0.833 | 0.833 |
| max     | 0.909 | 0.880 | 0.909 |

---

## ⚡ Comparación de Rendimiento

### Embeddings (este PoC)
- **Tiempo total:** 15.6s
- **Carga de modelo:** 6.1s
- **Generación embeddings:** 3.1s
- **Clasificación:** 6.3s
- **Memoria pico:** 140.6 MB
- **Costo:** $0 (local)

### LLM (método actual)
- **Modelo:** gpt-4o-mini
- **Tiempo estimado:** ~15-30s para 180 URLs (batch)
- **Costo estimado:** ~$0.02-0.04 por ejecución
- **Dependencia:** API externa (OpenAI)

---

## ⚙️ Configuración Utilizada

- **Modelo embeddings:** intfloat/multilingual-e5-small
- **Método clasificación:** cosine_similarity
- **Umbral similitud:** 0.5
- **Usar ejemplos:** True
- **Ejemplos por categoría:** 3
- **Estrategia embedding categoría:** mean

### Dataset
- **Fecha desde:** Sin filtro
- **Fecha hasta:** Sin filtro
- **Max URLs:** 100
- **Categorías filtradas:** Todas

---
*Informe generado por poc_category_classification v1.0*