# Guía para agentes

- Propósito: definiciones de tareas Celery para stages y scheduler.
- Archivos: `stage01_tasks.py` ejecuta extracción de URLs; `scheduler_tasks.py` programa corridas; `newsletter_tasks.py` maneja generación/envío. `*.bak` conserva versiones previas.
- Uso: importados por el worker en `celery_app/__init__.py`; mantén nombres de tareas y argumentos para compatibilidad con orquestador y Celery beat.
