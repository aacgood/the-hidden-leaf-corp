-- ============================================================
--  Table: company_donations
--  Purpose: Track each donor's total contribution and repayments
-- ============================================================

CREATE TABLE IF NOT EXISTS company_donations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Torn company reference
    company_id INTEGER NOT NULL,

    -- Donor info (Torn id)
    donator_id INTEGER NOT NULL,
    donator_name TEXT,

    -- Financial tracking
    amount_donated BIGINT DEFAULT 0 CHECK (amount_donated >= 0),
    amount_repaid BIGINT DEFAULT 0 CHECK (amount_repaid >= 0),

    -- Status: active | repaid | paused
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'repaid', 'paused')),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_company_donation UNIQUE (company_id, donator_id)
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_donations_company ON company_donations (company_id);
CREATE INDEX IF NOT EXISTS idx_donations_donator ON company_donations (donator_id);

-- RLS (Row Level Security)
ALTER TABLE company_donations ENABLE ROW LEVEL SECURITY;
