# Guía para agentes

- Propósito: routers de FastAPI agrupados por versión.
- Organización: carpeta `v1/` contiene routers separados por recurso (auth, api_keys, categories, newsletters, etc.) y `router.py` los agrega.
- Uso: añadir nuevas rutas en `v1/` y registrarlas en el router versionado para exponerlas en `main.py`.
