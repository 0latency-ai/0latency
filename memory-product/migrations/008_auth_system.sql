-- 008: Full auth system
-- Adds proper user authentication with sessions and email verification

-- Sessions table for auth tokens
CREATE TABLE IF NOT EXISTS memory_service.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    token VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    user_agent TEXT,
    ip_address INET
);

CREATE INDEX idx_sessions_token ON memory_service.sessions(token);
CREATE INDEX idx_sessions_tenant ON memory_service.sessions(tenant_id);
CREATE INDEX idx_sessions_expires ON memory_service.sessions(expires_at);

-- Email verification tokens
CREATE TABLE IF NOT EXISTS memory_service.verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    token VARCHAR(64) NOT NULL UNIQUE,
    type VARCHAR(32) NOT NULL, -- 'email_verification', 'password_reset'
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_tokens_token ON memory_service.verification_tokens(token);
CREATE INDEX idx_verification_tokens_tenant ON memory_service.verification_tokens(tenant_id);

-- Add password hash to tenants
ALTER TABLE memory_service.tenants 
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

-- RLS policies for sessions
ALTER TABLE memory_service.sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY sessions_tenant_isolation ON memory_service.sessions
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::UUID);

-- RLS policies for verification tokens
ALTER TABLE memory_service.verification_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY verification_tokens_tenant_isolation ON memory_service.verification_tokens
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::UUID);
