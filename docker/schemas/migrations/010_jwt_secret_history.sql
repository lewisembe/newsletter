-- Track JWT secret history (encrypted) to support key rotation without forcing logouts
CREATE TABLE IF NOT EXISTS jwt_secret_history (
    id SERIAL PRIMARY KEY,
    secret_encrypted TEXT NOT NULL,
    secret_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
