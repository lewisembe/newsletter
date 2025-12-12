# Legacy Files

Este directorio contiene archivos obsoletos del sistema newsletter_utils que ya no se utilizan tras la migración a PostgreSQL y la implementación del sistema de gestión de categorías.

## Archivos

### Database Files
- **`news.db`** - Base de datos SQLite original (30MB)
- **`news.db.backup.20251202`** - Backup de SQLite del 2 de diciembre 2024
- **`db_sqlite_old.py`** - Implementación original de SQLite (105KB)
- **`db.py.deprecated`** - Wrapper de compatibilidad para SQLiteURLDatabase → PostgreSQLURLDatabase

### Configuration Files
- **`categories.yml`** - Configuración de categorías (ahora en PostgreSQL)

## Migración completada

**Fecha**: 2024-12-04

### Cambios:
1. ✅ Todos los stages (01-05) y orchestrator ahora usan `PostgreSQLURLDatabase` directamente
2. ✅ Categorías migradas de YAML a tabla PostgreSQL `categories`
3. ✅ Eliminado wrapper `common/db.py` 
4. ✅ Sistema de gestión de categorías en webapp implementado

### Database actual:
- **PostgreSQL 16** en Docker (`newsletter_db`)
- Connection: `localhost:5432`
- Tablas: `urls`, `categories`, `clusters`, `ranking_runs`, `ranked_urls`, `newsletters`, `users`, etc.

## Recuperación

Si necesitas recuperar algún dato de las bases SQLite antiguas:
```bash
# Ver contenido de news.db
sqlite3 legacy/news.db ".tables"
sqlite3 legacy/news.db "SELECT COUNT(*) FROM urls;"
```

## Eliminación

Estos archivos pueden eliminarse después de verificar que todo funciona correctamente en PostgreSQL (recomendado después de 1-2 semanas de operación estable).
