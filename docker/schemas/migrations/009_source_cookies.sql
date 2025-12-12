-- Migration 009: Source Cookies Management
-- Store authentication cookies in PostgreSQL instead of filesystem
-- Author: Newsletter Utils Team
-- Date: 2025-12-06

-- Table for storing cookies per source
CREATE TABLE IF NOT EXISTS source_cookies (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    cookies JSONB NOT NULL,  -- Array of cookie objects

    -- Validation metadata
    last_validated_at TIMESTAMP,
    validation_status VARCHAR(50),  -- 'active', 'invalid', 'expired', 'not_tested'
    validation_message TEXT,
    last_validation_response_size INTEGER,
    test_url TEXT,

    -- Cookie expiry info
    has_expired_cookies BOOLEAN DEFAULT FALSE,
    expiring_soon BOOLEAN DEFAULT FALSE,
    days_until_expiry INTEGER,
    earliest_expiry TIMESTAMP,

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255),

    -- Constraints
    UNIQUE(source_id, domain)
);

-- Index for faster lookups
CREATE INDEX idx_source_cookies_domain ON source_cookies(domain);
CREATE INDEX idx_source_cookies_source_id ON source_cookies(source_id);
CREATE INDEX idx_source_cookies_validation_status ON source_cookies(validation_status);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_source_cookies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER trigger_update_source_cookies_updated_at
    BEFORE UPDATE ON source_cookies
    FOR EACH ROW
    EXECUTE FUNCTION update_source_cookies_updated_at();

-- Comments
COMMENT ON TABLE source_cookies IS 'Stores authentication cookies for sources requiring login';
COMMENT ON COLUMN source_cookies.cookies IS 'JSONB array of cookie objects with name, value, domain, path, etc.';
COMMENT ON COLUMN source_cookies.validation_status IS 'Result of last validation attempt: active, invalid, expired, not_tested';
COMMENT ON COLUMN source_cookies.test_url IS 'URL used for cookie validation';
