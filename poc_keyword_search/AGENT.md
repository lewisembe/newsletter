# Guía para agentes

- Propósito: POC para buscar URLs por temas/keywords (Google News + base SQLite) y mantener un histórico de búsquedas.
- Entrypoints: `01_search_urls_by_topic.py`, scripts de migración (`migrate_*.py`) y `init_poc_db.py` para preparar la BD.
- Directorios: `data/` almacena SQLite, `logs/` agrupa salidas, `src/` contiene el buscador (`google_news_searcher.py`). Documentación adicional en `README.md` y `MIGRATION_SUMMARY.md`.
- Uso: ajusta parámetros en `config.yml`; tests rápidos en `test_improvements.py`.
