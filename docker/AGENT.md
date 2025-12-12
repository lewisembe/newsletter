# Guía para agentes

- Propósito: infraestructura Docker para workers, DB y Nginx.
- Archivos clave: `Dockerfile.celery` para worker de Celery, `README.md` con instrucciones, `schemas/` con SQL y `init-scripts/` con inicialización de extensiones.
- Nginx: configs en `nginx/` (incluye stub de SSL) usadas por la webapp.
- Uso: `docker-compose.yml` en la raíz referencia estos assets; mantén rutas y nombres sincronizados.
- Notas: al añadir servicios/migraciones, actualiza también scripts de arranque y documentación.
