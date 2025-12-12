# 📊 Informe Comparativo de Experimentos
**PoC:** Category Classification con Embeddings
**Generado:** 2025-11-20 16:53:19

---

## 📈 Resumen Ejecutivo

Se ejecutaron **7 experimentos** para optimizar la clasificación por categorías usando embeddings:

### Resultados Clave
- **Baseline** (100 URLs): 59.0% accuracy
- **Mejor configuración** (100 URLs): **67.0% accuracy** (Configuración Óptima)
- **Mejora absoluta**: +8.0 puntos
- **Mejora relativa**: +13.6%

### Dataset Completo (3757 URLs)
- **Accuracy**: 54.7%
- **F1-Score**: 0.457
- **Tiempo**: 3m 42s
- **Conclusión**: Accuracy más baja sugiere que subset de 100 URLs no es representativo

---

## 📊 Tabla Comparativa (100 URLs)

| Experimento | Accuracy | Precision | Recall | F1 | Tiempo | Nota |
|-------------|----------|-----------|--------|-----|---------|------|
| Baseline        | 59.0%    | 0.484     | 0.606   | 0.476 | 15.5s   |  |
| Threshold 0.6   | 59.0%    | 0.484     | 0.606   | 0.476 | 16.7s   | ⚠️ Sin efecto (method=cosine_similarity ignora threshold) |
| 5 Ejemplos      | 66.0%    | 0.485     | 0.604   | 0.482 | 18.7s   | ✓ MEJORA: +7 pts accuracy |
| Weighted Strategy | 63.0%    | 0.461     | 0.589   | 0.463 | 17.9s   | ✓ MEJORA: +4 pts accuracy |
| Excluir 'otros' | 60.0%    | 0.436     | 0.578   | 0.437 | 16.8s   | ✓ MEJORA: +1 pt accuracy |
| Configuración Óptima | 67.0%    | 0.478     | 0.633   | 0.495 | 17.7s   | ✓✓ MEJOR: +8 pts accuracy |

---

## 🔍 Análisis por Experimento

### 1. Baseline

**Configuración:**
```
threshold=0.5, examples=3, strategy=mean, include_otros=yes
```

**Resultados:**
- Dataset: 100 URLs
- Accuracy: **59.0%**
- Precision (macro): 0.484
- Recall (macro): 0.606
- F1-Score (macro): 0.476
- Tiempo: 15.5s
- Memoria: 140.6 MB

---

### 2. Threshold 0.6

**Configuración:**
```
threshold=0.6, examples=3, strategy=mean, include_otros=yes
```

**Resultados:**
- Dataset: 100 URLs
- Accuracy: **59.0%**
- Precision (macro): 0.484
- Recall (macro): 0.606
- F1-Score (macro): 0.476
- Tiempo: 16.7s
- Memoria: 140.6 MB

**Observaciones:** ⚠️ Sin efecto (method=cosine_similarity ignora threshold)

**Δ vs Baseline:** Sin cambio

---

### 3. 5 Ejemplos

**Configuración:**
```
threshold=0.5, examples=5, strategy=mean, include_otros=yes
```

**Resultados:**
- Dataset: 100 URLs
- Accuracy: **66.0%**
- Precision (macro): 0.485
- Recall (macro): 0.604
- F1-Score (macro): 0.482
- Tiempo: 18.7s
- Memoria: 140.6 MB

**Observaciones:** ✓ MEJORA: +7 pts accuracy

**Δ vs Baseline:** +7.0 pts ✓

---

### 4. Weighted Strategy

**Configuración:**
```
threshold=0.5, examples=3, strategy=weighted_mean, include_otros=yes
```

**Resultados:**
- Dataset: 100 URLs
- Accuracy: **63.0%**
- Precision (macro): 0.461
- Recall (macro): 0.589
- F1-Score (macro): 0.463
- Tiempo: 17.9s
- Memoria: 140.6 MB

**Observaciones:** ✓ MEJORA: +4 pts accuracy

