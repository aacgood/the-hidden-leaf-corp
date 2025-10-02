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