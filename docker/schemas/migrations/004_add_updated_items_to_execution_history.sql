-- Migration: Add updated_items column to execution_history
-- Date: 2025-12-05
-- Description: Track number of existing URLs that were updated during execution

ALTER TABLE execution_history
ADD COLUMN IF NOT EXISTS updated_items INTEGER DEFAULT 0;

COMMENT ON COLUMN execution_history.updated_items IS 'Number of existing URLs that were updated (not newly inserted) during this execution';
