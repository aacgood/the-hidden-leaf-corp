CREATE TABLE company (
    company_id INTEGER PRIMARY KEY,
    torn_user_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    company_type INTEGER,          -- from profile
    popularity INTEGER,
    efficiency INTEGER,
    environment INTEGER,
    employees_hired INTEGER,
    employees_capacity INTEGER,
    storage_space INTEGER,         -- from upgrades.storage_space
    value BIGINT,
    days_old INTEGER,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);


ALTER TABLE company ENABLE ROW LEVEL SECURITY;