-- Enable required extensions for PostgreSQL
-- This script runs automatically when PostgreSQL container initializes

-- pg_trgm: For text similarity search and fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL extensions initialized successfully';
END $$;
