-- PostgreSQL Schema for Newsletter Utils
-- Manual conversion from SQLite with proper ordering and type fixes
-- Created: 2025-12-01

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity

-- ============================================
-- CORE TABLES (created first, no foreign keys)
-- ============================================

-- URLs Table: Main article storage
CREATE TABLE urls (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT,

    -- Classification
    content_type TEXT NOT NULL CHECK(content_type IN ('contenido', 'no_contenido')),
    content_subtype TEXT CHECK(content_subtype IN ('noticia', 'otros', NULL)),
    classification_method TEXT NOT NULL CHECK(classification_method IN ('cached_url', 'regex_rule', 'heuristic', 'llm_api')),
    rule_name TEXT DEFAULT NULL,

    -- Source
    source TEXT NOT NULL,

    -- Timestamps
    extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Content extraction
    content_extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    content_extraction_method TEXT CHECK(content_extraction_method IN ('libre', 'archiver', 'fallo', NULL)),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Stage 02: Categorization
    categoria_tematica TEXT DEFAULT NULL,
    categorized_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,

    -- Stage 04: Full content
    full_content TEXT DEFAULT NULL,
    extraction_status TEXT CHECK(extraction_status IN ('success', 'failed', 'pending', NULL)),
    extraction_error TEXT DEFAULT NULL,
    word_count INTEGER DEFAULT NULL,
    archive_url TEXT DEFAULT NULL,
    ai_summary TEXT,

    -- Stage 03: Relevance scoring
    relevance_level INTEGER DEFAULT NULL CHECK(relevance_level BETWEEN 1 AND 5),
    scored_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    scored_by_method TEXT DEFAULT NULL CHECK(scored_by_method IN ('level_scoring', 'dual_subset', NULL)),

    -- Stage 01.5: Clustering
    cluster_id TEXT DEFAULT NULL,
    cluster_assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

-- Clusters Table: Semantic clustering metadata
CREATE TABLE clusters (
    id TEXT PRIMARY KEY,
    run_date TEXT NOT NULL,
    centroid_url_id INTEGER,
    article_count INTEGER NOT NULL,
    avg_similarity DOUBLE PRECISION,
    similarity_mean DOUBLE PRECISION DEFAULT 0,
    similarity_m2 DOUBLE PRECISION DEFAULT 0,
    similarity_samples INTEGER DEFAULT 0,
    cluster_name TEXT DEFAULT NULL,
    last_assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (centroid_url_id) REFERENCES urls(id)
);

-- URL Embeddings: Binary vector storage
CREATE TABLE url_embeddings (
    url_id INTEGER PRIMARY KEY,
    embedding BYTEA NOT NULL,
    dimension INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
);

-- ============================================
-- RANKING TABLES
-- ============================================

-- Ranking Runs: Stage 03 execution tracking
CREATE TABLE ranking_runs (
    id SERIAL PRIMARY KEY,
    newsletter_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ranker_method TEXT NOT NULL,
    categories_filter TEXT,
    articles_count INTEGER,
    total_ranked INTEGER,
    status TEXT CHECK(status IN ('completed', 'failed')) DEFAULT 'completed',
    execution_time_seconds DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(newsletter_name, run_date)
);

-- Ranked URLs: Top URLs for newsletters
CREATE TABLE ranked_urls (
    id SERIAL PRIMARY KEY,
    ranking_run_id INTEGER NOT NULL,
    url_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    related_url_ids TEXT DEFAULT NULL,
    FOREIGN KEY(ranking_run_id) REFERENCES ranking_runs(id),
    FOREIGN KEY(url_id) REFERENCES urls(id)
);

-- ============================================
-- NEWSLETTER TABLES
-- ============================================

-- Newsletters: Generated newsletters
CREATE TABLE newsletters (
    id SERIAL PRIMARY KEY,
    newsletter_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    template_name TEXT NOT NULL,
    output_format TEXT NOT NULL,
    categories TEXT,
    content_markdown TEXT NOT NULL,
    content_html TEXT,
    articles_count INTEGER NOT NULL,
    articles_with_content INTEGER NOT NULL,
    ranking_run_id INTEGER,
    generation_method TEXT DEFAULT '4-step',
    model_summarizer TEXT DEFAULT 'gpt-4o-mini',
    model_writer TEXT DEFAULT 'gpt-4o',
    total_tokens_used INTEGER,
    generation_duration_seconds DOUBLE PRECISION,
    output_file_md TEXT,
    output_file_html TEXT,
    context_report_file TEXT,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(newsletter_name, run_date),
    FOREIGN KEY (ranking_run_id) REFERENCES ranking_runs(id) ON DELETE SET NULL
);

-- Debug Reports: Pipeline metrics
CREATE TABLE debug_reports (
    id SERIAL PRIMARY KEY,
    newsletter_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    stage_01_duration DOUBLE PRECISION,
    stage_02_duration DOUBLE PRECISION,
    stage_03_duration DOUBLE PRECISION,
    stage_04_duration DOUBLE PRECISION,
    stage_05_duration DOUBLE PRECISION,
    total_duration DOUBLE PRECISION,
    tokens_used_stage_02 INTEGER,
    tokens_used_stage_03 INTEGER,
    tokens_used_stage_05 INTEGER,
    total_tokens INTEGER,
    report_json TEXT,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(newsletter_name, run_date)
);

-- ============================================
-- PIPELINE TABLES
-- ============================================

-- Pipeline Executions: Orchestrator replay tracking
CREATE TABLE pipeline_executions (
    id SERIAL PRIMARY KEY,
    newsletter_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    config_snapshot TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'partial', 'failed')),
    last_successful_stage INTEGER CHECK(last_successful_stage IN (1, 2, 3, 4, 5)),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    UNIQUE(newsletter_name, run_date, created_at)
);

