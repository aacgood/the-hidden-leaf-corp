CREATE TABLE IF NOT EXISTS company_donation_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to master donation record
    donation_id UUID NOT NULL REFERENCES company_donations(id) ON DELETE CASCADE,

    -- Transaction type: donation | repayment
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('donation', 'repayment')),

    -- Transaction details
    amount BIGINT NOT NULL CHECK (amount > 0),
    notes TEXT,

    -- Discord / Torn tracking
    initiated_by TEXT,              -- Discord/Torn user ID who initiated the transaction
    confirmed_by TEXT,              -- Discord/Torn user ID who confirmed the transaction
    confirmed_at TIMESTAMPTZ,
    discord_message_id TEXT,        -- ID of the message to track emoji confirmation

    -- Transaction state
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_donation_transactions_donation_id 
    ON company_donation_transactions (donation_id);

CREATE INDEX IF NOT EXISTS idx_donation_transactions_recorded_at 
    ON company_donation_transactions (recorded_at DESC);

-- RLS
ALTER TABLE company_donation_transactions ENABLE ROW LEVEL SECURITY;
