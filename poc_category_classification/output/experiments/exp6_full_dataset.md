# 📊 Informe de Clasificación por Categorías
**Método:** Embeddings vs LLM (ground truth)
**Modelo:** intfloat/multilingual-e5-small
**Generado:** 2025-11-20 16:52:08

---

## 📈 Resumen Ejecutivo

- **Total de URLs analizadas:** 3757
- **Accuracy:** 54.67%
- **Precision (macro):** 0.474
- **Recall (macro):** 0.514
- **F1-Score (macro):** 0.457

- **Correctos:** 2054 (54.7%)
- **Incorrectos:** 1703 (45.3%)

---

## 📊 Métricas por Categoría

| Categoría | Precision | Recall | F1-Score | Support |
|-----------|-----------|--------|----------|---------|
| deportes     | 0.436 | 0.683 | 0.532 |  259 |
| economia     | 0.564 | 0.244 | 0.341 |  324 |
| finanzas     | 0.473 | 0.740 | 0.578 |  362 |
| geopolitica  | 0.363 | 0.758 | 0.491 |  260 |
| otros        | 0.000 | 0.000 | 0.000 |  263 |
| politica     | 0.830 | 0.344 | 0.486 |  881 |
| sociedad     | 0.614 | 0.783 | 0.688 | 1076 |
| tecnologia   | 0.514 | 0.563 | 0.537 |  332 |

---

## 🔍 Matriz de Confusión

| Verdadero \ Predicho | deportes | economia | finanzas | geopolitica | otros | politica | sociedad | tecnologia |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| deportes     |  177 |    0 |    1 |   13 |    0 |    1 |   63 |    4 |
| economia     |   10 |   79 |  147 |   31 |    0 |   12 |   33 |   12 |
| finanzas     |   20 |   16 |  268 |    7 |    0 |    5 |   28 |   18 |
| geopolitica  |    5 |    0 |   11 |  197 |    0 |    8 |   27 |   12 |
| otros        |   35 |    1 |   19 |   18 |    0 |   12 |  140 |   38 |
| politica     |   80 |   39 |   46 |  210 |    0 |  303 |  173 |   30 |
| sociedad     |   74 |    3 |   24 |   45 |    0 |   24 |  843 |   63 |
| tecnologia   |    5 |    2 |   50 |   21 |    0 |    0 |   67 |  187 |

---

## ⚠️ Patrones de Confusión Más Frecuentes

- **politica → geopolitica:** 210 casos
- **politica → sociedad:** 173 casos
- **economia → finanzas:** 147 casos
- **otros → sociedad:** 140 casos
- **politica → deportes:** 80 casos
- **sociedad → deportes:** 74 casos
- **tecnologia → sociedad:** 67 casos
- **sociedad → tecnologia:** 63 casos
- **deportes → sociedad:** 63 casos
- **tecnologia → finanzas:** 50 casos

---

## 📝 Ejemplos de Errores de Clasificación

### deportes → finanzas

1. **El streaming da el gran salto en el deporte: Netflix, Amazon o Dazn ya aglutinan el 20% del gasto en derechos**
   Confianza: 0.875

---

### deportes → geopolitica

1. **España Republica Checa**
   Confianza: 0.885

2. **Guía completa del encuentro y las actividades paralelas**
   Confianza: 0.865

3. **Conte se toma una insólita semana sabática en medio de la crisis del Nápoles**
   Confianza: 0.856

4. **El muro de Unai Simón en la España de Luis de la Fuente**
   Confianza: 0.854

5. **Récit Jean-Baptiste Chastand et Jérôme Porier Article réservé aux abonnésNovak Djokovic, l’idole du peuple serbe devenue la cible du président Aleksandar Vucic Le tennisman de 38 ans est soumis à de fortes pressions pour avoir pris fait et cause pour les étudiants dans leur combat contre la corruption et le pouvoir de Belgrade. 4 min de lecture**
   Confianza: 0.839

6. **The L.P.G.A. Has a Problem. Kai Trump Isn’t the Solution.**
   Confianza: 0.831

7. **Easy friendlies or tough opposition? England's World Cup dilemmaEngland have been able to start preparing for the World Cup for months, but the task of picking warm-up games is tricky. BBC Sport assesses some of the options.1 hr agoEngland Men**
   Confianza: 0.817

8. **Late-Game Chaos and Off-Field Drama Ran Wild in N.F.L. Week 11**
   Confianza: 0.817

9. **'European golf in rude health but sponsor demands solutions to fractured game'After a successful season inside the ropes for Europe's elite players, tour sponsors DP World are keen to sort off-course issues for the benefit of fans, writes Iain Carter.4 hrs agoGolf**
   Confianza: 0.812

