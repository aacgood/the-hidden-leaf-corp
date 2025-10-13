CREATE TABLE company_financials (
    id SERIAL PRIMARY KEY,

    -- Torn company reference
    company_id INTEGER NOT NULL,

    -- The day this snapshot represents (UTC)
    capture_date DATE NOT NULL,

    -- Financial metrics
    revenue BIGINT DEFAULT 0,           -- from company newsfeed or sold_worth
    stock_cost BIGINT DEFAULT 0,        -- estimated cost of stock sold/on_order
    wages BIGINT DEFAULT 0,             -- sum of employee wages
    advertising BIGINT DEFAULT 0,       -- daily ad spend from /detailed
    profit BIGINT GENERATED ALWAYS AS (
        revenue - stock_cost - wages - advertising
    ) STORED,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Enforce one record per company per day
    CONSTRAINT uq_company_financials UNIQUE (company_id, capture_date)
);

-- Optional index to speed up date-range queries
CREATE INDEX IF NOT EXISTS idx_company_financials_company_date
    ON company_financials (company_id, capture_date DESC);

-- RLS
ALTER TABLE company_financials ENABLE ROW LEVEL SECURITY;
