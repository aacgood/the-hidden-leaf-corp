-- ============================================================
--  Table: company_investments
--  Purpose: Track each investor’s total investment and returns
-- ============================================================

CREATE TABLE IF NOT EXISTS company_investments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Torn company reference
    company_id INTEGER NOT NULL,

    -- Investor info (Torn id)
    investor_id INTEGER NOT NULL,
    investor_name TEXT,

    -- Financial tracking
    total_invested BIGINT DEFAULT 0 CHECK (total_invested >= 0),
    total_returned BIGINT DEFAULT 0 CHECK (total_returned >= 0),

    -- Status: active | repaid | paused
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'repaid', 'paused')),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_company_investment UNIQUE (company_id, investor_id)
);

CREATE INDEX IF NOT EXISTS idx_investments_company ON company_investments (company_id);
CREATE INDEX IF NOT EXISTS idx_investments_investor ON company_investments (investor_id);

ALTER TABLE company_investments ENABLE ROW LEVEL SECURITY;

-- Added FK
ALTER TABLE public.company_investments
ADD CONSTRAINT fk_company
FOREIGN KEY (company_id) REFERENCES public.company(company_id);