# Guía para agentes

- Propósito: herramientas de la etapa 04 para extraer contenido completo, manejar paywalls y validar artículos.
- Componentes: `authenticated_scraper.py`, `cookie_manager.py` y `paywall_bypass.py` gestionan cookies/sesiones; `extractors.py` y `fetch_cascade.py` intentan múltiples estrategias de descarga; `content_cleaner.py` y `content_validator.py` higienizan/verifican texto.
- Cache: `xpath_cache.py` y `archive_fetcher.py` ayudan a reutilizar selectores y fuentes de archivo.
- Uso: invocado por `stages/04_extract_content.py`; cualquier cambio debe mantener compatibilidad con orquestador y scripts de test.
