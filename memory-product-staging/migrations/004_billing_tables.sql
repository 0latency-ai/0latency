-- Migration 004: Billing tables for Stripe integration
-- Run: psql $MEMORY_DB_CONN -f migrations/004_billing_tables.sql

-- Add stripe_customer_id to users if not exists
DO $$ BEGIN
    ALTER TABLE memory_service.users ADD COLUMN stripe_customer_id VARCHAR(128);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON memory_service.users(stripe_customer_id);

-- Subscriptions table
CREATE TABLE IF NOT EXISTS memory_service.subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES memory_service.users(id),
    stripe_customer_id VARCHAR(128) NOT NULL,
    stripe_subscription_id VARCHAR(128) UNIQUE,
    plan VARCHAR(32) NOT NULL DEFAULT 'pro',
    status VARCHAR(32) NOT NULL DEFAULT 'inactive',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON memory_service.subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_sub_id ON memory_service.subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON memory_service.subscriptions(status);

-- Usage records table
CREATE TABLE IF NOT EXISTS memory_service.usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES memory_service.users(id),
    endpoint VARCHAR(256),
    tokens_used INTEGER DEFAULT 0,
    memories_count INTEGER DEFAULT 0,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_records_user_id ON memory_service.usage_records(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_records_timestamp ON memory_service.usage_records(timestamp);
