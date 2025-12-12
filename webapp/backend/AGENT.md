# Guía para agentes

- Propósito: API backend (FastAPI) para gestionar newsletters, autenticación y acceso a datos.
- Estructura: `app/` contiene `main.py`, rutas en `api/`, autenticación en `auth/`, esquemas en `schemas/` y utilidades; `Dockerfile` y `requirements.txt` definen el entorno.
- Configuración: lee variables de entorno para DB/secretos; coordina con el esquema SQL de `docker/schemas`.
- Uso: ejecutar con `uvicorn app.main:app --reload` desde este directorio o levantar via Docker.
- JWT: al rotar `JWT_SECRET_KEY`, **antes de cambiarla** registra la clave vigente en la tabla `jwt_secret_history` (cifrada con `ENCRYPTION_KEY`). El backend ya lo hace en `ensure_current_secret_logged`, pero si editas claves manualmente asegúrate de que la clave anterior quede guardada para validar tokens existentes.
