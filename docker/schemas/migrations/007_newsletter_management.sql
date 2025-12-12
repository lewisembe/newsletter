-- Migration 007: Newsletter Management System
-- Añade tablas para gestionar configuraciones y ejecuciones de newsletters (stages 2-5)

-- 1. Tabla de configuraciones de newsletters
CREATE TABLE IF NOT EXISTS newsletter_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    description TEXT,

    -- Configuración de fuentes y categorías
    source_ids INTEGER[] NOT NULL DEFAULT '{}',
    category_ids INTEGER[] NOT NULL DEFAULT '{}',

    -- Configuración de ranking
    articles_count INTEGER DEFAULT 20,
    ranker_method VARCHAR(50) DEFAULT 'level_scoring',

    -- Configuración de output
    output_format VARCHAR(20) DEFAULT 'markdown',
    template_name VARCHAR(100) DEFAULT 'default',

    -- Opciones avanzadas
    skip_paywall_check BOOLEAN DEFAULT false,
    related_window_days INTEGER DEFAULT 365,

    -- Metadata
    is_active BOOLEAN DEFAULT true,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_newsletter_configs_active ON newsletter_configs(is_active);
CREATE INDEX idx_newsletter_configs_name ON newsletter_configs(name);

-- Trigger para updated_at
CREATE TRIGGER update_newsletter_configs_updated_at
    BEFORE UPDATE ON newsletter_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 2. Tabla de ejecuciones de newsletters (pipelines completos)
CREATE TABLE IF NOT EXISTS newsletter_executions (
    id SERIAL PRIMARY KEY,

    -- Asociaciones
    newsletter_config_id INTEGER REFERENCES newsletter_configs(id) ON DELETE SET NULL,
    schedule_id INTEGER REFERENCES scheduled_executions(id) ON DELETE SET NULL,
    source_execution_id INTEGER REFERENCES execution_history(id) ON DELETE SET NULL,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,

    -- Tipo de ejecución
    execution_type VARCHAR(20) NOT NULL,

    -- Estado general del pipeline
    status VARCHAR(20) DEFAULT 'pending',

    -- Snapshot de configuración (auditoría)
    config_snapshot JSONB NOT NULL,

    -- Parámetros específicos
    run_date DATE NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Resultados agregados
    total_stages INTEGER DEFAULT 4,
    completed_stages INTEGER DEFAULT 0,
    failed_stages INTEGER DEFAULT 0,

    -- Métricas consolidadas
    total_urls_processed INTEGER DEFAULT 0,
    total_urls_ranked INTEGER DEFAULT 0,
    total_urls_with_content INTEGER DEFAULT 0,
    newsletter_generated BOOLEAN DEFAULT false,

    -- Tokens y costos (suma de todos los stages)
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (total_input_tokens + total_output_tokens) STORED,
    total_cost_usd NUMERIC(10,4) DEFAULT 0,
    total_cost_eur NUMERIC(10,4) DEFAULT 0,

    -- Output files
    output_markdown_path VARCHAR(500),
    output_html_path VARCHAR(500),
    context_report_path VARCHAR(500),

    -- Error tracking
    error_message TEXT,

    -- Duración
    duration_seconds INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER
    ) STORED,

    -- Celery task tracking
    celery_task_id VARCHAR(255)
);

CREATE INDEX idx_newsletter_executions_status ON newsletter_executions(status);
CREATE INDEX idx_newsletter_executions_config ON newsletter_executions(newsletter_config_id);
CREATE INDEX idx_newsletter_executions_date ON newsletter_executions(run_date DESC);
CREATE INDEX idx_newsletter_executions_schedule ON newsletter_executions(schedule_id);
CREATE INDEX idx_newsletter_executions_created ON newsletter_executions(created_at DESC);

-- 3. Tabla de ejecuciones de stages individuales (2, 3, 4, 5)
CREATE TABLE IF NOT EXISTS newsletter_stage_executions (
    id SERIAL PRIMARY KEY,

    -- Relación con pipeline
    newsletter_execution_id INTEGER NOT NULL REFERENCES newsletter_executions(id) ON DELETE CASCADE,

    -- Identificación del stage
    stage_number INTEGER NOT NULL,
    stage_name VARCHAR(50) NOT NULL,

    -- Estado
    status VARCHAR(20) DEFAULT 'pending',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Métricas específicas del stage
    items_processed INTEGER DEFAULT 0,
    items_successful INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,

    -- Tokens y costos
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cost_usd NUMERIC(10,4) DEFAULT 0,
    cost_eur NUMERIC(10,4) DEFAULT 0,

    -- Metadata específica por stage (JSON flexible)
    stage_metadata JSONB,

    -- Logs
    log_file VARCHAR(500),
    error_message TEXT,

    -- Duración
    duration_seconds INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER
    ) STORED,

    UNIQUE(newsletter_execution_id, stage_number)
);

CREATE INDEX idx_newsletter_stage_executions_pipeline ON newsletter_stage_executions(newsletter_execution_id);
CREATE INDEX idx_newsletter_stage_executions_status ON newsletter_stage_executions(status);
CREATE INDEX idx_newsletter_stage_executions_stage ON newsletter_stage_executions(stage_number, status);

-- 4. Extender tabla scheduled_executions para soportar newsletters
ALTER TABLE scheduled_executions
    ADD COLUMN IF NOT EXISTS execution_target VARCHAR(50) DEFAULT '01_extract_urls';

ALTER TABLE scheduled_executions
    ADD COLUMN IF NOT EXISTS newsletter_config_id INTEGER REFERENCES newsletter_configs(id) ON DELETE CASCADE;

-- Constraint: si es newsletter_pipeline, debe tener newsletter_config_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_newsletter_schedule'
    ) THEN
        ALTER TABLE scheduled_executions
            ADD CONSTRAINT check_newsletter_schedule
            CHECK (
                (execution_target = '01_extract_urls' AND newsletter_config_id IS NULL) OR
                (execution_target = 'newsletter_pipeline' AND newsletter_config_id IS NOT NULL)
            );
    END IF;
END $$;

-- 5. Añadir campos de lock a tabla urls para coordinación Stage 02
ALTER TABLE urls
    ADD COLUMN IF NOT EXISTS classification_lock_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS classification_lock_by VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_urls_classification_lock ON urls(classification_lock_at)
    WHERE classification_lock_at IS NOT NULL;

-- 6. Tabla de configuración del sistema
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insertar valores default
INSERT INTO system_config (key, value, description) VALUES
    ('newsletter_execution_mode', 'parallel', 'Modo de ejecución: sequential o parallel'),
    ('newsletter_max_parallel', '3', 'Máximo de newsletters en paralelo (solo en modo parallel)')
ON CONFLICT (key) DO NOTHING;

-- Trigger para updated_at
CREATE TRIGGER update_system_config_updated_at
    BEFORE UPDATE ON system_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comentarios de documentación
COMMENT ON TABLE newsletter_configs IS 'Configuraciones de newsletters (reemplaza newsletters.yml)';
COMMENT ON TABLE newsletter_executions IS 'Tracking de pipelines completos de generación (stages 2-5)';
COMMENT ON TABLE newsletter_stage_executions IS 'Tracking individual de cada stage dentro de un pipeline';
COMMENT ON TABLE system_config IS 'Configuración global del sistema (execution mode, concurrency, etc.)';

COMMENT ON COLUMN urls.classification_lock_at IS 'Timestamp de lock para evitar clasificación duplicada';
COMMENT ON COLUMN urls.classification_lock_by IS 'ID de newsletter_execution que tiene el lock';
