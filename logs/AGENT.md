# Guía para agentes

- Propósito: almacenamiento de logs diarios por fecha (carpetas `YYYY-MM-DD`) y métricas como `token_usage.csv`.
- Convenciones: cada stage escribe su propio archivo dentro de la carpeta del día; scripts de análisis esperan este patrón.
- Uso: no editar manualmente los logs salvo para depurar; si necesitas limpiar, usa scripts de reset del proyecto.
- Privacidad: los logs pueden contener URLs y resultados de LLM; maneja con cuidado antes de compartir.
