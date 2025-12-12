# Log Rotation & Cleanup Strategy

Este documento describe la estrategia de rotación de logs y limpieza de datos para evitar desbordamiento de disco.

## Resumen de Acumulación

### 📊 Ubicaciones donde se acumulan datos:

| Ubicación | Tipo | Tamaño Actual | Rotación Implementada |
|-----------|------|---------------|----------------------|
| `logs/` | Logs pipeline | ~10 MB | ✅ Automática (14 días) |
| `data/newsletters/` | Newsletters generadas | ~4 MB | ⚠️ Manual (recomendado 90 días) |
| Docker containers | Logs contenedores | ~5 MB | ✅ Configurada (10MB × 3 archivos) |
| `__pycache__/` | Cache Python | ~4 KB | ⚠️ Manual (según necesidad) |
| `old/` | Código legacy | ~26 MB | ⚠️ Revisar/eliminar |
| `poc_keyword_search/` | POC antiguo | ~3 MB | ⚠️ Revisar/eliminar |

## Rotación Automática Implementada

### 1. Logs del Pipeline Python (`logs/`)
**Ubicación**: `common/logging_utils.py`

**Configuración actual**:
- **Por archivo**: Max 20 MB por log file, 5 backups rotados
- **Por directorio**: Elimina automáticamente directorios con fecha > 14 días
- **Implementado en**: Todos los stages (01-05)

```python
setup_rotating_file_logger(
    run_date="2025-12-10",
    log_filename="01_extract_urls.log",
    max_bytes=20 * 1024 * 1024,  # 20 MB
    backup_count=5,               # 5 rotaciones
    retention_days=14,            # Borra dirs > 14 días
)
```

**Proyección**: ~1 MB/día → **~14 MB máximo** con rotación actual ✅

### 2. Docker Container Logs
**Ubicación**: `docker-compose.yml`

**Configuración actual**:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"   # Máximo 10 MB por archivo
    max-file: "3"     # Mantiene 3 archivos rotados
```

**Proyección**: Max **30 MB por contenedor** (10MB × 3 archivos) ✅

**Contenedores activos**:
- `newsletter_backend`
- `newsletter_frontend`
- `newsletter_celery_worker`
- `newsletter_celery_worker_newsletters`
- `newsletter_celery_beat`
- `newsletter_postgres`
- `newsletter_redis`
- `newsletter_cloudbeaver`

**Total máximo**: ~240 MB para todos los contenedores ✅

## Limpieza Manual Recomendada

### 1. Newsletters Generadas (`data/newsletters/`)
**Situación actual**:
- 95 archivos (JSON + MD)
- ~4 MB total
- Sin rotación automática

**Recomendación**: Eliminar archivos > 90 días

**Script**: Ver `scripts/cleanup_logs.sh` (sección 2)

### 2. Python Cache (`__pycache__/`)
**Situación actual**:
- 103 directorios
- ~4 KB total (mínimo)

**Recomendación**: Limpiar solo si crece significativamente

**Comando**:
```bash
find . -type d -name "__pycache__" -exec rm -rf {} +
```

### 3. Código Legacy (`old/`, `poc_keyword_search/`)
**Situación actual**:
- `old/`: 26 MB (archivebox_data, perfiles browser, etc.)
- `poc_keyword_search/`: 3 MB

**Recomendación**:
- **Revisar** si es necesario conservar
- **Eliminar** o **mover a backup externo** si no se usa

## Script de Limpieza Unificado

### Uso:
```bash
# Ejecutar limpieza completa
./scripts/cleanup_logs.sh

# O con sudo para limpiar logs de Docker
sudo ./scripts/cleanup_logs.sh
```

### Qué hace:
1. ✅ Elimina directorios de logs > 30 días
2. ✅ Elimina newsletters > 90 días
3. ✅ Limpia `__pycache__`
4. ℹ️ Muestra tamaño de logs Docker (requiere sudo para truncar)
5. ℹ️ Reporta directorios `old/` y `poc_keyword_search/`
6. ℹ️ Muestra uso de disco Docker

### Programar con Cron (Opcional):
```bash
# Editar crontab
crontab -e

# Ejecutar cada domingo a las 3 AM
0 3 * * 0 /home/luis.martinezb/Documents/newsletter_utils/scripts/cleanup_logs.sh >> /tmp/newsletter_cleanup.log 2>&1
```

## Punto de Alerta Detectado

### ⚠️ Log Anómalo del 28-nov
**Archivo**: `logs/2025-11-28/04_extract_content.log` (5.8 MB)

**Acción recomendada**:
1. Investigar qué causó el log tan grande:
   ```bash
   head -100 logs/2025-11-28/04_extract_content.log
   grep -i "error\|exception\|traceback" logs/2025-11-28/04_extract_content.log | head -20
   ```

2. Verificar si hubo errores repetitivos o nivel de log incorrecto (DEBUG en lugar de INFO)

## Proyecciones de Crecimiento

### Sin rotación (escenario apocalíptico):
- **Logs**: ~1 MB/día × 365 días = **365 MB/año**
- **Newsletters**: ~1.4 MB/mes × 12 meses = **~17 MB/año**
- **Docker logs**: Sin límite, **podría crecer indefinidamente** 🔥

### Con rotación actual:
- **Logs pipeline**: **~14 MB** (14 días × 1 MB) ✅
- **Newsletters**: **~12 MB** (90 días con script) ✅
- **Docker logs**: **~240 MB** (30 MB × 8 contenedores) ✅
- **Total controlado**: **~266 MB** ✅

## Monitoreo Recomendado

### Comando rápido para revisar tamaños:
```bash
echo "=== Disk Usage Summary ==="
echo "Logs:        $(du -sh logs/ 2>/dev/null | cut -f1)"
echo "Data:        $(du -sh data/ 2>/dev/null | cut -f1)"
echo "Old:         $(du -sh old/ 2>/dev/null | cut -f1)"
echo "POC:         $(du -sh poc_keyword_search/ 2>/dev/null | cut -f1)"
echo "Docker:      $(sudo du -sh /var/lib/docker/containers/ 2>/dev/null | cut -f1)"
echo "Total:       $(du -sh . 2>/dev/null | cut -f1)"
```

### Alertas a configurar (opcional):
```bash
# Alerta si logs/ > 50 MB
if [ $(du -sm logs/ | cut -f1) -gt 50 ]; then
    echo "⚠️ ALERT: logs/ directory > 50 MB"
fi

# Alerta si data/ > 100 MB
if [ $(du -sm data/ | cut -f1) -gt 100 ]; then
    echo "⚠️ ALERT: data/ directory > 100 MB"
fi
```

## Resumen de Acciones

| Acción | Prioridad | Implementación |
|--------|-----------|----------------|
| Rotación logs pipeline | ✅ Completado | `common/logging_utils.py` |
| Rotación logs Docker | ✅ Completado | `docker-compose.yml` |
| Script limpieza manual | ✅ Completado | `scripts/cleanup_logs.sh` |
| Cron job (opcional) | 🟡 Recomendado | Usuario decide |
| Revisar `old/` | 🟡 Recomendado | Eliminar si no se usa |
| Investigar log 28-nov | 🟡 Recomendado | Verificar causa raíz |

---

**Conclusión**: Sistema bien protegido contra desbordamiento. La rotación automática ya está implementada. El script de limpieza manual es un complemento para datos legacy y newsletters antiguas.
