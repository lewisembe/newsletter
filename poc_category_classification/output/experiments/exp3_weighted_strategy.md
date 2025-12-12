# 📊 Informe de Clasificación por Categorías
**Método:** Embeddings vs LLM (ground truth)
**Modelo:** intfloat/multilingual-e5-small
**Generado:** 2025-11-20 16:46:40

---

## 📈 Resumen Ejecutivo

- **Total de URLs analizadas:** 100
- **Accuracy:** 63.00%
- **Precision (macro):** 0.461
- **Recall (macro):** 0.589
- **F1-Score (macro):** 0.463

- **Correctos:** 63 (63.0%)
- **Incorrectos:** 37 (37.0%)

---

## 📊 Métricas por Categoría

| Categoría | Precision | Recall | F1-Score | Support |
|-----------|-----------|--------|----------|---------|
| deportes     | 0.125 | 1.000 | 0.222 |    1 |
| economia     | 0.400 | 0.444 | 0.421 |    9 |
| finanzas     | 0.921 | 0.729 | 0.814 |   48 |
| geopolitica  | 0.500 | 0.800 | 0.615 |    5 |
| otros        | 0.000 | 0.000 | 0.000 |    3 |
| politica     | 0.800 | 0.471 | 0.593 |   17 |
| sociedad     | 0.273 | 0.600 | 0.375 |    5 |
| tecnologia   | 0.667 | 0.667 | 0.667 |   12 |

---

## 🔍 Matriz de Confusión

| Verdadero \ Predicho | deportes | economia | finanzas | geopolitica | otros | politica | sociedad | tecnologia |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| deportes     |    1 |    0 |    0 |    0 |    0 |    0 |    0 |    0 |
| economia     |    0 |    4 |    1 |    0 |    0 |    2 |    1 |    1 |
| finanzas     |    2 |    3 |   35 |    0 |    1 |    0 |    5 |    2 |
| geopolitica  |    1 |    0 |    0 |    4 |    0 |    0 |    0 |    0 |
| otros        |    1 |    0 |    0 |    1 |    0 |    0 |    1 |    0 |
| politica     |    3 |    3 |    1 |    1 |    1 |    8 |    0 |    0 |
| sociedad     |    0 |    0 |    0 |    1 |    0 |    0 |    3 |    1 |
| tecnologia   |    0 |    0 |    1 |    1 |    1 |    0 |    1 |    8 |

---

## ⚠️ Patrones de Confusión Más Frecuentes

- **finanzas → sociedad:** 5 casos
- **politica → economia:** 3 casos
- **politica → deportes:** 3 casos
- **finanzas → economia:** 3 casos
- **economia → politica:** 2 casos
- **finanzas → tecnologia:** 2 casos
- **finanzas → deportes:** 2 casos
- **politica → geopolitica:** 1 casos
- **tecnologia → otros:** 1 casos
- **sociedad → tecnologia:** 1 casos

---

## 📝 Ejemplos de Errores de Clasificación

### economia → finanzas

1. **La londinense Bond Street tiene el alquiler más caro del mundo**
   Confianza: 0.838

---

### economia → politica

1. **Hacienda prorroga el sistema de módulos para autónomos, pero deja los límites en el aire**
   Confianza: 0.856

2. **Cuánto subirán las pensiones a partir del 1 de enero de 2026**
   Confianza: 0.852

---

### economia → sociedad

1. **Mahou transformará bares**
   Confianza: 0.875

---

### economia → tecnologia

1. **Euríbor hoy**
   Confianza: 0.864

---

### finanzas → deportes

1. **Meta deberá pagar 479 millones a los medios españoles por competencia desleal**
   Confianza: 0.860

2. **Banco Sabadell**
   Confianza: 0.854

---

### finanzas → economia

1. **Santander dividendos**
   Confianza: 0.884

2. **ETF renta fija**
   Confianza: 0.880

3. **Bankinter modifica la cúpula para crecer en pagos digitales**
   Confianza: 0.856

---

### finanzas → otros

1. **Ceuta irrumpe con Endesa, REE y Templus en 'data center'**
   Confianza: 0.861

---

### finanzas → sociedad

1. **Inditex bate a LVMH como líder mundial de la moda**
   Confianza: 0.868

2. **Así gestiona su fortuna Amancio Ortega**
   Confianza: 0.858

3. **Amancio Ortega compra The Post en Canadá por cerca de 700 millones**
   Confianza: 0.851

4. **Santander First Brands**
   Confianza: 0.850

5. **Naturgy: el canal alcista, dibujado con escuadra y cartabón**
   Confianza: 0.840

---

### finanzas → tecnologia

1. **Cuáles son las profesiones del futuro, con Juanjo Amorín.**
   Confianza: 0.881

2. **Deloitte incorpora a 1.500 recién graduados, un 30% más**
   Confianza: 0.865

---

### geopolitica → deportes

1. **Europa y la carrera por los recursos naturales**
   Confianza: 0.856

---

## 📊 Estadísticas de Confianza (Similarity Scores)

| Métrica | Correctos | Incorrectos | Todos |
|---------|-----------|-------------|-------|
| mean    | 0.867 | 0.858 | 0.864 |
| median  | 0.867 | 0.857 | 0.863 |
| std     | 0.017 | 0.011 | 0.016 |
| min     | 0.830 | 0.838 | 0.830 |
| max     | 0.911 | 0.884 | 0.911 |

---

## ⚡ Comparación de Rendimiento

### Embeddings (este PoC)
- **Tiempo total:** 17.9s
- **Carga de modelo:** 6.7s
- **Generación embeddings:** 3.8s
- **Clasificación:** 7.3s
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
- **Estrategia embedding categoría:** weighted_mean

### Dataset
- **Fecha desde:** Sin filtro
- **Fecha hasta:** Sin filtro
- **Max URLs:** 100
- **Categorías filtradas:** Todas

---
*Informe generado por poc_category_classification v1.0*