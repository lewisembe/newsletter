# Guía para agentes

- Propósito: endpoints de la versión 1 de la API.
- Archivos: routers por dominio (`auth.py`, `api_keys.py`, `sources.py`, `newsletters.py`, etc.) y `router.py` que los incluye.
- Convención: cada router expone prefijos y tags coherentes; usa esquemas de `app/schemas` y lógica en servicios/DB asociados.
- Notas: mantener consistencia de dependencias de seguridad/auth para rutas protegidas.
