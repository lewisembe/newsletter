# Guía para agentes

- Propósito: scripts utilitarios para migraciones, pruebas rápidas y herramientas ad-hoc del pipeline.
- Categorías: migraciones de BD (`migrate_*.py`, `convert_db_to_postgres.py`), pruebas de extracción (`test_content_extraction.py`, `test_extraction_quick.py`), herramientas de cookies/JWT (`import_cookies.py`, `generate_jwt_secret.py`), y análisis (`analyze_context_report.py`, `analyze_failures.py`).
- Documentación: ver `README.md`, `README_POC_AUTH.md`, `README_CLEAR_SUMMARIES.md` para instrucciones específicas.
- Uso: ejecuta desde la raíz con el entorno configurado; muchos scripts asumen presencia de `.env` y conexiones a Postgres/LLM.
