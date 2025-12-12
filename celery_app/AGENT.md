# Guía para agentes

- Propósito: tareas Celery que ejecutan etapas del pipeline de newsletters de forma asíncrona.
- Archivos clave: `tasks/*.py` define jobs (stage01, scheduler, generación de newsletters); `utils/` aporta selección de API keys y cálculo de costes.
- Entrypoint típico: `celery -A celery_app.tasks worker --loglevel=info` (ver docker-compose para valores reales).
- Dependencias: usa módulos de `common` y las configuraciones de `config/`; asegúrate de tener variables de entorno (DB, OpenAI, Redis) cargadas.
- Nota: algunos archivos `.bak` guardan versiones previas de tareas; úsalos solo como referencia.
