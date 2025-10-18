-- ============================================================
--  Table: company_investment_transactions
--  Purpose: Log every investment or return transaction
-- ============================================================

CREATE TABLE IF NOT EXISTS company_investment_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    investment_id UUID NOT NULL REFERENCES company_investments(id) ON DELETE CASCADE,

    -- Transaction type
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('investment', 'return')),

    -- Transaction details
    amount BIGINT NOT NULL CHECK (amount > 0),
    notes TEXT,

    -- Discord / Torn tracking
    initiated_by TEXT,
    confirmed_by TEXT,
    confirmed_at TIMESTAMPTZ,

    -- Transaction state
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_investment_transactions_investment_id 
    ON company_investment_transactions (investment_id);

CREATE INDEX IF NOT EXISTS idx_investment_transactions_recorded_at 
    ON company_investment_transactions (recorded_at DESC);

ALTER TABLE company_investment_transactions ENABLE ROW LEVEL SECURITY;
