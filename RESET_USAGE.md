# Guía de Uso: Reset de Google Sheets

Este documento explica cómo resetear los datos del Google Sheet del Newsletter Bot.

## 🎯 ¿Qué hace el reset?

El reset limpia los datos procesados manteniendo la configuración:

### ✅ Se elimina:
- Todas las noticias procesadas (hoja "Noticias_Procesadas")
- Todos los newsletters generados (hoja "Newsletters_Generadas")

### ✅ Se conserva:
- Las fuentes configuradas (hoja "Fuentes")
- Los temas configurados (hoja "Temas")
- Los encabezados de todas las hojas

## 🖥️ Opción 1: Script de Línea de Comandos

### Uso básico

```bash
./venv/bin/python reset_sheets.py
```

### Flujo de confirmación

El script te pedirá confirmación DOS veces para evitar errores:

1. **Primera confirmación**: Escribe `SI` (en mayúsculas)
2. **Segunda confirmación**: Escribe `RESETEAR` (en mayúsculas)

### Ejemplo de ejecución

```
$ ./venv/bin/python reset_sheets.py

================================================================================
RESET GOOGLE SHEETS - NEWSLETTER BOT
================================================================================

================================================================================
⚠️  ADVERTENCIA: RESETEAR GOOGLE SHEET
================================================================================

Esta operación eliminará:
  • Todas las noticias procesadas
  • Todos los newsletters generados

Esta operación NO eliminará:
  • Las fuentes configuradas
  • Los temas configurados

================================================================================

¿Estás seguro de que deseas continuar? (escribe 'SI' para confirmar): SI

⚠️  ÚLTIMA ADVERTENCIA: Esta acción NO se puede deshacer.
Confirma nuevamente escribiendo 'RESETEAR': RESETEAR

================================================================================
Iniciando proceso de reset...
================================================================================

2025-11-05 10:30:15 - __main__ - INFO - Conectando a Google Sheets...
2025-11-05 10:30:16 - __main__ - INFO - ✓ Conectado a: Newsletter Bot Data

2025-11-05 10:30:16 - __main__ - INFO - Reseteando hoja: Noticias_Procesadas
2025-11-05 10:30:17 - __main__ - INFO -   ✓ Hoja 'Noticias_Procesadas' reseteada exitosamente (eliminadas 45 filas)
2025-11-05 10:30:17 - __main__ - INFO - Reseteando hoja: Newsletters_Generadas
2025-11-05 10:30:18 - __main__ - INFO -   ✓ Hoja 'Newsletters_Generadas' reseteada exitosamente (eliminadas 7 filas)

================================================================================
✅ RESET COMPLETADO EXITOSAMENTE
================================================================================

Hojas reseteadas: 2/2

Las siguientes hojas han sido limpiadas:
  • Noticias_Procesadas
  • Newsletters_Generadas

Las hojas de configuración (fuentes y temas) permanecen intactas.
================================================================================
```

### Cancelar el reset

Para cancelar en cualquier momento:

1. Escribe cualquier cosa diferente a `SI` o `RESETEAR`
2. O presiona `Ctrl+C`

```
¿Estás seguro de que deseas continuar? (escribe 'SI' para confirmar): no

❌ Operación cancelada.
```

## 🐍 Opción 2: Código Python

Puedes llamar las funciones de reset desde tu propio código Python.

### Reset completo (noticias + newsletters)

```python
from src.google_sheets import GoogleSheetsClient

# Inicializar cliente
client = GoogleSheetsClient()

# Reset completo (requiere confirmación explícita)
results = client.reset_all_data(confirm=True)

# Verificar resultados
if all(results.values()):
    print("✅ Todo reseteado exitosamente")
else:
    print("⚠️ Algunos resets fallaron")
    print(f"Noticias: {'✓' if results['processed_news'] else '✗'}")
    print(f"Newsletters: {'✓' if results['newsletters'] else '✗'}")
```

### Reset solo noticias procesadas

```python
from src.google_sheets import GoogleSheetsClient

client = GoogleSheetsClient()

# Resetear solo la hoja de noticias procesadas
success = client.reset_processed_news()

if success:
    print("✅ Noticias procesadas reseteadas")
else:
    print("❌ Error al resetear noticias")
```

### Reset solo newsletters

```python
from src.google_sheets import GoogleSheetsClient

client = GoogleSheetsClient()

# Resetear solo la hoja de newsletters
success = client.reset_newsletters()

if success:
    print("✅ Newsletters reseteados")
else:
    print("❌ Error al resetear newsletters")
```

### Ejemplo completo con manejo de errores