10. **The key questions facing Tuchel before World CupEngland head coach Thomas Tuchel now faces key decisions in the countdown to the World Cup, says chief football writer Phil McNulty.14 hrs agoEngland Men**
   Confianza: 0.809

---

### deportes → politica

1. **What Happens When College Football Games Are Only for the Rich?**
   Confianza: 0.814

---

### deportes → sociedad

1. **España merece campos llenos**
   Confianza: 0.899

2. **Los amaños en el tenis: antenas parabólicas, software de vanguardia y desfase de TV**
   Confianza: 0.879

3. **Los consejos de la psicóloga de las estrellas a los que quieran convertirse en entrenadores: "Hay que cambiar de gafas"**
   Confianza: 0.877

4. **Bellingham hace un Vinícius y se lleva un tirón de orejas: «El comportamiento es clave»**
   Confianza: 0.876

5. **La NFL se gasta dos millones en transformar el Bernabéu: sin escudos del Madrid ni Tour, con paneles contra el ruido, vestuarios más grandes...**
   Confianza: 0.876

6. **Los Miami Dolphins quieren ser el equipo NFL del mundo hispanohablante**
   Confianza: 0.875

7. **Dentro del show de la NFL en el Bernabéu: "Se ha agotado la comida y la bebida, no contaban el gran consumo de los estadounidenses"**
   Confianza: 0.875

8. **El visitante nocturno**
   Confianza: 0.874

9. **Así ha transformado la NFL el Bernabéu con dos millones de euros: gradas, vestuarios, salas de prensa, tienda**
   Confianza: 0.872

10. **Otro año de ensueño de McIlroy**
   Confianza: 0.871

---

### deportes → tecnologia

1. **He Ran a Sub-2 Hour Marathon. What’s Next?**
   Confianza: 0.836

2. **Ashes predictions - TMS pundits have their sayTest Match Special pundits including Michael Vaughan and Jonathan Agnew give their predictions for the 2025-26 Ashes series.1 hr agoCricket**
   Confianza: 0.821

3. **Patriots win to equal best run since Brady yearsThe New England Patriots win an eighth successive game for the first time since 2019 as they extend their overall lead in the AFC East standings.5 hrs agoAmerican Football**
   Confianza: 0.814

4. **Hakkinen's daughter, 14, joins McLaren programmeElla Hakkinen, the 14-year-old daughter of two-time F1 world champion Mika Hakkinen, is added to the McLaren driver development programme.49 mins agoMotorsport**
   Confianza: 0.814

---

### economia → deportes

1. **Competencia pide a LaLiga que venda sus derechos por tres años y elimine los lotes que impidan más de un operador**
   Confianza: 0.881

2. **Puente anuncia el proyecto AV350 para conectar Madrid-Barcelona en menos de dos horas con trenes a 350 kilómetros por hora**
   Confianza: 0.866

3. **Cinven asciende al español Jorge Quemada a lo más alto de su cúpula directiva**
   Confianza: 0.863

4. **Puente anuncia un plan para reducir a dos horas el trayecto del AVE Madrid-Barcelona**
   Confianza: 0.863

5. **Joao Oliveira, pluriempleado: "La sensación de la gente trabajadora es que trabajas y te sientes pobre"**
   Confianza: 0.861

6. **La NFL en el Bernabéu cumple con las expectativas y deja 70 millones de euros de impacto económico en Madrid**
   Confianza: 0.858

7. **La educación de élite británica asalta España y Madrid ya es su capital**
   Confianza: 0.856

8. **La negativa de Sapa y Santa Bárbara a fusionarse con Indra quiebra los planes de Sánchez y su campeón nacional de la Defensa**
   Confianza: 0.855

9. **Renfe se rebela ante la ley que le obliga a indemnizar por retrasos de 15 minutos en la alta velocidad**
   Confianza: 0.855

10. **El dueño de La Española roza 1.500 millones de euros en ingresos**
   Confianza: 0.850

---

### economia → finanzas

1. **Wall Street cae arrastrado por las tecnológicas**
   Confianza: 0.908

2. **La Primera de Expansión sobre los resultados de Sabadell, ACS, BlackRock, Santander, nucleares, Anthropic y Trump**
   Confianza: 0.905

3. **Wall Street se hunde un 2% lastrado por la tecnología, y el Ibex pone fin a su racha de máximos históricos**
   Confianza: 0.905

4. **Dónde invertir a contracorriente del mercado para ganar en Bolsa, con Juan Huerta de Soto, de Cobas AM**
   Confianza: 0.899

5. **Tres valores del Ibex se disparan más del 100% en 2025**
   Confianza: 0.898

