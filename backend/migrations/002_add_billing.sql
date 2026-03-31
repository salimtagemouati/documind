-- DocuMind Migration: Add Stripe billing columns to users table
-- Run this BEFORE deploying the Phase 3 backend changes.
--
-- Idempotent: uses IF NOT EXISTS / safe column additions.

-- Add billing columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'inactive';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(50) DEFAULT 'free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_queries_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_queries_date TIMESTAMPTZ;

-- Index for webhook lookups by stripe_customer_id
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Comment
COMMENT ON COLUMN users.subscription_tier IS 'free | pro';
COMMENT ON COLUMN users.subscription_status IS 'active | inactive | trialing | canceled | past_due';
