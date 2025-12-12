-- ============================================================================
-- Stage Executions Migration: Tables for execution tracking and scheduling
-- ============================================================================

-- Tabla: scheduled_executions (schedule definitions)
CREATE TABLE IF NOT EXISTS scheduled_executions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    stage_name VARCHAR(50) NOT NULL DEFAULT '01_extract_urls',
    cron_expression VARCHAR(100) NOT NULL,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
    parameters JSONB,  -- {source_ids: [1,2,3]}
    is_enabled BOOLEAN DEFAULT true,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_run_at TIMESTAMP WITH TIME ZONE
);

-- Tabla: execution_history (execution tracking)
CREATE TABLE IF NOT EXISTS execution_history (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES scheduled_executions(id) ON DELETE SET NULL,
    execution_type VARCHAR(20) NOT NULL,  -- 'scheduled' | 'manual'
    stage_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending' | 'running' | 'completed' | 'failed'

    -- API key tracking
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
    api_key_alias VARCHAR(255),  -- Snapshot

    -- Parameters
    parameters JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Results
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,

    -- Token tracking
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    -- Costs
    cost_usd NUMERIC(10, 4) DEFAULT 0,
    cost_eur NUMERIC(10, 4) DEFAULT 0,

    -- Error handling
    error_message TEXT,
    log_file VARCHAR(500),

    -- Duration
    duration_seconds INTEGER GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER
    ) STORED
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scheduled_executions_enabled ON scheduled_executions(is_enabled);
CREATE INDEX IF NOT EXISTS idx_scheduled_executions_next_run ON scheduled_executions(last_run_at, cron_expression);
CREATE INDEX IF NOT EXISTS idx_execution_history_status ON execution_history(status);
CREATE INDEX IF NOT EXISTS idx_execution_history_created_at ON execution_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_history_api_key ON execution_history(api_key_id);
CREATE INDEX IF NOT EXISTS idx_execution_history_schedule ON execution_history(schedule_id);

-- Triggers
CREATE TRIGGER update_scheduled_executions_updated_at
    BEFORE UPDATE ON scheduled_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Verification
DO $$
DECLARE
    schedule_count INTEGER;
    execution_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO schedule_count FROM scheduled_executions;
    SELECT COUNT(*) INTO execution_count FROM execution_history;
    RAISE NOTICE 'Migration complete: % schedules, % executions', schedule_count, execution_count;
END $$;
