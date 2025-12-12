# Guía para agentes

- Propósito: utilidades y dependencias de autenticación para el backend (JWT, seguridad de rutas).
- Archivos: `dependencies.py` declara dependencias FastAPI para proteger endpoints; `utils.py` maneja generación/validación de tokens y hashing.
- Uso: reutiliza estas funciones al crear nuevas rutas protegidas; mantiene consistencia con configuraciones en `config.py`.
