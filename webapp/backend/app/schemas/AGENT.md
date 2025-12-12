# Guía para agentes

- Propósito: modelos Pydantic usados en las rutas de la API (entradas y respuestas).
- Archivos: esquemas por dominio (`api_keys.py`, `auth.py`, `categories.py`, `sources.py`, etc.) alineados con tablas y routers v1.
- Uso: reutiliza y extiende estos modelos al añadir endpoints; mantener validaciones y alias consistentes con el esquema SQL.
