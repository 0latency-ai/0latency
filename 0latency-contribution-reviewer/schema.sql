-- 0Latency Contribution Review Database Schema

CREATE TABLE IF NOT EXISTS contribution_reviews (
  id SERIAL PRIMARY KEY,
  contribution_id VARCHAR(255) UNIQUE NOT NULL,
  type VARCHAR(50) NOT NULL,
  contributor VARCHAR(255) NOT NULL,
  contributor_email VARCHAR(255),
  github_url TEXT NOT NULL,
  recommendation VARCHAR(20) NOT NULL,
  reason TEXT NOT NULL,
  confidence FLOAT NOT NULL,
  human_override VARCHAR(20),
  override_reason TEXT,
  promo_code VARCHAR(50),
  promo_tier VARCHAR(50),
  promo_sent_at TIMESTAMP,
  webhook_payload JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contribution_id ON contribution_reviews(contribution_id);
CREATE INDEX IF NOT EXISTS idx_contributor ON contribution_reviews(contributor);
CREATE INDEX IF NOT EXISTS idx_type ON contribution_reviews(type);
CREATE INDEX IF NOT EXISTS idx_recommendation ON contribution_reviews(recommendation);
CREATE INDEX IF NOT EXISTS idx_created_at ON contribution_reviews(created_at);

-- Override tracking for learning
CREATE TABLE IF NOT EXISTS review_overrides (
  id SERIAL PRIMARY KEY,
  review_id INTEGER REFERENCES contribution_reviews(id),
  original_recommendation VARCHAR(20) NOT NULL,
  override_recommendation VARCHAR(20) NOT NULL,
  override_reason TEXT,
  overridden_by VARCHAR(255) NOT NULL,
  overridden_at TIMESTAMP DEFAULT NOW()
);

-- Contributor history for repeat submissions
CREATE TABLE IF NOT EXISTS contributor_stats (
  id SERIAL PRIMARY KEY,
  contributor VARCHAR(255) UNIQUE NOT NULL,
  total_contributions INTEGER DEFAULT 0,
  approved_count INTEGER DEFAULT 0,
  rejected_count INTEGER DEFAULT 0,
  manual_review_count INTEGER DEFAULT 0,
  total_rewards_sent INTEGER DEFAULT 0,
  first_contribution_at TIMESTAMP,
  last_contribution_at TIMESTAMP,
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contributor_stats ON contributor_stats(contributor);

-- Mission Control TODO items
CREATE TABLE IF NOT EXISTS mission_control_todos (
  id SERIAL PRIMARY KEY,
  review_id INTEGER REFERENCES contribution_reviews(id),
  todo_id VARCHAR(255),
  status VARCHAR(50) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(),
  resolved_at TIMESTAMP
);
