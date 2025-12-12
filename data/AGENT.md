# Guía para agentes

- Propósito: almacenamiento de datos del pipeline (bases SQLite/CSV procesados).
- Estructura: `news.db` es la BD principal; `newsletters/`, `processed/` y `debug/` guardan salidas por etapa o depuración.
- Prácticas: no versionar datasets sensibles; respeta nombres `urls_YYYY-MM-DD` y estructuras esperadas por stages/tests.
- Seguridad: verifica permisos antes de borrar/reescribir; algunos scripts resetean etapas y limpian aquí.
