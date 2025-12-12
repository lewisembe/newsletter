# 📊 Informe de Clasificación por Categorías
**Método:** Embeddings vs LLM (ground truth)
**Modelo:** intfloat/multilingual-e5-small
**Generado:** 2025-11-20 16:47:59

---

## 📈 Resumen Ejecutivo

- **Total de URLs analizadas:** 100
- **Accuracy:** 67.00%
- **Precision (macro):** 0.478
- **Recall (macro):** 0.633
- **F1-Score (macro):** 0.495

- **Correctos:** 67 (67.0%)
- **Incorrectos:** 33 (33.0%)

---

## 📊 Métricas por Categoría

| Categoría | Precision | Recall | F1-Score | Support |
|-----------|-----------|--------|----------|---------|
| deportes     | 0.250 | 1.000 | 0.400 |    1 |
| economia     | 0.308 | 0.444 | 0.364 |    9 |
| finanzas     | 0.925 | 0.771 | 0.841 |   48 |
| geopolitica  | 0.455 | 1.000 | 0.625 |    5 |
| otros        | 0.000 | 0.000 | 0.000 |    3 |
| politica     | 0.875 | 0.412 | 0.560 |   17 |
| sociedad     | 0.300 | 0.600 | 0.400 |    5 |
| tecnologia   | 0.714 | 0.833 | 0.769 |   12 |

---

## 🔍 Matriz de Confusión

| Verdadero \ Predicho | deportes | economia | finanzas | geopolitica | otros | politica | sociedad | tecnologia |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| deportes     |    1 |    0 |    0 |    0 |    0 |    0 |    0 |    0 |
| economia     |    0 |    4 |    2 |    1 |    0 |    1 |    1 |    0 |
| finanzas     |    0 |    4 |   37 |    0 |    0 |    0 |    4 |    3 |
| geopolitica  |    0 |    0 |    0 |    5 |    0 |    0 |    0 |    0 |
| otros        |    1 |    0 |    0 |    1 |    0 |    0 |    1 |    0 |
| politica     |    2 |    5 |    1 |    2 |    0 |    7 |    0 |    0 |
| sociedad     |    0 |    0 |    0 |    1 |    0 |    0 |    3 |    1 |
| tecnologia   |    0 |    0 |    0 |    1 |    0 |    0 |    1 |   10 |

---

## ⚠️ Patrones de Confusión Más Frecuentes

- **politica → economia:** 5 casos
- **finanzas → sociedad:** 4 casos
- **finanzas → economia:** 4 casos
- **finanzas → tecnologia:** 3 casos
- **politica → geopolitica:** 2 casos
- **economia → finanzas:** 2 casos
- **politica → deportes:** 2 casos
- **sociedad → tecnologia:** 1 casos
- **economia → geopolitica:** 1 casos
- **economia → politica:** 1 casos

---

## 📝 Ejemplos de Errores de Clasificación

### economia → finanzas

1. **La brecha de precios con el euro, una amenaza para las exportaciones españolas**
   Confianza: 0.856

2. **La londinense Bond Street tiene el alquiler más caro del mundo**
   Confianza: 0.848

---

### economia → geopolitica

1. **Euríbor hoy**
   Confianza: 0.879

---

### economia → politica

1. **Hacienda prorroga el sistema de módulos para autónomos, pero deja los límites en el aire**
   Confianza: 0.862

---

### economia → sociedad

1. **Mahou transformará bares**
   Confianza: 0.891

---

### finanzas → economia

1. **ETF renta fija**
   Confianza: 0.891

2. **La división de la Fed enfría el recorte de tipos en diciembre**
   Confianza: 0.880

3. **Ricardo Pumar: "Insur espera crecer más de un 60% hasta 2030"**
   Confianza: 0.878

4. **Bankinter modifica la cúpula para crecer en pagos digitales**
   Confianza: 0.865

---

### finanzas → sociedad

1. **Inditex bate a LVMH como líder mundial de la moda**
   Confianza: 0.878

2. **Así gestiona su fortuna Amancio Ortega**
   Confianza: 0.872

3. **Santander First Brands**
   Confianza: 0.857

4. **Naturgy: el canal alcista, dibujado con escuadra y cartabón**
   Confianza: 0.855

---

### finanzas → tecnologia

1. **Cuáles son las profesiones del futuro, con Juanjo Amorín.**
   Confianza: 0.888

2. **El grupo japonés Sojitz toma el control de Nexus Energía**
   Confianza: 0.880

3. **Redeia negociará con Iberdrola y Endesa el plan antiapagones**
   Confianza: 0.865

---

### otros → deportes

1. **Todd Green (King): "Siempre he disfrutado del proceso de sintetizar"**
   Confianza: 0.866

---

### otros → geopolitica

1. **Cómo debe trabajar un líder la comunicación de forma eficaz**
   Confianza: 0.845

---

### otros → sociedad

1. **La Rioja: el arte de las pequeñas cosas aplicado a los grandes eventos**
   Confianza: 0.863

---

## 📊 Estadísticas de Confianza (Similarity Scores)

| Métrica | Correctos | Incorrectos | Todos |
|---------|-----------|-------------|-------|
| mean    | 0.876 | 0.869 | 0.874 |
| median  | 0.874 | 0.866 | 0.873 |
| std     | 0.016 | 0.013 | 0.015 |
| min     | 0.843 | 0.845 | 0.843 |
| max     | 0.915 | 0.891 | 0.915 |

---

## ⚡ Comparación de Rendimiento

### Embeddings (este PoC)
- **Tiempo total:** 17.7s
- **Carga de modelo:** 6.5s
- **Generación embeddings:** 4.1s
- **Clasificación:** 7.0s
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
- **Umbral similitud:** 0.6
- **Usar ejemplos:** True
- **Ejemplos por categoría:** 5
- **Estrategia embedding categoría:** weighted_mean

### Dataset
- **Fecha desde:** Sin filtro
- **Fecha hasta:** Sin filtro
- **Max URLs:** 100
- **Categorías filtradas:** Todas

---
*Informe generado por poc_category_classification v1.0*