CREATE TABLE company (
    company_id INTEGER PRIMARY KEY,
    torn_user_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    company_acronym VARCHAR(10) UNIQUE,
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

-- INDEX
CREATE INDEX idx_company_acronym ON company (company_acronym);

-- RLS
ALTER TABLE company ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.company
ADD COLUMN rating integer DEFAULT 0,
ADD COLUMN discord_message_id BIGINT,
ADD COLUMN discord_channel_id BIGINT,
ADD COLUMN custom_msg_1 TEXT;