**Δ vs Baseline:** +4.0 pts ✓

---

### 5. Excluir 'otros'

**Configuración:**
```
threshold=0.5, examples=3, strategy=mean, include_otros=no
```

**Resultados:**
- Dataset: 100 URLs
- Accuracy: **60.0%**
- Precision (macro): 0.436
- Recall (macro): 0.578
- F1-Score (macro): 0.437
- Tiempo: 16.8s
- Memoria: 140.6 MB

**Observaciones:** ✓ MEJORA: +1 pt accuracy

**Δ vs Baseline:** +1.0 pts ✓

---

### 6. Configuración Óptima

**Configuración:**
```
threshold=0.6, examples=5, strategy=weighted_mean, include_otros=no
```

**Resultados:**
- Dataset: 100 URLs
- Accuracy: **67.0%**
- Precision (macro): 0.478
- Recall (macro): 0.633
- F1-Score (macro): 0.495
- Tiempo: 17.7s
- Memoria: 140.6 MB

**Observaciones:** ✓✓ MEJOR: +8 pts accuracy

**Δ vs Baseline:** +8.0 pts ✓

---

### 7. Dataset Completo

**Configuración:**
```
threshold=0.6, examples=5, strategy=weighted_mean, include_otros=no
```

**Resultados:**
- Dataset: 3757 URLs
- Accuracy: **54.7%**
- Precision (macro): 0.474
- Recall (macro): 0.514
- F1-Score (macro): 0.457
- Tiempo: 222.0s
- Memoria: 144.0 MB

**Observaciones:** ⚠️ Accuracy baja con dataset real (54.7%)

---

## 💡 Conclusiones y Recomendaciones

### ✅ Mejoras Efectivas
1. **Aumentar ejemplos a 5** → +7 pts accuracy (exp2: 66.0%)
2. **Weighted mean strategy** → +4 pts accuracy (exp3: 63.0%)
3. **Combinación óptima** → +8 pts accuracy (exp5: 67.0%)

### ❌ Mejoras No Efectivas
1. **Threshold 0.6** → Sin efecto (method=cosine_similarity ignora threshold)
2. **Excluir 'otros'** → Mejora mínima (+1 pt)

### ⚠️ Observación Importante: Dataset Size

La diferencia entre exp5 (67% con 100 URLs) y exp6 (54.7% con 3757 URLs) revela:
- **Sesgo de muestra**: Las 100 URLs más recientes son más fáciles de clasificar
- **Variabilidad real**: El dataset completo tiene mayor diversidad temática
- **Accuracy realista**: ~55% es más representativo del rendimiento real

### 🎯 Configuración Recomendada

```yaml
classification:
  method: cosine_similarity
  examples_per_category: 5  # ← CLAVE
  category_embedding_strategy: weighted_mean  # ← CLAVE

categories:
  exclude: ['otros']  # ← Opcional
```

### 📊 Comparación vs LLM

| Métrica | Embeddings (optimizado) | LLM (gpt-4o-mini) |
|---------|------------------------|-------------------|
| Accuracy | **~55%** | ~90-95% (estimado) |
| Velocidad | **3m 42s** (3757 URLs) | ~30-60s (180 URLs) |
| Costo | **$0** (local) | ~$0.03 por ejecución |
| Escalabilidad | **Sin límite** | Rate limits API |
| Reproducibilidad | **100%** | ~98% (temperature=0.2) |

### 🚀 Próximos Pasos

1. **Modelo más grande**: Probar `intfloat/multilingual-e5-base` (768 dims)
2. **Fine-tuning**: Entrenar clasificador supervisado con histórico
3. **Hybrid approach**: Embeddings para categorías fáciles, LLM para difíciles
4. **Análisis de errores**: Identificar patrones de confusión y ajustar categorías
5. **Temporal analysis**: Evaluar si accuracy varía con el tiempo

---

*Informe generado automáticamente - 2025-11-20 16:53:19*