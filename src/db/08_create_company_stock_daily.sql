-- Table to store daily snapshots of company inventory stock levels

CREATE TABLE company_stock_daily (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    cost INTEGER NOT NULL,           -- cost to company per unit
    rrp INTEGER NOT NULL,            -- recommended retail price
    price INTEGER NOT NULL,          -- current sale price
    in_stock INTEGER NOT NULL,
    on_order INTEGER NOT NULL,
    sold_amount INTEGER NOT NULL,
    sold_worth INTEGER NOT NULL,
    
    estimated_remaining_days INTEGER,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE (company_id, item_name, snapshot_date)
);

DROP INDEX IF EXISTS idx_unique_company_stock_daily;

CREATE UNIQUE INDEX idx_unique_company_stock_daily
ON company_stock_daily (company_id, item_name, snapshot_date);

ALTER TABLE company_stock_daily ENABLE ROW LEVEL SECURITY;