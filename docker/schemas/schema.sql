-- PostgreSQL Schema Migration
-- Migrated from SQLite database: data/news.db
-- Generated: /home/luis.martinezb/Documents/newsletter_utils/docker/schemas/schema.sql
-- 
-- This schema creates all tables, indexes, triggers, and views
-- for the newsletter pipeline application.
--

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity

-- ============================================
-- TABLES
-- ============================================

-- Table: clustering_runs
CREATE TABLE clustering_runs (
                    id SERIAL PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    similarity_threshold REAL NOT NULL,
                    adaptive_threshold INTEGER NOT NULL,
                    adaptive_k REAL,
                    max_neighbors INTEGER,
                    min_cluster_size INTEGER,
                    config_json TEXT NOT NULL,
                    urls_processed INTEGER NOT NULL,
                    clusters_created INTEGER NOT NULL,
                    total_clusters INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

-- Table: clusters
CREATE TABLE clusters (
            id TEXT PRIMARY KEY,
            run_date TEXT NOT NULL,
            centroid_url_id INTEGER,
            article_count INTEGER NOT NULL,
            avg_similarity REAL,
            similarity_mean REAL DEFAULT 0,
            similarity_m2 REAL DEFAULT 0,
            similarity_samples INTEGER DEFAULT 0,
            last_assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP, cluster_name TEXT DEFAULT NULL,
            FOREIGN KEY (centroid_url_id) REFERENCES urls(id)
        );

-- Table: debug_reports
CREATE TABLE debug_reports (
                id SERIAL PRIMARY KEY,
                newsletter_name TEXT NOT NULL,
                run_date TEXT NOT NULL,
                stage_01_duration REAL,
                stage_02_duration REAL,
                stage_03_duration REAL,
                stage_04_duration REAL,
                stage_05_duration REAL,
                total_duration REAL,
                tokens_used_stage_02 INTEGER,
                tokens_used_stage_03 INTEGER,
                tokens_used_stage_05 INTEGER,
                total_tokens INTEGER,
                report_json TEXT,
                generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(newsletter_name, run_date)
            );

-- Table: newsletters
CREATE TABLE newsletters (
            id SERIAL PRIMARY KEY,

            -- Identificación
            newsletter_name TEXT NOT NULL,
            run_date TEXT NOT NULL,

            -- Configuración
            template_name TEXT NOT NULL,
            output_format TEXT NOT NULL,
            categories TEXT,

            -- Contenido
            content_markdown TEXT NOT NULL,
            content_html TEXT,

            -- Metadata de generación
            articles_count INTEGER NOT NULL,
            articles_with_content INTEGER NOT NULL,

            -- Execution tracking
            ranking_run_id INTEGER,
            generation_method TEXT DEFAULT '4-step',
            model_summarizer TEXT DEFAULT 'gpt-4o-mini',
            model_writer TEXT DEFAULT 'gpt-4o',

            -- Performance
            total_tokens_used INTEGER,
            generation_duration_seconds REAL,

            -- Files
            output_file_md TEXT,
            output_file_html TEXT,
            context_report_file TEXT,

            -- Timestamps
            generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

            -- Constraints
            UNIQUE(newsletter_name, run_date),
            FOREIGN KEY (ranking_run_id) REFERENCES ranking_runs(id) ON DELETE SET NULL
        );

-- Table: pipeline_executions
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

-- Table: pipeline_runs
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
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                , execution_id INTEGER REFERENCES pipeline_executions(id));

-- Table: ranked_urls
CREATE TABLE "ranked_urls" (
            id SERIAL PRIMARY KEY,
            ranking_run_id INTEGER NOT NULL,
            url_id INTEGER NOT NULL,
            rank INTEGER NOT NULL, related_url_ids TEXT DEFAULT NULL,
            FOREIGN KEY(ranking_run_id) REFERENCES ranking_runs(id),
            FOREIGN KEY(url_id) REFERENCES urls(id)
        );

-- Table: ranking_runs
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
                execution_time_seconds REAL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(newsletter_name, run_date)
            );

-- Table: site_cookies
CREATE TABLE site_cookies (
                    id SERIAL PRIMARY KEY,
                    domain TEXT NOT NULL,
                    cookie_name TEXT NOT NULL,
                    cookie_value TEXT NOT NULL,
                    path TEXT DEFAULT '/',
                    secure BOOLEAN DEFAULT 1,
                    http_only BOOLEAN DEFAULT 0,
                    same_site TEXT CHECK(same_site IN ('Strict', 'Lax', 'None', NULL)),
                    expiry INTEGER DEFAULT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(domain, cookie_name)
                );

-- Table: url_embeddings
CREATE TABLE url_embeddings (
            url_id INTEGER PRIMARY KEY,
            embedding BYTEA NOT NULL,
            dimension INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
        );

