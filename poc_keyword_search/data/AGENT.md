# Guía para agentes

- Contenido: bases SQLite (`poc_news*.db`) usadas por el POC de búsqueda por keywords.
- Uso: `poc_news.db` es la activa; los backups (`*_backup_*`, `*_test`) sirven para restaurar o probar migraciones.
- Precaución: evita editar directamente; usa scripts de migración o los helpers de `src/`.
