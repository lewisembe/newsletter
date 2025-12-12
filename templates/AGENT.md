# Guía para agentes

- Propósito: plantillas usadas para prompts de LLM y formatos de salida de newsletters.
- Estructura: `prompts/` contiene JSON con roles/estilos; `outputs/` guarda ejemplos base (`newsletter.html`, `newsletter.md`).
- Uso: los stages cargan estas plantillas para generar resúmenes y boletines; mantener claves y placeholders intactos.
- Nota: al agregar variaciones, documenta en el nombre del archivo y sincroniza con configuraciones en `config/llm.yaml` o stages.
