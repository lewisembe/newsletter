# Guía para agentes

- Propósito: migraciones incrementales aplicadas sobre el esquema principal de Postgres.
- Convención: prefijo numérico (`003_...`) marca el orden; cada archivo es idempotente en entornos nuevos si se aplican en secuencia.
- Uso: crear nuevas migraciones con el siguiente número disponible y documentar cambios (columnas, índices, tablas). Evita editar migraciones ya aplicadas en producción.
