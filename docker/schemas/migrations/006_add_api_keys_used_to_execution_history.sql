-- Migration: Add API keys tracking to execution_history table
-- Created: 2025-12-05
-- Description: Track which API keys were used during execution (including fallbacks)

-- Add column to store JSON array of API key IDs used (primary + fallbacks)
ALTER TABLE execution_history
ADD COLUMN IF NOT EXISTS api_keys_used INTEGER[] DEFAULT NULL;

-- Add comment
COMMENT ON COLUMN execution_history.api_keys_used IS 'Array of API key IDs used during execution (first=primary, rest=fallbacks)';

-- Create index for querying by API keys used
CREATE INDEX IF NOT EXISTS idx_execution_history_api_keys_used
ON execution_history USING GIN (api_keys_used);
