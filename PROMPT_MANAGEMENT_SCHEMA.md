## Prompt management schema (propuesta v1)

Este archivo describe el esquema SQL añadido en `db/prompt_management_schema.sql` para gestionar prompts, plantillas y modelos LLM vía base de datos y panel admin.

### Tablas clave
- **models**: catálogo de modelos (alias env, proveedor, nombre de modelo, propósito, límites).
- **llm_prompts**: prompts por stage/operation con system/user template, placeholders, response_format, sampling params, versionado y estado.
- **prompt_usages**: ruteo Stage→Operation→Prompt con overrides de modelo/params.
- **prompt_categories**: ontologías/listas (categorías temáticas, content_types, reglas) versionadas.
- **newsletter_templates**: plantillas de newsletters (Stage 05) con system/user template, placeholders y sampling params.
- **prompt_params**: key/value adicionales por prompt (payload de prueba, schemas, guardrails).
- **audit_logs**: historial de cambios (opcional) con diffs y versión.

### Notas de implementación
- La DDL usa `gen_random_uuid()`. Si la instancia no tiene `pgcrypto`, habilitar con `CREATE EXTENSION IF NOT EXISTS "pgcrypto";`.
- `response_format` se espera JSON con el schema/descriptor de salida para validación en UI.
- `placeholders` en prompts/plantillas debe listar las llaves permitidas para validación de runtime/UI.
- Versionado: `status` (`draft|approved|archived`) + `version` por fila. Publicar = incrementar versión; rollback = reactivar versión previa.

### Próximos pasos recomendados
1) Crear migración aplicando `db/prompt_management_schema.sql`.
2) Sembrar v1 con los prompts actuales (`common/llm.py`, `stage01_extraction/url_classifier.py`, `selector_generator`, `stages/03_ranker.py`, `stage04` validators, `templates/prompts/*.json`, `config/categories.yml`).
3) Implementar loaders para leer desde DB con fallback a archivos/env.
4) Construir UI admin por pestañas de stage, validando schemas y placeholders, con test en vivo contra el LLM.
