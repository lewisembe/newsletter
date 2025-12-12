-- Migration: Add execution_id column to urls table
-- This allows tracking which execution extracted each URL

-- Add execution_id column (nullable for existing data)
ALTER TABLE urls
ADD COLUMN execution_id INTEGER REFERENCES execution_history(id) ON DELETE SET NULL;

-- Create index for efficient lookups
CREATE INDEX idx_urls_execution_id ON urls(execution_id);

-- Add comment
COMMENT ON COLUMN urls.execution_id IS 'FK to execution_history - tracks which execution extracted this URL';
