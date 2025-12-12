# Newsletter Utils - Pipeline de Noticias Automatizado

> Nota: este README refleja el estado inicial (solo Stage 01 completada). El pipeline actual usa PostgreSQL y tiene etapas 2-5 y webapp activas; consulta `DB_SCHEMA_OVERVIEW.md`, los README de `stages/` y `webapp/README.md` para información reciente.

Pipeline modular en Python para automatizar la obtención, clasificación, análisis y redacción de noticias de prensa diaria.

## Estado del Proyecto

### ✅ Etapa 1 - Extract URLs (COMPLETADA)

La primera etapa del pipeline está completamente funcional:

- ✅ Scraping web con Selenium en modo headless
- ✅ Extracción de enlaces desde múltiples fuentes configurables
- ✅ Filtrado inteligente con LLM (OpenAI) para identificar noticias reales vs navegación/ads
- ✅ Guardado en CSV con separador TAB
- ✅ Logging completo por fecha
- ✅ Tests unitarios

### 🔄 Próximas Etapas

- ⏳ Etapa 2: Upsert URLs y clasificación en base de datos
- ⏳ Etapa 3: Filtrado para newsletters
- ⏳ Etapa 4: Ranking de titulares
- ⏳ Etapa 5: Extracción de contenido completo
- ⏳ Etapa 6: Generación de newsletters

## Instalación

### Prerrequisitos

- Python 3.11+
- Chromium/Chrome y chromedriver instalados
- Cuenta de OpenAI con API key

### Setup

1. Crear entorno virtual:
```bash
python3 -m venv venv
source venv/bin/activate  # En Linux/Mac
# o
venv\Scripts\activate  # En Windows
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno:
El archivo `.env` ya está configurado con tu API key de OpenAI.

## Uso

### Ejecutar Etapa 1: Extract URLs

```bash
# Usar fecha de hoy
python stages/01_extract_urls.py

# Especificar fecha
python stages/01_extract_urls.py --date 2025-11-09
```

### Salida

- **CSV**: `data/raw/urls_YYYY-MM-DD.csv` con columnas:
  - `url`: URL del artículo
  - `title`: Titular
  - `source`: URL de la fuente
  - `extracted_at`: Timestamp de extracción

- **Logs**: `logs/YYYY-MM-DD/01_extract_urls.log`

### Ejemplo de ejecución exitosa

```
2025-11-09 18:51:08 - INFO - Stage 01: Extract URLs - Starting for 2025-11-09
2025-11-09 18:51:08 - INFO - Loaded 2 enabled sources from config/sources.yml
2025-11-09 18:51:08 - INFO - Processing source: BBC News (https://www.bbc.com/news)
2025-11-09 18:51:08 - INFO - Extracted 44 raw links from BBC News
2025-11-09 18:51:08 - INFO - Filtered to 24 news articles from BBC News
2025-11-09 18:51:08 - INFO - Saved 24 URLs to data/raw/urls_2025-11-09.csv
2025-11-09 18:51:08 - INFO - Stage 01: Extract URLs - Completed in 15.80s
```

## Configuración

### Fuentes de Noticias

Editar `config/sources.yml` para añadir/modificar fuentes:

```yaml
sources:
  - id: "bbc"
    name: "BBC News"
    url: "https://www.bbc.com/news"
    selectors:
      - "a[data-testid='internal-link']"
      - "h2 a"
      - "h3 a"
    enabled: true
```

### Categorías

Editar `config/categories.yml` para modificar las categorías disponibles.

### Configuración LLM

Editar `config/llm.yaml` para ajustar modelos y parámetros por etapa.

## Tests

Ejecutar tests unitarios:

```bash
pytest tests/test_extract_urls.py -v
```

Para cambios que afecten a la webapp, ejecuta los tests end-to-end con Playwright contra `https://lewisembe.duckdns.org` y revisa los logs de consola del navegador en el reporte HTML:

```bash
cd webapp/frontend
npm install
npx playwright test --trace on --reporter=html
npx playwright show-report  # abre el reporte; revisa Trace -> Console
```

## Herramientas de Desarrollo

### Reset Stage Tool

Script para limpiar/resetear archivos generados por cualquier stage:

```bash
# Resetear Stage 01 para hoy (con confirmación)
python reset_stage.py --stage 01

# Ver qué se borraría sin borrar nada
python reset_stage.py --stage 01 --date 2025-11-09 --dry-run

# Resetear todos los stages para una fecha
python reset_stage.py --stage all --date 2025-11-09

# Solo borrar logs, mantener datos
python reset_stage.py --stage 01 --logs-only
```

Ver documentación completa en [RESET_TOOL.md](RESET_TOOL.md)

### Token Usage Tracker

Sistema automático de tracking de consumo de tokens de OpenAI:

```bash
# Ver resumen de uso de tokens
python view_token_usage.py

# Ver uso para una fecha específica
python view_token_usage.py --date 2025-11-09

# Ver uso detallado por stage
python view_token_usage.py --stage 01 --detailed

# Filtrar por fecha y stage
python view_token_usage.py --date 2025-11-09 --stage 01
```

El tracking se registra automáticamente en `logs/token_usage.csv` con:
- Timestamp de cada llamada
- Fecha de ejecución
- Stage que hizo la llamada
- Modelo utilizado (gpt-4o-mini, gpt-4o, etc.)
- Operación realizada
- Tokens de entrada y salida
- Costo en USD calculado automáticamente

## Estructura del Proyecto

```
newsletter_utils/
├── config/              # Archivos de configuración YAML
├── stages/              # Scripts de cada etapa del pipeline
├── common/              # Utilidades compartidas
├── data/
│   ├── raw/            # Datos crudos (CSVs)
│   └── processed/      # Datos procesados
├── logs/               # Logs por fecha
├── tests/              # Tests unitarios
├── .env                # Variables de entorno
├── requirements.txt    # Dependencias Python
└── README.md          # Este archivo
```

## Notas Técnicas

### Selenium en ARM64/Raspberry Pi

El proyecto está configurado para usar chromium y chromedriver del sistema en arquitecturas ARM64.

### Formato CSV

Se usa TAB como separador (`\t`) en lugar de comas para evitar conflictos con el contenido de los titulares.

### Filtrado LLM

El filtrado con OpenAI identifica automáticamente:
- ✅ Artículos de noticias reales
- ❌ Enlaces de navegación (Inicio, Contacto, etc.)
- ❌ Páginas de sección/categoría
- ❌ Publicidad y contenido promocional
- ❌ Enlaces "Ver más", "Todas las noticias", etc.

## Problemas Conocidos

### El Confidencial no extrae enlaces

Los selectores CSS configurados para El Confidencial no están capturando enlaces. Esto se puede solucionar:

1. Inspeccionando la página con DevTools del navegador
2. Identificando los selectores correctos
3. Actualizando `config/sources.yml`

### Títulos con saltos de línea

Algunos títulos contienen saltos de línea. El módulo `csv` de Python maneja esto correctamente al leer el archivo.

## Próximos Pasos

1. Ajustar selectores CSS para El Confidencial
2. Añadir más fuentes de noticias españolas
3. Implementar Etapa 2: Upsert URLs y clasificación
4. Desarrollar base de datos SQLite
5. Implementar orquestador completo

## Autor

Pipeline desarrollado para automatizar la generación de newsletters personalizadas.
