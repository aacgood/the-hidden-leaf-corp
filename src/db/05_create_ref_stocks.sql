-- Tracks which stock blocks a director currently holds
CREATE TABLE ref_stocks (
    id BIGSERIAL PRIMARY KEY,
    stock_id INT NOT NULL,
    stock_acronym TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    stock_effect TEXT NOT NULL,
    stock_requirement INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (stock_id)
);

-- RLS
ALTER TABLE ref_stocks ENABLE ROW LEVEL SECURITY;

-- Hard coded data, this shouldnt change often enough to warrant a Lambda function and were only after a subset of stock blocks

INSERT INTO ref_stocks (stock_id, stock_acronym, stock_name, stock_effect, stock_requirement, updated_at)
VALUES
  (3, 'SYS', 'Syscore MFG', 'an Advanced firewall', 3000000, now()),
  (8, 'YAZ', 'Yazoo', 'Free banner advertising', 1000000, now()),
  (11, 'MSG', 'Messaging Inc.', 'Free classified advertising', 300000, now()),
  (13, 'TCP', 'TC Media Productions', 'a Company sales boost', 1000000, now()),
  (23, 'TGP', 'Tell Group Plc.', 'a Company advertising boost', 2500000, now()),
  (25, 'WSU', 'West Side University', 'a 10% education course time reduction', 1000000, now())
  
ON CONFLICT (stock_id) 
DO UPDATE SET
  updated_at = now();