CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    torn_user_id BIGINT NOT NULL,        -- Torn user id
    employee_name TEXT,
    company_id BIGINT NOT NULL,          -- FK to company
    position TEXT,                       -- "Trainer", "Sales Assistant", etc
    days_in_company INT,
    wage INT,

    -- working stats
    manual_labor INT,
    intelligence INT,
    endurance INT,

    -- effectiveness breakdown
    effectiveness_total INT,             
    working_stats INT,
    settled_in INT,
    merits INT,
    director_education INT,
    management INT,
    addiction INT,
    inactivity INT,        -- negative score applied per inactive day

    allowable_addiction INT,             -- calculated addiction score
    last_updated TIMESTAMP DEFAULT NOW(),

    UNIQUE (torn_user_id)
);

-- RLS
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;

-- FK
ALTER TABLE public.employees
ADD CONSTRAINT fk_employees_company
FOREIGN KEY (company_id) REFERENCES public.company(company_id);