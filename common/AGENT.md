# Guía para agentes

- Propósito: utilidades compartidas (LLM, cifrado, Postgres, generación de selectores, tracking de tokens) usadas por las etapas del pipeline.
- Submódulos clave: `stage01_extraction/` (Selenium + clasificación de URLs) y `stage04_extraction/` (extracción de contenido y bypass de paywalls).
- Uso: importar helpers desde aquí en stages, Celery y scripts (`from common.llm import ...`, `from common.postgres_db import PostgresDB`, etc.).
- Configuración: depende de YAML/JSON en `config/` y variables de entorno para DB, OpenAI y cookies.
- Notas: respeta las interfaces existentes; algunos módulos mantienen cachés (`xpath_cache.py`) y manejan cookies/token_usage.
