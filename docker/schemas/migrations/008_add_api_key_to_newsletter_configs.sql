-- Migration 008: Add API key support to newsletter_configs
-- This allows newsletters to use specific API keys with fallback support

-- Add api_key_id column (nullable, references api_keys table)
ALTER TABLE newsletter_configs
ADD COLUMN api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL;

-- Add enable_fallback column (defaults to true)
ALTER TABLE newsletter_configs
ADD COLUMN enable_fallback BOOLEAN DEFAULT true;

-- Create index for API key lookups
CREATE INDEX idx_newsletter_configs_api_key_id ON newsletter_configs(api_key_id);

-- Add comment
COMMENT ON COLUMN newsletter_configs.api_key_id IS 'Primary API key to use for this newsletter (with fallback support if enable_fallback=true)';
COMMENT ON COLUMN newsletter_configs.enable_fallback IS 'Enable automatic fallback to other API keys if primary key fails';
