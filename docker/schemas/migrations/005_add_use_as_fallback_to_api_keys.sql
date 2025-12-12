-- Migration: Add use_as_fallback field to api_keys table
-- Created: 2025-12-05
-- Description: Allows API keys to be marked as fallback credentials

-- Add use_as_fallback column (default TRUE for backward compatibility)
ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS use_as_fallback BOOLEAN NOT NULL DEFAULT TRUE;

-- Create index for efficient fallback key lookup
CREATE INDEX IF NOT EXISTS idx_api_keys_use_as_fallback
ON api_keys(use_as_fallback)
WHERE is_active = TRUE;

-- Add comment
COMMENT ON COLUMN api_keys.use_as_fallback IS 'Whether this API key can be used as fallback when primary key runs out of credits';
