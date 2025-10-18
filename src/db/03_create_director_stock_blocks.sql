-- Tracks which stock blocks a director currently holds
CREATE TABLE director_stock_blocks (
    id BIGSERIAL PRIMARY KEY,
    torn_user_id BIGINT REFERENCES directors(torn_user_id) ON DELETE CASCADE,
    stock_id INT NOT NULL,
    shares_held INT NOT NULL,
    has_block BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (torn_user_id, stock_id)
);

-- RLS
ALTER TABLE director_stock_blocks ENABLE ROW LEVEL SECURITY;

-- FK
ALTER TABLE director_stock_blocks
ADD CONSTRAINT director_stock_blocks_stock_id_fkey
FOREIGN KEY (stock_id) REFERENCES ref_stocks(stock_id);