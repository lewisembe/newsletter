-- Migration 009: Add visibility to newsletter_configs
-- Adds support for public/private newsletters (private by default)

ALTER TABLE newsletter_configs
    ADD COLUMN IF NOT EXISTS visibility VARCHAR(10) NOT NULL DEFAULT 'private';

-- Ensure visibility values are constrained
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_newsletter_configs_visibility'
    ) THEN
        ALTER TABLE newsletter_configs
            ADD CONSTRAINT chk_newsletter_configs_visibility
            CHECK (visibility IN ('public', 'private'));
    END IF;
END $$;

-- Backfill existing rows to 'private' explicitly
-- Legacy configs are considered public so current behavior is preserved
UPDATE newsletter_configs SET visibility = 'public' WHERE visibility IS NULL;

COMMENT ON COLUMN newsletter_configs.visibility IS 'Visibility for a newsletter config: public or private (default private)';