```python
#!/usr/bin/env python3
"""
Ejemplo de reset programático
"""
import logging
from src.google_sheets import GoogleSheetsClient

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_data():
    """Reset completo con manejo de errores"""
    try:
        # Conectar
        logger.info("Conectando a Google Sheets...")
        client = GoogleSheetsClient()
        logger.info(f"✓ Conectado a: {client.spreadsheet.title}")

        # Confirmar con el usuario (si es script interactivo)
        confirmacion = input("\n⚠️  ¿Resetear todos los datos? (SI/no): ")

        if confirmacion != "SI":
            logger.info("Operación cancelada")
            return

        # Ejecutar reset
        logger.info("Reseteando datos...")
        results = client.reset_all_data(confirm=True)

        # Reportar resultados
        if all(results.values()):
            logger.info("✅ Reset completado exitosamente")
        else:
            logger.warning("⚠️ Algunos resets fallaron")
            for sheet, success in results.items():
                status = "✓" if success else "✗"
                logger.info(f"  {status} {sheet}")

    except ValueError as e:
        logger.error(f"Error de validación: {e}")
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)

if __name__ == '__main__':
    reset_data()
```

## 🛡️ Seguridad

### Protección contra errores

1. **Confirmación doble**: El script CLI requiere dos confirmaciones explícitas
2. **Parámetro confirm**: El método `reset_all_data()` requiere `confirm=True`
3. **Logging detallado**: Todas las operaciones se registran en los logs
4. **Preservación de configuración**: Las hojas de fuentes y temas nunca se tocan

### Recuperación de datos

⚠️ **IMPORTANTE**: El reset es irreversible. Si necesitas los datos:

1. **Haz backup manual**: Descarga las hojas antes de resetear
2. **Duplica el sheet**: Crea una copia del Google Sheet completo
3. **Usa histórico de versiones**: Google Sheets guarda versiones anteriores

Para restaurar datos borrados accidentalmente:

1. Abre el Google Sheet
2. Ve a "Archivo" → "Historial de versiones" → "Ver historial de versiones"
3. Selecciona una versión anterior
4. Haz clic en "Restaurar esta versión"

## 📊 Casos de Uso

### Desarrollo y Testing

```bash
# Limpiar datos de prueba antes de un test real
./venv/bin/python reset_sheets.py
./venv/bin/python main.py
```

### Empezar de cero

Si quieres recomenzar la recolección de noticias sin mantener el historial:

```bash
./venv/bin/python reset_sheets.py
```

### Limpiar datos antiguos

Si has acumulado muchas noticias y quieres limpiar:

```python
from src.google_sheets import GoogleSheetsClient

client = GoogleSheetsClient()

# Ver cuántas noticias hay
news = client.get_all_processed_news()
print(f"Noticias almacenadas: {len(news)}")

# Si son demasiadas, resetear
if len(news) > 1000:
    client.reset_all_data(confirm=True)
    print("✓ Datos antiguos eliminados")
```

## 🔧 Troubleshooting

### Error: "Must explicitly confirm reset"

```python
# ❌ Incorrecto
client.reset_all_data()

# ✅ Correcto
client.reset_all_data(confirm=True)
```

### Error: "Failed to initialize Google Sheets client"

Verifica:
1. Que `config/credentials.json` existe
2. Que el Google Sheet está compartido con la service account
3. Que el `GOOGLE_SHEETS_ID` en `.env` es correcto

### El reset no elimina las hojas

El reset NO elimina las hojas completas, solo limpia su contenido (excepto los headers). Esto es intencional para mantener la estructura.

## 📝 Logs

Todos los resets se registran en `logs/newsletter_bot.log`:

```
2025-11-05 10:30:16 - src.google_sheets - WARNING - ⚠️  RESETTING ALL DATA (keeping sources and topics)
2025-11-05 10:30:16 - src.google_sheets - INFO - Resetting processed news sheet...
2025-11-05 10:30:17 - src.google_sheets - INFO - ✓ Processed news sheet reset successfully
2025-11-05 10:30:17 - src.google_sheets - INFO - Resetting newsletters sheet...
2025-11-05 10:30:18 - src.google_sheets - INFO - ✓ Newsletters sheet reset successfully
2025-11-05 10:30:18 - src.google_sheets - INFO - ✅ All data reset successfully
```

## 🤔 Preguntas Frecuentes

### ¿Puedo resetear solo una hoja?

Sí, usa los métodos individuales:

```python
client.reset_processed_news()  # Solo noticias
client.reset_newsletters()     # Solo newsletters
```

### ¿Se pueden recuperar los datos después del reset?

Solo a través del historial de versiones de Google Sheets (limitado a ~30 días).

### ¿Qué pasa con las fuentes y temas?

Nunca se tocan. El reset solo afecta datos procesados, no configuración.

### ¿Puedo automatizar el reset periódico?

Sí, puedes crear un cron job:

```bash
# Resetear el primer día de cada mes
0 0 1 * * cd /ruta/al/proyecto && echo "SI\nRESETEAR" | ./venv/bin/python reset_sheets.py
```

---

**Desarrollado con ❤️ para el Newsletter Bot**
