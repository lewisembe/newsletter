# Guía para agentes

- Propósito: lógica central para búsquedas de Google News y persistencia de keywords.
- Módulo principal: `google_news_searcher.py` gestiona queries, parseo y escritura en la BD SQLite configurada.
- Uso: importado por scripts en la raíz; al extender funcionalidad, mantener la API pública (`GoogleNewsSearcher` y helpers) estable.
- Dependencias: lee `config.yml` y espera tablas creadas por las migraciones de `poc_news.db`.