-- Table: urls
CREATE TABLE "urls" (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT,

    -- Classification (Nivel 1)
    content_type TEXT NOT NULL CHECK(content_type IN ('contenido', 'no_contenido')),

    -- Classification (Nivel 2, opcional)
    content_subtype TEXT CHECK(content_subtype IN ('noticia', 'otros', NULL)),

    -- Classification metadata
    classification_method TEXT NOT NULL CHECK(classification_method IN ('cached_url', 'regex_rule', 'heuristic', 'llm_api')),
    rule_name TEXT DEFAULT NULL,

    -- Source
    source TEXT NOT NULL,

    -- Timestamps (ISO 8601 UTC)
    extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Content extraction tracking (Stage 04)
    content_extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    content_extraction_method TEXT CHECK(content_extraction_method IN ('libre', 'archiver', 'fallo', NULL)),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
, categoria_tematica TEXT DEFAULT NULL, categorized_at TIMESTAMP WITH TIME ZONE DEFAULT NULL, full_content TEXT DEFAULT NULL, extraction_status TEXT CHECK(extraction_status IN ('success', 'failed', 'pending', NULL)), extraction_error TEXT DEFAULT NULL, word_count INTEGER DEFAULT NULL, archive_url TEXT DEFAULT NULL, ai_summary TEXT, relevance_level INTEGER DEFAULT NULL CHECK(relevance_level BETWEEN 1 AND 5), scored_at TIMESTAMP WITH TIME ZONE DEFAULT NULL, scored_by_method TEXT DEFAULT NULL CHECK(scored_by_method IN ('level_scoring', 'dual_subset', NULL)), cluster_id TEXT DEFAULT NULL, cluster_assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NULL);


-- ============================================
-- INDEXES
-- ============================================

-- Index: idx_categoria_tematica
CREATE INDEX idx_categoria_tematica ON urls(categoria_tematica);

-- Index: idx_categorized_at
CREATE INDEX idx_categorized_at ON urls(categorized_at);

-- Index: idx_cluster_id
CREATE INDEX idx_cluster_id ON urls(cluster_id);

-- Index: idx_cluster_name
CREATE INDEX idx_cluster_name ON clusters(cluster_name);

-- Index: idx_clusters_run_date
CREATE INDEX idx_clusters_run_date ON clusters(run_date);

-- Index: idx_content_type
CREATE INDEX idx_content_type ON urls(content_type);

-- Index: idx_cookies_domain
CREATE INDEX idx_cookies_domain ON site_cookies(domain);

-- Index: idx_cookies_expiry
CREATE INDEX idx_cookies_expiry ON site_cookies(expiry);

-- Index: idx_extracted_at
CREATE INDEX idx_extracted_at ON urls(extracted_at);

-- Index: idx_extracted_content
CREATE INDEX idx_extracted_content ON urls(extracted_at, content_type);

-- Index: idx_extraction_status
CREATE INDEX idx_extraction_status ON urls(extraction_status);

-- Index: idx_last_extracted_at
CREATE INDEX idx_last_extracted_at ON urls(last_extracted_at);

-- Index: idx_newsletters_date
CREATE INDEX idx_newsletters_date ON newsletters(run_date);

-- Index: idx_newsletters_generated_at
CREATE INDEX idx_newsletters_generated_at ON newsletters(generated_at);

-- Index: idx_newsletters_name
CREATE INDEX idx_newsletters_name ON newsletters(newsletter_name);

-- Index: idx_newsletters_ranking
CREATE INDEX idx_newsletters_ranking ON newsletters(ranking_run_id);

-- Index: idx_pipeline_date
CREATE INDEX idx_pipeline_date ON pipeline_runs(run_date);

-- Index: idx_pipeline_executions_lookup
CREATE INDEX idx_pipeline_executions_lookup
        ON pipeline_executions(newsletter_name, run_date, status)
    ;

-- Index: idx_pipeline_newsletter
CREATE INDEX idx_pipeline_newsletter ON pipeline_runs(newsletter_name);

-- Index: idx_pipeline_newsletter_date_stage
CREATE INDEX idx_pipeline_newsletter_date_stage ON pipeline_runs(newsletter_name, run_date, stage);

-- Index: idx_pipeline_stage
CREATE INDEX idx_pipeline_stage ON pipeline_runs(stage);

-- Index: idx_pipeline_status
CREATE INDEX idx_pipeline_status ON pipeline_runs(status);

-- Index: idx_ranked_urls_ranking
CREATE INDEX idx_ranked_urls_ranking ON ranked_urls(ranking_run_id, rank);

-- Index: idx_ranked_urls_url
CREATE INDEX idx_ranked_urls_url ON ranked_urls(url_id, ranking_run_id);

-- Index: idx_source
CREATE INDEX idx_source ON urls(source);

-- Index: idx_title
CREATE INDEX idx_title ON urls(title);

-- Index: idx_url
CREATE UNIQUE INDEX idx_url ON urls(url);

-- Index: idx_url_embeddings_dimension
CREATE INDEX idx_url_embeddings_dimension ON url_embeddings(dimension);

-- Index: idx_urls_category
CREATE INDEX idx_urls_category
            ON urls(categoria_tematica)
        ;

-- Index: idx_urls_content_type
CREATE INDEX idx_urls_content_type
            ON urls(content_type)
        ;

-- Index: idx_urls_date
CREATE INDEX idx_urls_date
            ON urls(last_extracted_at)
        ;

-- Index: idx_urls_extraction_status
CREATE INDEX idx_urls_extraction_status
            ON urls(extraction_status)
        ;

-- Index: idx_urls_relevance_level
CREATE INDEX idx_urls_relevance_level ON urls(relevance_level);

-- Index: idx_urls_scored_at
CREATE INDEX idx_urls_scored_at ON urls(scored_at);

-- Index: idx_urls_scoring_method
CREATE INDEX idx_urls_scoring_method ON urls(scored_by_method);

-- Index: idx_word_count
CREATE INDEX idx_word_count ON urls(word_count);


-- ============================================
-- TRIGGERS
-- ============================================


-- PostgreSQL Trigger Functions
-- These replace SQLite's AFTER UPDATE triggers for auto-updating timestamps

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply timestamp trigger to tables with updated_at column
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


-- URLs with Cluster Information (read-only view)
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
-- 
-- To apply this schema to PostgreSQL:
-- docker-compose exec -T postgres psql -U newsletter_user newsletter_db < docker/schemas/schema.sql
--