6. **Cómo afecta a la Bolsa el fin del 'cierre' de EEUU**
   Confianza: 0.895

7. **Sabadell cede un 5% en bolsa al lograr beneficio récord y reducir márgenes**
   Confianza: 0.894

8. **El mercado digiere el impacto del cierre de la Administración de EE UU bajo la gran incógnita de la situación económica**
   Confianza: 0.894

9. **Precio Gasolina hoy**
   Confianza: 0.893

10. **Santander Mapfre entrará en beneficios "más pronto que tarde"**
   Confianza: 0.891

---

### economia → geopolitica

1. **Débiles perspectivas de crecimiento europeo**
   Confianza: 0.900

2. **Alemania rica, Alemania pobre**
   Confianza: 0.893

3. **Tormenta en el coste de la vida**
   Confianza: 0.886

4. **La UE acuerda imponer aranceles a las mercancías baratas que provienen de China**
   Confianza: 0.884

5. **Todo o nada: el trilema del Ejecutivo ante el baile de sillones económicos en la eurozona**
   Confianza: 0.882

6. **La UE aprieta para que los pedidos de Temu y Shein paguen aranceles**
   Confianza: 0.881

7. **Países Bajos rebaja la tensión comercial entre Europa y China al suspender los controles a Nexperia**
   Confianza: 0.879

8. **Euríbor hoy**
   Confianza: 0.879

9. **La tension monte à la Coordination rurale avant son congrès**
   Confianza: 0.878

10. **Bruselas constata que la fortaleza económica de España se frena**
   Confianza: 0.876

---

### economia → politica

1. **Pensiones 2026**
   Confianza: 0.891

2. **El Pacto de Toledo necesita una revisión: "Quien no tenga hijos debe cotizar...**
   Confianza: 0.888

3. **Bertrand Venteau, adepte des actions coup-de-poing, élu à la tête de la Coordination rurale**
   Confianza: 0.878

4. **La Airef paraliza el nuevo examen del sistema de pensiones que le encargó el Gobierno porque cree que no cumple la ley**
   Confianza: 0.872

5. **La formación en riesgos laborales para empleadas de hogar aún no está disponible a pocas horas de que sea obligatoria la evaluación**
   Confianza: 0.865

6. **Renfe se rebela contra el mandato del Congreso de indemnizar los retrasos de más de 15 minutos**
   Confianza: 0.862

7. **Hacienda prorroga el sistema de módulos para autónomos, pero deja los límites en el aire**
   Confianza: 0.862

8. **La amenaza que se cierne sobre los recién licenciados universitarios**
   Confianza: 0.860

9. **Dans la recherche, un budget en trompe-l’œil**
   Confianza: 0.856

10. **Las trabajadoras podrán exigir desde el viernes a sus empleadores la evaluación de riesgos laborales**
   Confianza: 0.853

---

### economia → sociedad

1. **Mahou transformará bares**
   Confianza: 0.891

2. **1Mercadona revela el origen de las naranjas que venderá este año en sus supermercados**
   Confianza: 0.890

3. **3Mercadona revela el origen de las naranjas que venderá este año en sus supermercados**
   Confianza: 0.887

4. **Ayudas alquiler Madrid**
   Confianza: 0.884

5. **Paga extra navidad**
   Confianza: 0.883

6. **Renueva tu armario de invierno con estas superofertas de Uniqlo, Mango y Massimo Dutti**
   Confianza: 0.881

7. **Fincas rústicas**
   Confianza: 0.879

8. **El peón de dama de la Bolsa que todos aconsejan comprar**
   Confianza: 0.873

9. **Casa prefabricada**
   Confianza: 0.873

10. **El Black Friday de Amazon empieza ya y estos son los mejores chollos del primer día de ofertas**
   Confianza: 0.872

---

## 📊 Estadísticas de Confianza (Similarity Scores)

| Métrica | Correctos | Incorrectos | Todos |
|---------|-----------|-------------|-------|
| mean    | 0.858 | 0.855 | 0.857 |
| median  | 0.860 | 0.855 | 0.858 |
| std     | 0.021 | 0.019 | 0.020 |
| min     | 0.786 | 0.787 | 0.786 |
| max     | 0.917 | 0.910 | 0.917 |

---

## ⚡ Comparación de Rendimiento

### Embeddings (este PoC)
- **Tiempo total:** 3m 42s
- **Carga de modelo:** 6.1s
- **Generación embeddings:** 3.3s
- **Clasificación:** 3m 33s
- **Memoria pico:** 144.0 MB
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
- **Max URLs:** Sin límite
- **Categorías filtradas:** Todas

---
*Informe generado por poc_category_classification v1.0*