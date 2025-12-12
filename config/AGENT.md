# Guía para agentes

- Propósito: configuraciones en YAML/JSON para fuentes, categorías, newsletters y reglas de scraping/validación.
- Archivos clave: `sources.yml` (selectores y URLs), `newsletters.yml` (config de envío/contenido), `url_classification_rules.yml`, `xpath_cache.yml` y `cookies_ft.json` (credenciales de FT, mantener privado).
- Uso: las etapas y scripts cargan estos archivos directamente; preservar esquemas y campos esperados.
- Notas: evita subir secretos; respeta comentarios/orden porque algunos scripts hacen lecturas por clave.
