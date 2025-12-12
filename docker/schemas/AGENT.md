# Guía para agentes

- Propósito: definición del esquema de base de datos y migraciones SQL para Postgres.
- Archivos base: `schema.sql` y `schema_manual.sql` describen el estado completo; `*_migration.sql` agregan tablas/cambios incrementales.
- Carpeta `migrations/`: migraciones numeradas aplicadas en orden; sincronízalas con el código que las consume.
- Uso: al modificar el modelo de datos, genera una nueva migración aquí y referencia en los entrypoints o scripts de despliegue.
