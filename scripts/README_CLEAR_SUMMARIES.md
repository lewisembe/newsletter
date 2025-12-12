# Clear Summaries Script

Script para limpiar los resúmenes de artículos cacheados en la base de datos.

## Uso

```bash
# Ver cuántos resúmenes hay (dry-run)
venv/bin/python scripts/clear_summaries.py --dry-run

# Limpiar todos los resúmenes
venv/bin/python scripts/clear_summaries.py

# Limpiar resúmenes de otra base de datos
venv/bin/python scripts/clear_summaries.py --db-path path/to/other.db
```

## ¿Cuándo usar este script?

- **Después de cambios en el formato de resúmenes** (como la migración a JSON estructurado)
- **Para forzar regeneración de todos los resúmenes** con nueva versión del prompt
- **Para liberar espacio en DB** (aunque los resúmenes son pequeños)

## Seguridad

- ✅ Pide confirmación antes de borrar
- ✅ Soporta `--dry-run` para ver qué se borraría sin hacer cambios
- ✅ No afecta el contenido de los artículos, solo los resúmenes cacheados

## Regeneración automática

Después de limpiar los resúmenes:

1. Los resúmenes se regenerarán automáticamente cuando Stage 05 se ejecute
2. Se cachearán en el nuevo formato JSON estructurado
3. Solo se genera el resumen una vez por artículo (se reutiliza en futuras ejecuciones)

## Ejemplo

```bash
$ venv/bin/python scripts/clear_summaries.py --dry-run
Found 42 articles with cached summaries

[DRY RUN] Would clear all summaries, but --dry-run flag is set

$ venv/bin/python scripts/clear_summaries.py
Found 42 articles with cached summaries

Are you sure you want to clear 42 summaries? (yes/no): yes
✓ Cleared 42 summaries successfully

Summaries will be regenerated with JSON format when Stage 05 runs again.
```
