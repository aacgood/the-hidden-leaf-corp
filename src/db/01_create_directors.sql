-- Table to store main director info
CREATE TABLE directors (
    torn_user_id BIGINT PRIMARY KEY,
    director_name TEXT NOT NULL,
    company_id BIGINT,
    api_key TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- RLS
ALTER TABLE directors ENABLE ROW LEVEL SECURITY;

--FK
ALTER TABLE directors
ADD CONSTRAINT directors_company_id_fkey
FOREIGN KEY (company_id) REFERENCES company(company_id);


ALTER TABLE directors
ADD COLUMN prospective BOOLEAN DEFAULT FALSE;