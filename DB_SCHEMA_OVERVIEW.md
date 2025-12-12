# Database Overview

Guía rápida de las tablas principales y su rol en el pipeline de newsletters.

## Contenido y clasificación
- `urls`: URLs extraídas en Stage 01 (`content_type`, `categoria_tematica`, `content_subtype`, `extracted_at`, `source`). Se actualiza en Stage 02.
- `sources`: fuentes configuradas (`name`, `display_name`, `base_url`, `language`, `is_active`, `priority`, `notes`).
- `categories`: categorías temáticas disponibles (`id`/slug, `name`, `description`, `examples`). Usadas por Stage 02.
- `reclassification_jobs`: tracking de jobs de reclasificación de categorías.
- `url_embeddings` / `clusters` / `clustering_runs`: soporte de clustering y embeddings (limpieza masiva, stats).

## Pipeline histórico (legacy orchestrator)
- `pipeline_runs`: ejecuciones por stage (1-5) del orquestador antiguo; columnas clave `newsletter_name`, `run_date`, `stage`, `status`, `started_at`, `completed_at`, `output_file`, `error_message`.
- `pipeline_executions`: ejecuciones completas del orquestador (agrupa varios `pipeline_runs`); `newsletter_name`, `run_date`, `status`, `config_snapshot`, `last_successful_stage`, `created_at`, `completed_at`.

## Pipeline actual (newsletters)
- `newsletter_executions`: ejecuciones del pipeline 2-5 lanzadas vía API/web; `newsletter_config_id`, `run_date`, `execution_type`, `status`, `started_at`, `completed_at`, `completed_stages`, `failed_stages`, `total_urls_*`, `output_markdown_path`, `output_html_path`, `context_report_path`, `error_message`, `celery_task_id`.
- `newsletter_stage_executions`: detalle por stage (2-5) para cada `newsletter_execution` (`stage_number`, `stage_name`, `status`, `items_processed`, `items_successful`, `items_failed`, `started_at`, `completed_at`, `duration_seconds`, `error_message`, `stage_metadata`).
- `ranking_runs` y `ranked_urls`: rankings generados en Stage 03 (`ranking_runs` tiene `newsletter_name`, `run_date`, `ranker_method`; `ranked_urls` vincula `ranking_run_id` con URLs y su score/posición).
- `newsletters`: resultado final generado en Stage 05 (`newsletter_name`, `run_date`, `template_name`, `output_format`, `articles_count`, `articles_with_content`, `ranking_run_id`, `content_markdown`, `content_html`, `output_file_md`, `output_file_html`, `context_report_file`, `generated_at`, `total_tokens_used`, `generation_duration_seconds`).

## Configuración y gestión
- `newsletter_configs`: configuración de cada newsletter (fuentes, categorías, templates, límites de artículos, etc.).
- `scheduled_executions`: programaciones CRON (newsletter_pipeline, stage_01, etc.), con `cron_expression`, `is_enabled`, `last_run_at`, `execution_target`, `parameters`.
- `execution_history`: histórico de Stage 01 y otros jobs (status, `stage_name`, `schedule_id`, `started_at`, `completed_at`, `error_message`, `duration_seconds`).
- `system_config`: pares clave/valor para ajustes globales (modo de ejecución, paralelismo, etc.).
- `api_keys`: claves OpenAI encriptadas (`alias`, `encrypted_key`, `use_as_fallback`, `usage_count`, `last_used_at`, `is_active`).
- `users`: autenticación/roles (`nombre`, `email`, `role`, `is_active`, `created_at`, `last_login`).
- `cookies`: cookies de scraping por dominio (`cookie_json`, `status`, `created_at`, `updated_at`).

## Notas operativas
- `newsletter_executions` y `newsletter_stage_executions` son las que ves en el panel web para ejecuciones manuales/programadas.
- `newsletters` guarda el contenido final; `output_file_md` apunta al archivo en `data/newsletters/`.
- `ranking_runs` y `ranked_urls` permiten reutilizar rankings sin recalcular si no usas `--force`.
- El pipeline actual usa Postgres; `DATABASE.md` contiene el detalle extendido de columnas y ejemplos.
