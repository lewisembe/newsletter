# Newsletter Bot 📰🤖

Sistema automatizado para generar newsletters inteligentes a partir de múltiples fuentes de noticias, con clasificación automática por temas y enlaces sin paywall.

**🎯 Arquitectura Modular**: Sistema refactorizado en 7 stages independientes, cada uno testeable y mejorable por separado. Ver [ARCHITECTURE.md](ARCHITECTURE.md) para detalles.

## 🎯 Características

- ✅ **Fetching Inteligente**: Soporte para RSS feeds y web crawling
- ✅ **Clasificación Automática**: Usa OpenAI para clasificar artículos en categorías predefinidas
- ✅ **Sin Paywalls**: Genera enlaces sin paywall usando archive.ph, Wayback Machine y 12ft.io
- ✅ **Deduplicación**: Evita artículos repetidos entre ejecuciones
- ✅ **Newsletter Elegante**: Genera newsletters narrativas profesionales con formato Markdown
- ✅ **Google Sheets**: Almacena todo en Google Sheets para fácil acceso
- ✅ **Optimizado para Costos**: Minimiza uso de tokens de OpenAI (~$3/mes para 50 artículos/día)

## 📋 Estructura del Proyecto

```
newsletter_bot/
├── config/
│   ├── __init__.py
│   ├── settings.py              # Configuración central
│   └── credentials.json         # Credenciales de Google (no incluido en git)
├── src/
│   ├── __init__.py
│   ├── google_sheets.py         # Integración con Google Sheets
│   ├── news_fetcher.py          # Fetch de noticias (RSS + crawler)
│   ├── content_processor.py     # Limpieza y procesamiento de contenido
│   ├── archive_service.py       # Servicios de archivo sin paywall
│   ├── deduplicator.py          # Sistema de deduplicación
│   └── openai_client.py         # Cliente de OpenAI
├── main.py                       # Pipeline principal
├── setup_demo_data.py           # Script para datos de prueba
├── requirements.txt             # Dependencias Python
├── .env                         # Variables de entorno (no incluido en git)
├── .env.example                 # Plantilla de variables de entorno
├── .gitignore                   # Archivos ignorados por git
└── README.md                    # Este archivo
```

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
cd /path/to/newsletter_bot
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar Google Sheets API

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto
3. Habilita **Google Sheets API** y **Google Drive API**
4. Crea una Service Account:
   - Ve a "APIs & Services" → "Credentials"
   - Clic en "Create Credentials" → "Service Account"
   - Descarga el archivo JSON con las credenciales
5. Guarda el archivo como `config/credentials.json`
6. Copia el email de la service account (del archivo JSON)
7. Comparte tu Google Sheet con ese email dándole permisos de **Editor**

### 4. Configurar OpenAI API

