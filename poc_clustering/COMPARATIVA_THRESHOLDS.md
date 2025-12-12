# Comparativa de Thresholds en Clustering

## Dataset de Prueba
- **Fecha:** 2025-11-17
- **Categoría:** política
- **Artículos totales:** 234

---

## Threshold 0.75 (Permisivo)

### Métricas Generales
- **Clusters detectados:** 20
- **Artículos agrupados:** 210 (89.7%)
- **Artículos únicos:** 24 (10.3%)
- **Cluster más grande:** 121 artículos (#CrisisPolíticaEspaña)
- **Similitud promedio:** 0.85
- **Tiempo de procesamiento:** 45.7s

### Distribución
| Tamaño Cluster | Cantidad | % |
|----------------|----------|---|
| 2 artículos | - | - |
| 3-5 artículos | - | - |
| 6-10 artículos | - | - |
| 11+ artículos | 1 | 5.0% |

### Ejemplos de Clusters
- **#CrisisPolíticaEspaña** (121 artículos) - DEMASIADO AMPLIO
  - Mezcla múltiples temas: caso Koldo, Begoña Gómez, AVE, Telefónica, etc.
  - Agrupa cualquier noticia relacionada con política española

### Conclusión
❌ **Demasiado permisivo** - Crea clusters gigantes que mezclan temas diferentes.

---

## Threshold 0.88 (Estricto)

### Métricas Generales
- **Clusters detectados:** 30
- **Artículos agrupados:** 85 (36.3%)
- **Artículos únicos:** 149 (63.7%)
- **Cluster más grande:** 10 artículos (#ResponsabilidadMazón)
- **Similitud promedio:** 0.93
- **Tiempo de procesamiento:** 50.0s

### Distribución
| Tamaño Cluster | Cantidad | % |
|----------------|----------|---|
| 2 artículos | 18 | 60.0% |
| 3-5 artículos | 11 | 36.7% |
| 6-10 artículos | 1 | 3.3% |
| 11+ artículos | 0 | 0.0% |

### Ejemplos de Clusters (Top 10)
1. **#ResponsabilidadMazón** (10 artículos) ✅
   - Comparecencia de Mazón por la DANA
   - 5 medios diferentes cubriendo el mismo evento

2. **#CondenaSheikhHasina** (5 artículos) ✅
   - Condena a muerte de ex-PM de Bangladesh
   - 5 medios internacionales

3. **#PuigdemontDetención** (4 artículos) ✅
   - Petición de Puigdemont al TC sobre orden de detención
   - 4 medios españoles

4. **#ConflictoAbortoMadrid** (4 artículos) ✅
   - Conflicto Gobierno-Madrid sobre registro de objetores
   - 3 medios diferentes

5. **#DéficitCCAA2026** (4 artículos) ✅
   - Hacienda ofrece déficit 0.1% a CCAA
   - 4 medios cubriendo el mismo anuncio

6. **#ArchivoCasoBegoña** (3 artículos) ✅
   - Archivo de causa contra alto cargo de Moncloa
   - 3 medios

7. **#ReaperturaLínea7B** (3 artículos) ✅
   - Reapertura línea de metro tras DANA
   - 3 medios valencianos

8. **#SegundaVueltaChile** (3 artículos) ✅
   - Elecciones presidenciales Chile (Jara vs Kast)
   - 3 medios

9. **#ÁbalosPagosNegros** (3 artículos) ✅
   - Caso Ábalos y empresarios PSOE
   - 3 medios

10. **#CasoBegoñaGómez** (2 artículos) ✅
    - Investigación software UCM
    - 2 medios

### Conclusión
✅ **Óptimo** - Clusters cohesivos que representan el mismo evento cubierto por múltiples medios.

---

## Análisis Comparativo

### Precisión vs Recall

| Threshold | Precisión | Recall | Balance |
|-----------|-----------|--------|---------|
| **0.75** | Baja | Alta (89.7%) | Muchos falsos positivos |
| **0.88** | Alta | Media (36.3%) | Pocos falsos positivos |

### Calidad de Clusters

**Threshold 0.75:**
- ❌ Clusters demasiado grandes (hasta 121 artículos)
- ❌ Mezcla temas diferentes
- ❌ Hashtags poco específicos
- ✅ Agrupa casi todo

**Threshold 0.88:**
- ✅ Clusters específicos (máx 10 artículos)
- ✅ Eventos bien definidos
- ✅ Hashtags descriptivos
- ✅ Misma historia, múltiples medios
- ⚠️ Deja muchos artículos sin agrupar (63.7%)

### Casos de Uso Recomendados

**Threshold 0.75-0.80 (Permisivo):**
- Cuando quieres maximizar agrupación
- Detección de temas amplios
- Primera pasada de deduplicación

**Threshold 0.85-0.90 (Estricto):**
- ✅ **Recomendado para newsletter**
- Detección de mismo evento cubierto por múltiples medios
- Deduplicación precisa
- Evitar información repetida

**Threshold 0.90+ (Muy Estricto):**
- Solo para detectar duplicados casi exactos
- Mismo titular con ligeras variaciones

---

## Recomendación Final

### Para el pipeline de newsletters: **Threshold 0.85-0.88**

**Justificación:**
1. Agrupa efectivamente el mismo evento cubierto por distintos medios
2. Evita mezclar temas diferentes
3. Los hashtags son específicos y útiles
4. Los artículos únicos (63.7%) son noticias genuinamente diferentes

**Ejemplo ideal:**
```
Cluster #ResponsabilidadMazón (10 artículos):
  - El País: "Mazón niega su responsabilidad"
  - ABC: "Mazón en la comisión de investigación"
  - El Mundo: "Nada habría cambiado si yo hubiera estado"
  - El Confidencial: "Mazón culpa a los técnicos"
  - Expansión: "Mazón dice que ha asumido responsabilidad"

→ Mismo evento, perspectivas ligeramente diferentes, 5 medios
→ Usuario lee solo 1-2 artículos en vez de 10 repetidos
```

### Configuración Recomendada

```yaml
clustering:
  similarity_threshold: 0.87
  adaptive_threshold: true
  adaptive_k: 0.8
  min_cluster_size: 2
```

### Beneficios para el Newsletter

1. **Reduce redundancia:** De 10 artículos sobre Mazón → mostrar solo 2-3 representativos
2. **Mejora diversidad:** El 63.7% de artículos únicos asegura variedad de temas
3. **Contexto enriquecido:** Ver que 5 medios cubren un tema indica relevancia
4. **Hashtags útiles:** Permiten al usuario identificar rápidamente el tema

---

## Próximos Pasos

### Optimizaciones Posibles

1. **Threshold por categoría:**
   ```yaml
   category_thresholds:
     politica: 0.88  # Más estricto
     tecnologia: 0.82  # Más permisivo
     deportes: 0.85
   ```

2. **Threshold adaptativo mejorado:**
   - Ajustar threshold según número de fuentes
   - Si 5+ medios cubren un tema → threshold más bajo

3. **Post-procesamiento:**
   - Fusionar clusters con >80% de solapamiento
   - Dividir clusters >15 artículos automáticamente

4. **Integración con Stage 05:**
   - Incluir información de cluster en el contexto del LLM
   - Generar resumen sintético de clusters grandes
   - Priorizar artículos de clusters importantes

---

**Generado:** 2025-11-17 por poc_clustering v0.1.0
