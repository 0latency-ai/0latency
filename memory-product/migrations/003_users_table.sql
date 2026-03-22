-- Migration 003: Users table for auth system
-- Run: psql "$MEMORY_DB_CONN" -f migrations/003_users_table.sql

CREATE TABLE IF NOT EXISTS memory_service.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE,
    name VARCHAR(256),
    avatar_url TEXT,
    github_id VARCHAR(64) UNIQUE,
    google_id VARCHAR(128) UNIQUE,
    password_hash TEXT,
    plan VARCHAR(16) NOT NULL DEFAULT 'free',
    tenant_id UUID REFERENCES memory_service.tenants(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON memory_service.users(email);
CREATE INDEX IF NOT EXISTS idx_users_github_id ON memory_service.users(github_id);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON memory_service.users(google_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON memory_service.users(tenant_id);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION memory_service.update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON memory_service.users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON memory_service.users
    FOR EACH ROW
    EXECUTE FUNCTION memory_service.update_users_updated_at();
