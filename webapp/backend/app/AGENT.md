# Guía para agentes

- Propósito: núcleo de la API FastAPI.
- Estructura: `main.py` crea la app; `api/` define routers; `auth/` gestiona autenticación; `schemas/` define Pydantic models; `utils/` ofrece helpers comunes.
- Uso: cualquier endpoint nuevo debe registrarse en `api/__init__.py`/routers y usar esquemas validados.
- Configuración: valores cargados desde variables de entorno en `config.py` (DB, JWT, CORS, etc.).
