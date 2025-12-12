# Guía para agentes

- Propósito: implementación principal de las etapas del pipeline (`01_extract_urls` a `05_generate_newsletters`) y orquestador.
- Archivos clave: `01_extract_urls.py`, `02_filter_for_newsletters.py`, `03_ranker.py`, `04_extract_content.py`, `05_generate_newsletters.py`, `orchestrator.py` y README específicos por etapa.
- Dependencias: utilizan utilidades de `common/` y configuraciones de `config/`; el orquestador gestiona fechas y ejecución secuencial.
- Uso: correr cada etapa manualmente o vía orquestador/Celery; mantener compatibilidad con tests y scripts de reset.