1. Ve a [OpenAI Platform](https://platform.openai.com/api-keys)
2. Crea una nueva API key
3. Guárdala en el archivo `.env`

### 5. Crear archivo .env

```bash
cp .env.example .env
```

Edita el archivo `.env` con tus credenciales:

```env
# OpenAI API Configuration
OPENAI_API_KEY=tu_clave_de_openai_aqui

# Google Sheets Configuration
GOOGLE_SHEETS_ID=tu_id_del_google_sheet

# Content Processing
MAX_TOKENS_PER_ARTICLE=1000
MAX_ARTICLES_PER_DAY=100

# Execution Configuration
TIMEZONE=America/New_York
LOG_LEVEL=INFO

# OpenAI Models
CLASSIFICATION_MODEL=gpt-3.5-turbo
NEWSLETTER_MODEL=gpt-4-turbo-preview

# Archive Services (priority order)
ARCHIVE_SERVICES=archive.today,web.archive.org,12ft.io
```

### 6. Configurar Google Sheet

El Google Sheet necesita 4 pestañas con las siguientes estructuras:

#### Pestaña 1: "Fuentes"
| nombre | url | tipo | activo |
|--------|-----|------|--------|
| Financial Times | https://www.ft.com/rss/home | rss | si |

#### Pestaña 2: "Temas"
| id | nombre | keywords | descripcion |
|----|--------|----------|-------------|
| 1 | Economía y Finanzas | economía, finanzas, mercados | Noticias sobre economía y mercados financieros |

#### Pestaña 3: "Noticias_Procesadas"
| fecha_publicacion | titulo | fuente | tema | contenido_completo | contenido_truncado | url_original | url_sin_paywall | fecha_fetch | hash_contenido |
|-------------------|--------|--------|------|-------------------|-------------------|--------------|-----------------|-------------|----------------|
| *Se llena automáticamente* |

#### Pestaña 4: "Newsletters_Generadas"
| fecha_generacion | contenido | num_articulos | temas_cubiertos |
|------------------|-----------|---------------|-----------------|
| *Se llena automáticamente* |

**O simplemente ejecuta:**

```bash
./venv/bin/python setup_demo_data.py
```

Esto creará las pestañas automáticamente y agregará datos de ejemplo.

## 🎮 Uso

### Ejecución Manual

```bash
./venv/bin/python main.py
```

### Testing de Stages Individuales

Cada stage puede ser probado independientemente:

```bash
# Stage 1: Source Loading
./venv/bin/python -m stages.stage1_source_loading

# Stage 2: News Fetching
./venv/bin/python -m stages.stage2_news_fetching

# Stage 3: Content Processing
./venv/bin/python -m stages.stage3_content_processing

# Stage 4: Deduplication
./venv/bin/python -m stages.stage4_deduplication

# Stage 5: Classification
./venv/bin/python -m stages.stage5_classification

# Stage 6: Newsletter Generation
./venv/bin/python -m stages.stage6_newsletter_generation

# Stage 7: Persistence
./venv/bin/python -m stages.stage7_persistence
```

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para detalles de cada stage.

### Pipeline Completo (7 Stages)

El pipeline ejecuta estos pasos automáticamente:

1. **Fetch de fuentes activas** desde Google Sheets
2. **Carga de temas predefinidos**
3. **Obtención de artículos** desde RSS feeds o web crawling
4. **Filtrado de duplicados** usando URLs y hashes de contenido
5. **Procesamiento de contenido** (limpieza, extracción, truncado)
6. **Creación de enlaces sin paywall**
7. **Clasificación con OpenAI** (usando contenido truncado)
8. **Guardado en Google Sheets** (contenido completo)
9. **Generación de newsletter** con OpenAI GPT-4
10. **Guardado de newsletter** en Google Sheets

### Resultados

- Los artículos procesados se guardan en la pestaña **"Noticias_Procesadas"**
- La newsletter se guarda en la pestaña **"Newsletters_Generadas"**
- Logs detallados en `logs/newsletter_bot.log`

## 🔧 Configuración Avanzada

### Agregar Nuevas Fuentes

Edita la pestaña "Fuentes" en Google Sheets:

**Para RSS:**
```
nombre: The Guardian
url: https://www.theguardian.com/world/rss
tipo: rss
activo: si
```

**Para Web Crawling:**
```
nombre: TechCrunch
url: https://techcrunch.com
tipo: crawl
activo: si
```

### Agregar Nuevos Temas

Edita la pestaña "Temas" en Google Sheets:

```
id: 6
nombre: Deportes
keywords: deportes, fútbol, baloncesto, olimpiadas
descripcion: Noticias sobre deportes y eventos atléticos
```

### Ajustar Modelos de OpenAI

En el archivo `.env`:

```env
# Usar GPT-4 para clasificación (más preciso pero más caro)
CLASSIFICATION_MODEL=gpt-4-turbo-preview

# Usar GPT-3.5 para newsletter (más barato pero menos elaborado)
NEWSLETTER_MODEL=gpt-3.5-turbo
```

## 📊 Estimación de Costos

### Costos de OpenAI (aproximados)

**Por artículo:**
- Clasificación (GPT-3.5-turbo): ~1,000 tokens = $0.001
- Total por artículo: **$0.001**

**Por newsletter:**
- Generación (GPT-4-turbo): ~5,000 tokens = $0.05
- Total por newsletter: **$0.05**

**Mensual (50 artículos/día):**
- Clasificación: 50 × $0.001 × 30 = $1.50
- Newsletter: $0.05 × 30 = $1.50
- **Total: ~$3/mes**

## 🛠️ Troubleshooting

### Error: "No module named 'config'"

```bash
# Asegúrate de ejecutar desde el directorio raíz
./venv/bin/python main.py
```

### Error: "OPENAI_API_KEY is not set"

```bash
# Verifica que el archivo .env existe y tiene la clave correcta
cat .env | grep OPENAI_API_KEY
```

### Error: "Google credentials file not found"

```bash
# Verifica que las credenciales están en el lugar correcto
ls -la config/credentials.json
```

### No se encuentran artículos

1. Verifica que las fuentes están marcadas como "activas" en Google Sheets
2. Verifica que las URLs de RSS son correctas
3. Revisa los logs en `logs/newsletter_bot.log`

## 🔄 Ejecución Diaria Automática

### Opción 1: Cron (Linux/Mac)

```bash
crontab -e
```

Agrega:
```
0 8 * * * cd /ruta/al/newsletter_bot && ./venv/bin/python main.py
```

Esto ejecutará el script todos los días a las 8:00 AM.

### Opción 2: Task Scheduler (Windows)

1. Abre Task Scheduler
2. Crea nueva tarea básica
3. Trigger: Diario a las 8:00 AM
4. Acción: Ejecutar programa
   - Programa: `C:\ruta\al\venv\Scripts\python.exe`
   - Argumentos: `main.py`
   - Directorio: `C:\ruta\al\newsletter_bot`

### Opción 3: GitHub Actions (Cloud)

Crea `.github/workflows/newsletter.yml`:

```yaml
name: Generate Newsletter

on:
  schedule:
    - cron: '0 8 * * *'  # 8 AM UTC diario
  workflow_dispatch:  # Permite ejecución manual

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GOOGLE_SHEETS_ID: ${{ secrets.GOOGLE_SHEETS_ID }}
```

## 📝 Logs

Los logs se guardan en `logs/newsletter_bot.log` con información detallada:

- Conexiones a APIs
- Artículos procesados
- Clasificaciones realizadas
- Errores y warnings

## 🤝 Contribuir

¡Contribuciones son bienvenidas! Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

MIT License - Ver archivo LICENSE para más detalles

## 🙏 Agradecimientos

- OpenAI por la API de GPT
- Google por Sheets API
- Newspaper3k para extracción de artículos
- Archive.ph, Wayback Machine y 12ft.io por servicios de archivo

## 📧 Soporte

Para preguntas o problemas, abre un issue en el repositorio de GitHub.

---

**Desarrollado con ❤️ usando Python y OpenAI**
