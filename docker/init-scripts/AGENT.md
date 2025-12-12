# Guía para agentes

- Contenido: scripts SQL ejecutados al inicializar el contenedor de Postgres.
- Actual: `01_extensions.sql` habilita extensiones necesarias (p.ej., `uuid-ossp`).
- Uso: cualquier nueva dependencia de extensión debe añadirse aquí para entornos dockerizados.
- Nota: mantener orden numérico para que los entrypoints de Postgres los apliquen secuencialmente.
