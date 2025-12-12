# Guía de esquema de base de datos (PostgreSQL)

- Esquema activo: Postgres definido en `docker/schemas/schema.sql` + migraciones en `docker/schemas/migrations/`.
- Conexión habitual: variables de entorno (`DATABASE_URL`) usadas por pipeline, Celery y webapp.

## Tablas principales (pipeline noticias)
- `urls`: URLs extraídas; `id`, `url` (UNIQUE), `title`, `source`, `content_type` (`contenido`/`no_contenido`), `content_subtype` (`noticia`/`otros`), `classification_method`, `rule_name`, `extracted_at`, `last_extracted_at`, `categorized_at`, `categoria_tematica`, `full_content`, `extraction_status` (`pending`/`success`/`failed`), `content_extraction_method`, `relevance_level` (1-5), `scored_at`, `scored_by_method`, `archive_url`, `word_count`, `ai_summary`, `cluster_id`, `cluster_assigned_at`, `execution_id` (FK `execution_history`).
- `ranking_runs`: ejecuciones Stage 03; `id`, `newsletter_name`, `run_date`, `ranker_method`, `categories_filter`, `articles_count`, `total_ranked`, `status`, `execution_time_seconds`, `created_at`.  
  `ranked_urls`: `ranking_run_id` → `url_id` con `rank`, `score/related_url_ids`.
- `newsletters`: resultados finales; `id`, `newsletter_name`, `run_date`, `template_name`, `output_format`, `categories`, `articles_count`, `articles_with_content`, `ranking_run_id`, `content_markdown`, `content_html`, `output_file_md/html`, `context_report_file`, `generated_at`, `total_tokens_used`, `generation_duration_seconds`, `model_*`, `generation_method`.
- `debug_reports`: métricas agregadas por newsletter/fecha (duraciones por stage, tokens, total_duration, report_json).
- `url_embeddings`, `clusters`, `clustering_runs`: soporte embeddings/clustering; `url_embeddings` guarda vectores; `clusters` mantiene centroides y tamaño; `clustering_runs` registra parámetros/estadísticas por corrida.

## Gestión de newsletters (webapp/API)
- `newsletter_configs`: configuración; `id`, `name` (UNIQUE), `display_name`, `description`, `source_ids` (INT[]), `category_ids` (INT[]), `articles_count`, `ranker_method`, `output_format`, `template_name`, `skip_paywall_check`, `related_window_days`, `is_active`, `api_key_id`, `enable_fallback`, `created_by_user_id`, timestamps.
- `newsletter_executions`: ejecuciones 2-5; `id`, `newsletter_config_id`, `run_date`, `execution_type` (manual/scheduled), `status`, `started_at`, `completed_at`, `completed_stages`, `failed_stages`, `total_urls_processed`, `total_urls_with_content`, `output_markdown_path`, `output_html_path`, `context_report_path`, `error_message`, `celery_task_id`, `execution_metadata` (JSON).
- `newsletter_stage_executions`: detalle por etapa; `id`, `newsletter_execution_id`, `stage_number`, `stage_name`, `status`, `items_processed/successful/failed`, `started_at`, `completed_at`, `duration_seconds`, `error_message`, `stage_metadata` (JSON).
- `pipeline_executions` y `pipeline_runs`: tracking legacy del orquestador por stage; estados por `newsletter_name`/`run_date`/`stage`, `last_successful_stage`, `output_file`, `error_message`.
- `scheduled_executions`: programación; `id`, `name`, `stage_name`/`execution_target`, `cron_expression`, `parameters` (JSON), `is_enabled`, `api_key_id`, `created_by_user_id`, `last_run_at`, timestamps.
- `execution_history`: corridas de Stage 01 y otros jobs; `id`, `stage_name`, `execution_type`, `status`, `api_key_id/alias`, `api_keys_used` (INT[]), `parameters`, `started_at`, `completed_at`, `total_items`, `processed_items`, `failed_items`, tokens/costs, `error_message`, `log_file`, `duration_seconds`.

## Operaciones y seguridad
- `api_keys`: claves LLM cifradas; `id`, `alias`, `encrypted_key`, `model`, `use_as_fallback`, `usage_count`, `last_used_at`, `is_active`, `notes`, `metadata`, `user_id`, `created_at/updated_at`.
- `users`: autenticación/roles; `id`, `nombre`, `email` (UNIQUE), `hashed_password`, `role` (`admin`/`user`/`enterprise`), `is_active`, `created_at/updated_at`, `last_login`.
- `system_config`: KV global; `key`, `value`, `updated_at`.
- `sources`: catálogo de fuentes; `id`, `name` (UNIQUE), `display_name`, `base_url`, `language`, `description`, `is_active`, `priority`, `notes`, timestamps.
- `categories`: taxonomía; `id` (slug), `name`, `description`, `consolidates` (JSONB), `examples` (JSONB), timestamps.
- `api`/`stage` scheduling: ver `scheduled_executions` y `execution_history` arriba.

## Cookies y scraping
- `site_cookies`: cookies por dominio (`domain`, `cookie_name`, `cookie_value`, flags, expiry, timestamps).
- `source_cookies`: cookies por fuente con metadata de validación; `source_id` FK, `domain`, `cookies` (JSONB), estado/fechas de validación, auditoría (`created_by`, `updated_by`).

## Vistas útiles
- `urls_with_cluster`: une `urls` con `clusters` para exponer nombre y tamaño de clúster.

## Referencias cruzadas
- Ver `DB_SCHEMA_OVERVIEW.md` para descripción detallada y relaciones.
- Ver `docker/schemas/schema.sql`, `schema_manual.sql` y migraciones numeradas para columnas exactas, tipos y triggers.
