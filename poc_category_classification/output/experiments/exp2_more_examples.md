# 📊 Informe de Clasificación por Categorías
**Método:** Embeddings vs LLM (ground truth)
**Modelo:** intfloat/multilingual-e5-small
**Generado:** 2025-11-20 16:46:00

---

## 📈 Resumen Ejecutivo

- **Total de URLs analizadas:** 100
- **Accuracy:** 66.00%
- **Precision (macro):** 0.485
- **Recall (macro):** 0.604
- **F1-Score (macro):** 0.482

- **Correctos:** 66 (66.0%)
- **Incorrectos:** 34 (34.0%)

---

## 📊 Métricas por Categoría

| Categoría | Precision | Recall | F1-Score | Support |
|-----------|-----------|--------|----------|---------|
| deportes     | 0.167 | 1.000 | 0.286 |    1 |
| economia     | 0.286 | 0.444 | 0.348 |    9 |
| finanzas     | 0.925 | 0.771 | 0.841 |   48 |
| geopolitica  | 0.444 | 0.800 | 0.571 |    5 |
| otros        | 0.000 | 0.000 | 0.000 |    3 |
| politica     | 0.889 | 0.471 | 0.615 |   17 |
| sociedad     | 0.273 | 0.600 | 0.375 |    5 |
| tecnologia   | 0.900 | 0.750 | 0.818 |   12 |

---

## 🔍 Matriz de Confusión

| Verdadero \ Predicho | deportes | economia | finanzas | geopolitica | otros | politica | sociedad | tecnologia |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| deportes     |    1 |    0 |    0 |    0 |    0 |    0 |    0 |    0 |
| economia     |    0 |    4 |    2 |    1 |    0 |    1 |    1 |    0 |
| finanzas     |    1 |    5 |   37 |    0 |    0 |    0 |    5 |    0 |
| geopolitica  |    0 |    0 |    1 |    4 |    0 |    0 |    0 |    0 |
| otros        |    1 |    0 |    0 |    1 |    0 |    0 |    1 |    0 |
| politica     |    3 |    5 |    0 |    1 |    0 |    8 |    0 |    0 |
| sociedad     |    0 |    0 |    0 |    1 |    0 |    0 |    3 |    1 |
| tecnologia   |    0 |    0 |    0 |    1 |    1 |    0 |    1 |    9 |

---

## ⚠️ Patrones de Confusión Más Frecuentes

- **politica → economia:** 5 casos
- **finanzas → sociedad:** 5 casos
- **finanzas → economia:** 5 casos
- **politica → deportes:** 3 casos
- **economia → finanzas:** 2 casos
- **tecnologia → otros:** 1 casos
- **politica → geopolitica:** 1 casos
- **sociedad → tecnologia:** 1 casos
- **economia → geopolitica:** 1 casos
- **economia → politica:** 1 casos

---

## 📝 Ejemplos de Errores de Clasificación

### economia → finanzas

1. **La brecha de precios con el euro, una amenaza para las exportaciones españolas**
   Confianza: 0.859

2. **La londinense Bond Street tiene el alquiler más caro del mundo**
   Confianza: 0.855

---

### economia → geopolitica

1. **Euríbor hoy**
   Confianza: 0.880

---

### economia → politica

1. **Hacienda prorroga el sistema de módulos para autónomos, pero deja los límites en el aire**
   Confianza: 0.866

---

### economia → sociedad

1. **Mahou transformará bares**
   Confianza: 0.893

---

### finanzas → deportes

1. **Banco Sabadell**
   Confianza: 0.859

---

### finanzas → economia

1. **ETF renta fija**
   Confianza: 0.889

2. **La división de la Fed enfría el recorte de tipos en diciembre**
   Confianza: 0.886

3. **Ricardo Pumar: "Insur espera crecer más de un 60% hasta 2030"**
   Confianza: 0.881

4. **Los ascensos a socios en las Big Four se hunden a mínimos de cinco años**
   Confianza: 0.879

5. **Bankinter modifica la cúpula para crecer en pagos digitales**
   Confianza: 0.869

---

### finanzas → sociedad

1. **Cuáles son las profesiones del futuro, con Juanjo Amorín.**
   Confianza: 0.886

2. **Inditex bate a LVMH como líder mundial de la moda**
   Confianza: 0.880

3. **Así gestiona su fortuna Amancio Ortega**
   Confianza: 0.878

4. **Naturgy: el canal alcista, dibujado con escuadra y cartabón**
   Confianza: 0.861

5. **Santander First Brands**
   Confianza: 0.857

---

### geopolitica → finanzas

1. **La noruega Kongsberg desembarca en España ante la eclosión de fondos públicos para Defensa**
   Confianza: 0.862

---

### otros → deportes

1. **Todd Green (King): "Siempre he disfrutado del proceso de sintetizar"**
   Confianza: 0.868

---

### otros → geopolitica

1. **Cómo debe trabajar un líder la comunicación de forma eficaz**
   Confianza: 0.842

---

## 📊 Estadísticas de Confianza (Similarity Scores)

| Métrica | Correctos | Incorrectos | Todos |
|---------|-----------|-------------|-------|
| mean    | 0.879 | 0.871 | 0.876 |
| median  | 0.878 | 0.869 | 0.876 |
| std     | 0.015 | 0.013 | 0.015 |
| min     | 0.845 | 0.842 | 0.842 |
| max     | 0.913 | 0.893 | 0.913 |

---

## ⚡ Comparación de Rendimiento

### Embeddings (este PoC)
- **Tiempo total:** 18.7s
- **Carga de modelo:** 6.4s
- **Generación embeddings:** 4.6s
- **Clasificación:** 7.7s
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
- **Ejemplos por categoría:** 5
- **Estrategia embedding categoría:** mean

### Dataset
- **Fecha desde:** Sin filtro
- **Fecha hasta:** Sin filtro
- **Max URLs:** 100
- **Categorías filtradas:** Todas

---
*Informe generado por poc_category_classification v1.0*