-- Prompt and model management schema (v1 draft)
-- This DDL creates tables to manage LLM prompts, templates, models, and usage routing.

-- Extension needed for gen_random_uuid (enable if not already)
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias TEXT UNIQUE NOT NULL,              -- e.g., MODEL_URL_FILTER
    provider TEXT NOT NULL,                  -- openai, anthropic, etc.
    model_name TEXT NOT NULL,                -- gpt-4o-mini
    purpose TEXT NOT NULL,                   -- url_filter, classifier, ranker, paywall, completeness, selector, newsletter
    max_tokens INT,
    cost_metadata JSONB,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,               -- slug: filter_news_urls, rank_batch
    stage TEXT NOT NULL,                     -- '01'...'05' or 'general'
    operation TEXT NOT NULL,                 -- filter_news_urls, classify_thematic_batch, etc.
    scope TEXT NOT NULL,                     -- system, user_template, composite
    system_prompt TEXT,
    user_prompt_template TEXT,
    placeholders JSONB DEFAULT '[]',
    response_format JSONB,                   -- expected JSON schema or format descriptor
    default_model TEXT,                      -- FK by alias to models.alias
    temperature NUMERIC,
    max_tokens INT,
    batch_size INT,
    version INT DEFAULT 1,
    status TEXT DEFAULT 'approved' CHECK (status IN ('draft','approved','archived')),
    notes TEXT,
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prompt_usages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage TEXT NOT NULL,
    operation TEXT NOT NULL,
    prompt_id UUID REFERENCES llm_prompts(id),
    model_override TEXT,
    temperature_override NUMERIC,
    max_tokens_override INT,
    batch_size_override INT,
    enabled BOOLEAN DEFAULT TRUE,
    UNIQUE(stage, operation)
);

CREATE TABLE IF NOT EXISTS prompt_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,               -- thematic_categories, content_types_level1, etc.
    items JSONB NOT NULL,                    -- array of objects with id, name, description, examples
    version INT DEFAULT 1,
    status TEXT DEFAULT 'approved' CHECK (status IN ('draft','approved','archived')),
    notes TEXT,
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS newsletter_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,               -- default, concise, tech_focus, etc.
    description TEXT,
    system_prompt TEXT,
    user_prompt_template TEXT,
    placeholders JSONB DEFAULT '[]',         -- ["date","newsletter_name","context"]
    default_model TEXT,
    temperature NUMERIC,
    max_tokens INT,
    version INT DEFAULT 1,
    status TEXT DEFAULT 'approved' CHECK (status IN ('draft','approved','archived')),
    notes TEXT,
    created_by TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prompt_params (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID REFERENCES llm_prompts(id),
    key TEXT NOT NULL,                       -- sample_payload, schema_json, guardrails, etc.
    value JSONB NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,               -- prompt|template|category|model
    entity_id UUID NOT NULL,
    version INT,
    diff JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);
