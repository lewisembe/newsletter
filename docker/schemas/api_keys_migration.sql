-- Migration: Add api_keys table for encrypted OpenAI API key management
-- Purpose: Store encrypted API keys with aliases for admin and enterprise users

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    alias VARCHAR(255) NOT NULL UNIQUE,
    encrypted_key TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    notes TEXT
);

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_alias ON api_keys(alias);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_api_keys_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_api_keys_updated_at
    BEFORE UPDATE ON api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_api_keys_updated_at();

-- Comments for documentation
COMMENT ON TABLE api_keys IS 'Stores encrypted OpenAI API keys with aliases for secure management';
COMMENT ON COLUMN api_keys.alias IS 'Human-readable identifier for the API key';
COMMENT ON COLUMN api_keys.encrypted_key IS 'Encrypted OpenAI API key using Fernet symmetric encryption';
COMMENT ON COLUMN api_keys.user_id IS 'Foreign key to users table (NULL for system-wide admin keys)';
COMMENT ON COLUMN api_keys.is_active IS 'Whether the API key is currently active and usable';
COMMENT ON COLUMN api_keys.last_used_at IS 'Timestamp of last usage for monitoring';
COMMENT ON COLUMN api_keys.usage_count IS 'Counter for number of times the key has been used';
