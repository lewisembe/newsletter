# Guía para agentes

- Propósito: utilidades de la etapa 01 (extracción de URLs) centradas en Selenium y filtrado inicial.
- Componentes: `selenium_utils.py` configura y opera navegadores headless; `url_classifier.py` usa reglas/LLM para descartar enlaces no noticiosos.
- Dependencias: requiere drivers de Selenium y configuración de fuentes en `config/sources.yml`.
- Uso rápido: las funciones son consumidas por `stages/01_extract_urls.py` y tareas Celery; evita romper firmas públicas.
