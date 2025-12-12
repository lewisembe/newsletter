-- Migration 009: User Newsletter Subscriptions
-- Store user subscriptions in Postgres instead of localStorage

CREATE TABLE IF NOT EXISTS user_newsletter_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    newsletter_config_id INTEGER NOT NULL REFERENCES newsletter_configs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, newsletter_config_id)
);

CREATE INDEX IF NOT EXISTS idx_user_newsletter_subscriptions_user ON user_newsletter_subscriptions(user_id);