-- Pipeline Runs: Stage execution tracking
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    newsletter_name TEXT NOT NULL,
    run_date TEXT NOT NULL,
    stage INTEGER NOT NULL CHECK(stage IN (1, 2, 3, 4, 5)),
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    output_file TEXT DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    execution_id INTEGER REFERENCES pipeline_executions(id)
);

-- Site Cookies: Cookie storage for authenticated scraping
CREATE TABLE site_cookies (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    cookie_name TEXT NOT NULL,
    cookie_value TEXT NOT NULL,
    path TEXT DEFAULT '/',
    secure BOOLEAN DEFAULT TRUE,
    http_only BOOLEAN DEFAULT FALSE,
    same_site TEXT CHECK(same_site IN ('Strict', 'Lax', 'None', NULL)),
    expiry INTEGER DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, cookie_name)
);

-- Clustering Runs: Clustering execution history
CREATE TABLE clustering_runs (
    id SERIAL PRIMARY KEY,
    run_date TEXT NOT NULL,
    model_name TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    similarity_threshold DOUBLE PRECISION NOT NULL,
    adaptive_threshold INTEGER NOT NULL,
    adaptive_k DOUBLE PRECISION,
    max_neighbors INTEGER,
    min_cluster_size INTEGER,
    config_json TEXT NOT NULL,
    urls_processed INTEGER NOT NULL,
    clusters_created INTEGER NOT NULL,
    total_clusters INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INDEXES
-- ============================================

-- URLs table indexes
CREATE UNIQUE INDEX idx_url ON urls(url);
CREATE INDEX idx_extracted_at ON urls(extracted_at);
CREATE INDEX idx_last_extracted_at ON urls(last_extracted_at);
CREATE INDEX idx_content_type ON urls(content_type);
CREATE INDEX idx_source ON urls(source);
CREATE INDEX idx_extracted_content ON urls(extracted_at, content_type);
CREATE INDEX idx_title ON urls(title);
CREATE INDEX idx_categoria_tematica ON urls(categoria_tematica);
CREATE INDEX idx_categorized_at ON urls(categorized_at);
CREATE INDEX idx_extraction_status ON urls(extraction_status);
CREATE INDEX idx_word_count ON urls(word_count);
CREATE INDEX idx_urls_relevance_level ON urls(relevance_level);
CREATE INDEX idx_urls_scored_at ON urls(scored_at);
CREATE INDEX idx_urls_scoring_method ON urls(scored_by_method);
CREATE INDEX idx_cluster_id ON urls(cluster_id);

-- Clusters table indexes
CREATE INDEX idx_clusters_run_date ON clusters(run_date);
CREATE INDEX idx_cluster_name ON clusters(cluster_name);

-- URL embeddings indexes
CREATE INDEX idx_url_embeddings_dimension ON url_embeddings(dimension);

-- Pipeline runs indexes
CREATE INDEX idx_pipeline_newsletter ON pipeline_runs(newsletter_name);
CREATE INDEX idx_pipeline_date ON pipeline_runs(run_date);
CREATE INDEX idx_pipeline_stage ON pipeline_runs(stage);
CREATE INDEX idx_pipeline_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_newsletter_date_stage ON pipeline_runs(newsletter_name, run_date, stage);

-- Site cookies indexes
CREATE INDEX idx_cookies_domain ON site_cookies(domain);
CREATE INDEX idx_cookies_expiry ON site_cookies(expiry);

-- Newsletters indexes
CREATE INDEX idx_newsletters_name ON newsletters(newsletter_name);
CREATE INDEX idx_newsletters_date ON newsletters(run_date);
CREATE INDEX idx_newsletters_ranking ON newsletters(ranking_run_id);
CREATE INDEX idx_newsletters_generated_at ON newsletters(generated_at);

-- Ranked URLs indexes
CREATE INDEX idx_ranked_urls_ranking ON ranked_urls(ranking_run_id, rank);
CREATE INDEX idx_ranked_urls_url ON ranked_urls(url_id, ranking_run_id);

-- Pipeline executions indexes
CREATE INDEX idx_pipeline_executions_lookup ON pipeline_executions(newsletter_name, run_date, status);

-- ============================================
-- TRIGGERS
-- ============================================

-- Trigger function for auto-updating timestamps
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at column
CREATE TRIGGER update_urls_timestamp
    BEFORE UPDATE ON urls
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_clusters_timestamp
    BEFORE UPDATE ON clusters
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_site_cookies_timestamp
    BEFORE UPDATE ON site_cookies
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

-- ============================================
-- VIEWS
-- ============================================

-- URLs with Cluster Information
CREATE OR REPLACE VIEW urls_with_cluster AS
SELECT
    u.id,
    u.url,
    u.title,
    u.source,
    u.content_type,
    u.content_subtype,
    u.categoria_tematica,
    u.extracted_at,
    u.last_extracted_at,
    u.cluster_id,
    u.cluster_assigned_at,
    c.cluster_name,
    c.article_count as cluster_size,
    c.avg_similarity as cluster_similarity
FROM urls u
LEFT JOIN clusters c ON u.cluster_id = c.id;

-- ============================================
-- MIGRATION COMPLETE
-- ============================================
